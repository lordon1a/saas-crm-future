from flask import Blueprint, request, jsonify, session, Response, current_app, send_from_directory
from models import db, Conversation, Message, Customer, QuickReply, Note, User, Workspace
from models_crm import Contact
from services.meta_api_client import MetaAPIClient
from services.conversation_manager import ConversationManager
from services.message_manager import MessageManager
from services.quick_reply_manager import QuickReplyManager
from services.collaboration_service import CollaborationService
from services.email_hub_service import EmailHubService
from services.telegram_service import TelegramService
from realtime import socketio
from datetime import datetime
from sqlalchemy import or_
from config import Config
import json, time, queue, threading, os
import logging
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)
MAX_MEDIA_UPLOAD_SIZE = 15 * 1024 * 1024  # 15MB

bp = Blueprint('api', __name__, url_prefix='/api')

def _message_to_json(msg, include_sender_name=False, user_cache=None):
    media_type = getattr(msg, 'media_type', None)
    media_url = getattr(msg, 'media_url', None)
    d = {
        'id': msg.id,
        'conversation_id': msg.conversation_id,
        'sender_type': msg.sender_type,
        'message_body': msg.message_body,
        'channel': getattr(msg, 'channel', 'whatsapp') or 'whatsapp',
        'is_read': msg.is_read,
        'created_at': msg.created_at.isoformat(),
        'media_type': media_type,
        'media_url': f"/api/media/{media_url}" if media_url else None,
    }
    if include_sender_name and msg.sender_type == 'agent' and user_cache is not None:
        d['sender_name'] = user_cache.get(msg.sender_id) if msg.sender_id else None
    elif include_sender_name and hasattr(msg, 'sender') and msg.sender:
        d['sender_name'] = msg.sender.name
    else:
        d['sender_name'] = None
    return d


def _emit_realtime_message(workspace_id, conversation, message):
    try:
        socketio.emit(
            'new_incoming_message',
            {
                'message_id': message.id,
                'conversation_id': conversation.id,
                'contact_id': conversation.customer_id,
                'text': message.message_body,
                'sender_type': message.sender_type,
                'channel': getattr(message, 'channel', 'whatsapp') or 'whatsapp',
                'timestamp': message.created_at.isoformat() if message.created_at else None,
            },
            room=f'contact_{conversation.customer_id}',
        )
        socketio.emit(
            'inbox_updated',
            {
                'conversation_id': conversation.id,
                'contact_id': conversation.customer_id,
                'message_id': message.id,
            },
            room=f'ws_{workspace_id}',
        )
    except Exception as exc:
        logger.warning('Socket emit failed for outgoing message: %s', exc)

def login_required_api(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'error': 'Unauthorized'}), 401
        if not session.get('workspace_id'):
            return jsonify({'error': 'Workspace context missing'}), 401
        return f(*args, **kwargs)
    return decorated

@bp.route('/conversations', methods=['GET'])
@login_required_api
def get_conversations():
    """Get list of conversations for current workspace - OPTIMIZED"""
    from sqlalchemy.orm import joinedload
    from sqlalchemy import func
    
    workspace_id = session.get('workspace_id')
    status = request.args.get('status', '').strip()
    tag = request.args.get('tag', '').strip()
    search = request.args.get('search', '').strip()
    limit = int(request.args.get('limit', 50))
    
    # OPTIMIZED: Eager load customer to avoid N+1
    query = Conversation.query.options(joinedload(Conversation.customer)).filter(
        Conversation.workspace_id == workspace_id
    )
    
    if status:
        query = query.filter(Conversation.status == status)
    
    if tag:
        query = query.filter(Conversation.tags.ilike(f'%{tag}%'))
    
    if search:
        query = query.join(Customer).filter(
            or_(
                Customer.profile_name.ilike(f'%{search}%'),
                Customer.phone_number.ilike(f'%{search}%')
            )
        )
    
    conversations = query.order_by(Conversation.last_message_at.desc()).limit(limit).all()
    
    # OPTIMIZED: Tek sorguda tüm sayaçlar
    counts = db.session.query(
        func.count(Conversation.id).label('total'),
        func.sum(db.case((Conversation.status == 'open', 1), else_=0)).label('open'),
        func.sum(db.case((Conversation.status == 'pending', 1), else_=0)).label('pending')
    ).filter(Conversation.workspace_id == workspace_id).first()
    
    total_count = counts.total or 0
    open_count = counts.open or 0
    pending_count = counts.pending or 0
    
    # OPTIMIZED: Tüm conversation ID'leri için tek sorguda last messages
    conv_ids = [c.id for c in conversations]
    
    # Son mesajları tek sorguda çek
    last_messages = {}
    if conv_ids:
        subq = db.session.query(
            Message.conversation_id,
            func.max(Message.created_at).label('max_created')
        ).filter(
            Message.conversation_id.in_(conv_ids)
        ).group_by(Message.conversation_id).subquery()
        
        last_msgs = db.session.query(Message).join(
            subq,
            db.and_(
                Message.conversation_id == subq.c.conversation_id,
                Message.created_at == subq.c.max_created
            )
        ).all()
        
        for msg in last_msgs:
            last_messages[msg.conversation_id] = msg.message_body
    
    # OPTIMIZED: Tüm unread counts tek sorguda
    unread_counts = {}
    if conv_ids:
        unread_data = db.session.query(
            Message.conversation_id,
            func.count(Message.id).label('unread')
        ).filter(
            Message.conversation_id.in_(conv_ids),
            Message.sender_type == 'customer',
            Message.is_read == False
        ).group_by(Message.conversation_id).all()
        
        for row in unread_data:
            unread_counts[row.conversation_id] = row.unread
    
    # OPTIMIZED: CRM contacts tek sorguda
    customer_ids = [c.customer.id for c in conversations]
    crm_contacts = {}
    if customer_ids:
        contacts = Contact.query.options(joinedload(Contact.company)).filter(
            Contact.workspace_id == workspace_id,
            Contact.customer_id.in_(customer_ids)
        ).all()
        
        for contact in contacts:
            crm_contacts[contact.customer_id] = {
                'id': contact.id,
                'full_name': contact.full_name,
                'role': contact.role,
                'job_title': contact.job_title,
                'company_id': contact.company_id,
                'company_name': contact.company.name if contact.company else None
            }
    
    # Build result
    result = []
    for conv in conversations:
        result.append({
            'id': conv.id,
            'customer': {
                'id': conv.customer.id,
                'phone_number': conv.customer.phone_number,
                'profile_name': conv.customer.profile_name,
                'email': conv.customer.email,
                'notes': conv.customer.notes,
                'private_notes': conv.customer.private_notes,
                'crm_contact': crm_contacts.get(conv.customer.id)
            },
            'status': conv.status,
            'tags': conv.tags,
            'notes': conv.notes,
            'last_message': last_messages.get(conv.id, ''),
            'last_message_at': conv.last_message_at.isoformat(),
            'unread_count': unread_counts.get(conv.id, 0),
            'message_count': len(conv.messages)
        })
    
    return jsonify({
        'conversations': result,
        'counts': {
            'total': total_count,
            'open': open_count,
            'pending': pending_count
        }
    }), 200

# ─── SSE Notification Broadcast ─────────────────────────────────────────────
# Basit in-memory queue (tek worker; production'da Redis PubSub kullanın)
_sse_listeners = {}  # workspace_id -> [queue, ...]
_sse_lock = threading.Lock()

def push_notification(workspace_id, event_type, data):
    """Webhook/message handler tarafından çağrılır, SSE subscriber'larına iletir"""
    with _sse_lock:
        listeners = _sse_listeners.get(workspace_id, [])
        dead = []
        for q in listeners:
            try:
                q.put_nowait((event_type, data))
            except Exception:
                dead.append(q)
        for q in dead:
            listeners.remove(q)

@bp.route('/notifications/stream')
@login_required_api
def notifications_stream():
    """SSE endpoint: yeni mesaj geldiğinde frontend'e push gönderir"""
    workspace_id = session.get('workspace_id')
    q = queue.Queue(maxsize=50)
    with _sse_lock:
        _sse_listeners.setdefault(workspace_id, []).append(q)

    def generate():
        # Bağlantı kurulduğunu bildir
        yield 'event: connected\ndata: {"ok": true}\n\n'
        try:
            while True:
                try:
                    event_type, data = q.get(timeout=25)
                    yield f'event: {event_type}\ndata: {json.dumps(data)}\n\n'
                except queue.Empty:
                    yield ': heartbeat\n\n'  # keep-alive
        except GeneratorExit:
            pass
        finally:
            with _sse_lock:
                listeners = _sse_listeners.get(workspace_id, [])
                if q in listeners:
                    listeners.remove(q)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )

@bp.route('/conversations/<int:conversation_id>', methods=['GET'])
@login_required_api
def get_conversation_detail(conversation_id):
    """Get conversation details verifying workspace ownership"""
    workspace_id = session.get('workspace_id')
    conversation = Conversation.query.filter_by(id=conversation_id, workspace_id=workspace_id).first()
    if not conversation:
        return jsonify({'error': 'Conversation not found in this workspace'}), 404
    
    include_internal = (session.get('user_role') or '').lower() != 'customer'
    try:
        notes = CollaborationService.list_notes_for_conversation(conversation_id, include_internal)
    except Exception as exc:
        logger.warning('Conversation detail note load fallback for %s: %s', conversation_id, exc)
        notes = []
    
    return jsonify({
        'id': conversation.id,
        'customer': {
            'id': conversation.customer.id,
            'phone_number': conversation.customer.phone_number,
            'profile_name': conversation.customer.profile_name,
            'email': conversation.customer.email,
            'notes': conversation.customer.notes,
            'private_notes': conversation.customer.private_notes,
            'created_at': conversation.customer.created_at.isoformat()
        },
        'status': conversation.status,
        'tags': conversation.tags,
        'notes': conversation.notes,
        'assigned_to': conversation.assigned_to,
        'conversation_notes': [
            {
                'id': note.id,
                'content': note.content,
                'is_internal': bool(getattr(note, 'is_internal', False)),
                'created_at': note.created_at.isoformat()
            } for note in notes
        ],
        'message_count': len(conversation.messages),
        'created_at': conversation.last_message_at.isoformat()
    }), 200

@bp.route('/conversations/<int:conversation_id>/full', methods=['GET'])
@login_required_api
def get_conversation_full(conversation_id):
    """Konuşma detayı + mesajlarını tek istekte döndür (performans optimizasyonu)"""
    workspace_id = session.get('workspace_id')
    conversation = Conversation.query.filter_by(
        id=conversation_id, workspace_id=workspace_id
    ).first()
    if not conversation:
        return jsonify({'error': 'Conversation not found'}), 404

    # Mesajlar (eager: sender adını da al)
    msgs = Message.query.filter_by(conversation_id=conversation_id)\
        .order_by(Message.created_at.asc()).all()

    user_cache = {}
    for msg in msgs:
        if msg.sender_id and msg.sender_id not in user_cache:
            u = User.query.get(msg.sender_id)
            user_cache[msg.sender_id] = u.name if u else None
    messages_data = [_message_to_json(msg, include_sender_name=True, user_cache=user_cache) for msg in msgs]

    # Mark unread as read (aynı istekte)
    Message.query.filter_by(
        conversation_id=conversation_id,
        sender_type='customer',
        is_read=False
    ).update({'is_read': True})
    db.session.commit()

    include_internal = (session.get('user_role') or '').lower() != 'customer'
    try:
        notes = CollaborationService.list_notes_for_conversation(conversation_id, include_internal)
    except Exception as exc:
        logger.warning('Conversation full note load fallback for %s: %s', conversation_id, exc)
        notes = []

    return jsonify({
        'conversation': {
            'id': conversation.id,
            'status': conversation.status,
            'tags': conversation.tags,
            'notes': conversation.notes,
            'assigned_to': conversation.assigned_to,
            'created_at': conversation.last_message_at.isoformat(),
            'customer': {
                'id': conversation.customer.id,
                'phone_number': conversation.customer.phone_number,
                'profile_name': conversation.customer.profile_name,
                'email': conversation.customer.email,
                'notes': conversation.customer.notes,
                'private_notes': conversation.customer.private_notes,
                'created_at': conversation.customer.created_at.isoformat()
            },
            'conversation_notes': [
                {
                    'id': n.id,
                    'content': n.content,
                    'is_internal': bool(getattr(n, 'is_internal', False)),
                    'created_at': n.created_at.isoformat(),
                }
                for n in notes
            ]
        },
        'messages': messages_data
    }), 200


@bp.route('/conversations/<int:conversation_id>/assign', methods=['PUT'])
@login_required_api
def assign_conversation(conversation_id):
    """Konuşmayı bir temsilciye ata (veya atamayı kaldır)"""
    workspace_id = session.get('workspace_id')
    conv = Conversation.query.filter_by(id=conversation_id, workspace_id=workspace_id).first_or_404()
    data = request.get_json()
    user_id = data.get('user_id')  # None ise atama kaldır
    if user_id:
        # Verilen user'ın bu workspace'e ait olduğunu doğrula
        target = User.query.filter_by(id=user_id, workspace_id=workspace_id).first()
        if not target:
            return jsonify({'error': 'Kullanıcı bu Workspace\'e ait değil'}), 400
    conv.assigned_to = user_id
    db.session.commit()
    return jsonify({'status': 'assigned', 'assigned_to': user_id}), 200

@bp.route('/team', methods=['GET'])
@login_required_api
def get_workspace_team():
    """Frontend'de Temsilci Ata dropdown'u için workspace üyelerini listele"""
    workspace_id = session.get('workspace_id')
    users = User.query.filter_by(workspace_id=workspace_id).all()
    return jsonify([{'id': u.id, 'name': u.name, 'role': u.role} for u in users]), 200

@bp.route('/customers/<int:customer_id>/profile', methods=['GET'])
@login_required_api
def get_customer_profile(customer_id):
    """360° Müşteri profili: istatistik + tüm konuşma geçmişi + notlar"""
    workspace_id = session.get('workspace_id')
    customer = Customer.query.filter_by(id=customer_id, workspace_id=workspace_id).first_or_404()

    # Tüm konuşmaları al (en yeniden en eskiye)
    conversations = Conversation.query.filter_by(
        customer_id=customer_id,
        workspace_id=workspace_id
    ).order_by(Conversation.last_message_at.desc()).all()

    # İstatistikler
    total_convs = len(conversations)
    closed_convs = sum(1 for c in conversations if c.status == 'closed')
    open_convs = sum(1 for c in conversations if c.status == 'open')

    # Etiket frekansı (tüm konuşmaların etiketlerini topla)
    tag_freq = {}
    for conv in conversations:
        if conv.tags:
            for tag in conv.tags.split(','):
                tag = tag.strip()
                if tag:
                    tag_freq[tag] = tag_freq.get(tag, 0) + 1

    # Atanan temsilci bilgisi
    def get_assignee_name(user_id):
        if not user_id: return None
        u = User.query.get(user_id)
        return u.name if u else None

    # Konuşma geçmişiñ son 20 konuşma
    conv_history = []
    for conv in conversations[:20]:
        last_msg = Message.query.filter_by(
            conversation_id=conv.id
        ).order_by(Message.created_at.desc()).first()
        conv_history.append({
            'id': conv.id,
            'status': conv.status,
            'tags': conv.tags,
            'last_message': last_msg.message_body[:80] if last_msg else '',
            'last_message_at': conv.last_message_at.isoformat(),
            'message_count': len(conv.messages),
            'assigned_to_name': get_assignee_name(conv.assigned_to)
        })

    return jsonify({
        'customer': {
            'id': customer.id,
            'profile_name': customer.profile_name or customer.phone_number,
            'phone_number': customer.phone_number,
            'email': customer.email or '',
            'notes': customer.notes or '',
            'private_notes': customer.private_notes or '',
            'created_at': customer.created_at.isoformat()
        },
        'stats': {
            'total_conversations': total_convs,
            'closed_conversations': closed_convs,
            'open_conversations': open_convs,
            'tag_frequency': tag_freq,
            'first_contact': conversations[-1].last_message_at.isoformat() if conversations else customer.created_at.isoformat()
        },
        'conversations': conv_history
    }), 200

@bp.route('/conversations/<int:conversation_id>/messages', methods=['GET'])
@login_required_api
def get_messages(conversation_id):
    """Get messages for a conversation verifying workspace ownership"""
    workspace_id = session.get('workspace_id')
    conversation = Conversation.query.filter_by(id=conversation_id, workspace_id=workspace_id).first()
    if not conversation:
        return jsonify({'error': 'Conversation not found'}), 404

    after_id = request.args.get('after_id', type=int)
    query = Message.query.filter_by(conversation_id=conversation_id)
    if after_id and after_id > 0:
        query = query.filter(Message.id > after_id)

    messages = query.order_by(Message.created_at.asc()).all()
    
    result = []
    for msg in messages:
        sender_name = None
        if msg.sender_type != 'customer' and msg.sender:
            sender_name = msg.sender.name
        result.append({
            'id': msg.id,
            'sender_type': msg.sender_type,
            'sender_name': sender_name,
            'message_body': msg.message_body,
            'channel': getattr(msg, 'channel', 'whatsapp') or 'whatsapp',
            'is_read': msg.is_read,
            'created_at': msg.created_at.isoformat(),
            'media_type': getattr(msg, 'media_type', None),
            'media_url': f"/api/media/{msg.media_url}" if getattr(msg, 'media_url', None) else None,
        })
    return jsonify(result), 200

@bp.route('/conversations/<int:conversation_id>/mark-read', methods=['POST'])
@login_required_api
def mark_conversation_read(conversation_id):
    """Mark all customer messages in conversation as read"""
    workspace_id = session.get('workspace_id')
    conversation = Conversation.query.filter_by(id=conversation_id, workspace_id=workspace_id).first()
    if not conversation:
        return jsonify({'error': 'Conversation not found'}), 404
    
    Message.query.filter_by(
        conversation_id=conversation_id,
        sender_type='customer',
        is_read=False
    ).update({'is_read': True})
    db.session.commit()
    
    return jsonify({'status': 'ok'}), 200

@bp.route('/messages/send', methods=['POST'])
@login_required_api
def send_message():
    """Send message to customer"""
    data = request.get_json()
    conversation_id = data.get('conversation_id')
    message_body = data.get('message_body', '').strip()
    channel = (data.get('channel') or 'whatsapp').strip().lower()
    workspace_id = session.get('workspace_id')
    
    if not message_body:
        return jsonify({'error': 'Mesaj boş olamaz'}), 400
    
    conversation = Conversation.query.filter_by(id=conversation_id, workspace_id=workspace_id).first()
    if not conversation:
        return jsonify({'error': 'Conversation not found'}), 404
    
    customer = conversation.customer
    workspace = Workspace.query.get(workspace_id)

    if channel not in {'whatsapp', 'telegram', 'email'}:
        return jsonify({'error': 'Geçersiz kanal'}), 400

    result = {'success': False, 'error': 'Gönderilemedi', 'message_id': None}

    if channel == 'whatsapp':
        token = (workspace and workspace.whatsapp_access_token) or None
        phone_id = (workspace and workspace.whatsapp_phone_number_id) or None
        meta_client = MetaAPIClient(access_token=token, phone_number_id=phone_id)
        result = meta_client.send_text_message(customer.phone_number, message_body)
    elif channel == 'telegram':
        if not workspace or not workspace.telegram_bot_token:
            return jsonify({'error': 'Telegram bot token yapılandırılmamış'}), 400
        if not customer.telegram_chat_id:
            return jsonify({'error': 'Bu müşteri için telegram_chat_id yok'}), 400
        telegram_service = TelegramService(workspace.telegram_bot_token)
        result = telegram_service.send_message(customer.telegram_chat_id, message_body)
    else:
        if not customer.email:
            return jsonify({'error': 'Müşterinin email adresi yok'}), 400
        try:
            EmailHubService.queue_outbound_email(
                workspace_id=workspace_id,
                user_id=session.get('user_id', 1),
                to_email=customer.email,
                subject='CRM Mesajı',
                body_text=message_body,
                body_html='',
            )
            result = {'success': True, 'message_id': f'email-{time.time_ns()}', 'error': None}
        except Exception as exc:
            result = {'success': False, 'message_id': None, 'error': str(exc)}
    
    if result['success']:
        # Save to database
        sender_id = session.get('user_id', 1)
        message = MessageManager.save_outgoing_message(
            conversation_id=conversation_id,
            message_body=message_body,
            sender_id=sender_id,
            meta_message_id=result['message_id'],
            channel=channel,
        )
        
        # Giden mesajları otomatik okundu işaretle
        message.is_read = True
        
        # Update conversation last_message_at
        ConversationManager.update_last_message_time(conversation_id)
        db.session.commit()
        _emit_realtime_message(workspace_id, conversation, message)
        
        return jsonify({
            'status': 'sent',
            'message_id': message.id,
            'message': _message_to_json(message)
        }), 200
    
    return jsonify({'error': result['error']}), 500


# ─── Medya: dosya sunumu ve medya gönderimi ─────────────────────────────────

@bp.route('/media/<path:subpath>', methods=['GET'])
@login_required_api
def serve_media(subpath):
    """Workspace'e ait medya dosyasını sunar. subpath = workspace_1/xxx.jpg"""
    workspace_id = session.get('workspace_id')
    if not subpath.startswith(f"workspace_{workspace_id}/") and subpath != f"workspace_{workspace_id}":
        return jsonify({'error': 'Forbidden'}), 403
    root = os.path.abspath(Config.MEDIA_UPLOAD_FOLDER)
    filepath = os.path.abspath(os.path.join(root, subpath))
    if os.path.commonpath([root, filepath]) != root or not os.path.isfile(filepath):
        return jsonify({'error': 'Not found'}), 404
    directory = os.path.dirname(filepath)
    filename = os.path.basename(filepath)
    return send_from_directory(directory, filename, as_attachment=False)


@bp.route('/messages/send-media', methods=['POST'])
@login_required_api
def send_media():
    """Medya gönder (görsel veya belge). Form: conversation_id, type=image|document, file, caption (opsiyonel)"""
    workspace_id = session.get('workspace_id')
    conversation_id = request.form.get('conversation_id', type=int)
    media_type = (request.form.get('type') or 'image').strip().lower()
    caption = (request.form.get('caption') or '').strip()
    if not conversation_id:
        return jsonify({'error': 'conversation_id gerekli'}), 400
    if media_type not in ('image', 'document'):
        return jsonify({'error': 'type image veya document olmalı'}), 400
    if 'file' not in request.files:
        return jsonify({'error': 'Dosya yükleyin'}), 400
    file = request.files['file']
    if not file or not file.filename:
        return jsonify({'error': 'Geçerli dosya seçin'}), 400

    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > MAX_MEDIA_UPLOAD_SIZE:
        return jsonify({'error': 'Dosya çok büyük (maksimum 15MB)'}), 400
    conversation = Conversation.query.filter_by(id=conversation_id, workspace_id=workspace_id).first()
    if not conversation:
        return jsonify({'error': 'Conversation not found'}), 404
    workspace = Workspace.query.get(workspace_id)
    if not workspace or not workspace.whatsapp_access_token or not workspace.whatsapp_phone_number_id:
        return jsonify({'error': 'WhatsApp kanalı yapılandırılmamış'}), 400
    root = os.path.abspath(Config.MEDIA_UPLOAD_FOLDER)
    folder = os.path.join(root, f"workspace_{workspace_id}")
    os.makedirs(folder, exist_ok=True)
    original_name = secure_filename(file.filename) or ('upload.jpg' if media_type == 'image' else 'upload.pdf')
    ext = os.path.splitext(original_name)[1] or ('.jpg' if media_type == 'image' else '.pdf')
    safe_name = secure_filename(f"{time.time_ns()}_{original_name}")[:200]
    if not safe_name.endswith(ext):
        safe_name += ext
    relative_path = f"workspace_{workspace_id}/{safe_name}"
    filepath = os.path.join(folder, safe_name)
    file.save(filepath)
    base_url = request.url_root.rstrip('/')
    media_full_url = f"{base_url}/api/media/{relative_path}"
    meta_client = MetaAPIClient(
        access_token=workspace.whatsapp_access_token,
        phone_number_id=workspace.whatsapp_phone_number_id
    )
    if media_type == 'image':
        result = meta_client.send_image(conversation.customer.phone_number, media_full_url, caption=caption or None)
    else:
        result = meta_client.send_document(
            conversation.customer.phone_number, media_full_url,
            caption=caption or None, filename=file.filename
        )
    if not result.get('success'):
        return jsonify({'error': result.get('error', 'Gönderilemedi')}), 500
    body_label = '[🖼️ Görsel]' if media_type == 'image' else '[📄 Belge]'
    if caption:
        body_label += ' ' + caption
    message = MessageManager.save_outgoing_message(
        conversation_id=conversation_id,
        message_body=body_label,
        sender_id=session.get('user_id'),
        meta_message_id=result['message_id'],
        channel='whatsapp',
        media_type=media_type,
        media_url=relative_path
    )
    ConversationManager.update_last_message_time(conversation_id)
    db.session.commit()
    _emit_realtime_message(workspace_id, conversation, message)
    return jsonify({
        'status': 'sent',
        'message_id': message.id,
        'message': _message_to_json(message)
    }), 200

@bp.route('/conversations/<int:conversation_id>/status', methods=['PUT'])
@login_required_api
def update_status(conversation_id):
    """Update conversation status"""
    workspace_id = session.get('workspace_id')
    data = request.get_json()
    status = data.get('status')
    
    conversation = Conversation.query.filter_by(id=conversation_id, workspace_id=workspace_id).first()
    if not conversation:
        return jsonify({'error': 'Conversation not found'}), 404
    
    if status not in ['open', 'resolved', 'pending']:
        return jsonify({'error': 'Invalid status'}), 400
    
    conversation.status = status
    db.session.commit()
    
    return jsonify({'status': 'updated', 'new_status': status}), 200

@bp.route('/conversations/<int:conversation_id>/tags', methods=['POST'])
@login_required_api
def update_tags(conversation_id):
    """Update conversation tags"""
    workspace_id = session.get('workspace_id')
    data = request.get_json()
    tags = data.get('tags')
    
    conversation = Conversation.query.filter_by(id=conversation_id, workspace_id=workspace_id).first()
    if not conversation:
        return jsonify({'error': 'Conversation not found'}), 404
        
    conversation.tags = tags
    db.session.commit()
    return jsonify({'status': 'updated', 'tags': conversation.tags}), 200

@bp.route('/conversations/<int:conversation_id>/notes', methods=['POST'])
@login_required_api
def add_note(conversation_id):
    """Add note to conversation"""
    workspace_id = session.get('workspace_id')
    data = request.get_json()
    content = data.get('content')
    is_internal = bool(data.get('is_internal', False))
    
    if not content:
        return jsonify({'error': 'Content required'}), 400
    
    conversation = Conversation.query.filter_by(id=conversation_id, workspace_id=workspace_id).first()
    if not conversation:
        return jsonify({'error': 'Conversation not found'}), 404
    
    note = Note(
        conversation_id=conversation_id,
        user_id=session.get('user_id', 1),
        content=content,
        is_internal=is_internal,
    )
    db.session.add(note)
    db.session.commit()

    CollaborationService.process_note_mentions(
        workspace_id=workspace_id,
        note_id=note.id,
        actor_user_id=session.get('user_id'),
    )
    
    return jsonify({
        'id': note.id,
        'content': note.content,
        'is_internal': bool(note.is_internal),
        'created_at': note.created_at.isoformat()
    }), 201

@bp.route('/customers/<int:customer_id>', methods=['PUT'])
@login_required_api
def update_customer(customer_id):
    """Update customer information"""
    workspace_id = session.get('workspace_id')
    data = request.get_json()
    
    customer = Customer.query.filter_by(id=customer_id, workspace_id=workspace_id).first()
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404
    
    if 'profile_name' in data:
        customer.profile_name = data['profile_name']
    if 'email' in data:
        customer.email = data['email']
    if 'notes' in data:
        customer.notes = data['notes']
    if 'private_notes' in data:
        customer.private_notes = data['private_notes']
    
    db.session.commit()
    
    return jsonify({'status': 'updated'}), 200

@bp.route('/quick-replies', methods=['GET'])
@login_required_api
def get_quick_replies():
    """Get all quick replies for current workspace"""
    workspace_id = session.get('workspace_id')
    replies = QuickReplyManager.get_all_quick_replies(workspace_id)
    result = [{'id': r.id, 'title': r.title, 'body': r.body} for r in replies]
    return jsonify(result), 200

@bp.route('/quick-replies', methods=['POST'])
@login_required_api
def create_quick_reply():
    """Yeni hızlı yanıt oluştur"""
    workspace_id = session.get('workspace_id')
    data = request.get_json()
    title = data.get('title', '').strip()
    body = data.get('body', '').strip()
    
    if not title or not body:
        return jsonify({'error': 'Başlık ve içerik zorunludur'}), 400
        
    reply = QuickReply(workspace_id=workspace_id, title=title, body=body)
    db.session.add(reply)
    db.session.commit()
    
    return jsonify({'id': reply.id, 'title': reply.title, 'body': reply.body}), 201

@bp.route('/quick-replies/<int:reply_id>', methods=['PUT'])
@login_required_api
def update_quick_reply(reply_id):
    """Hızlı yanıtı güncelle"""
    workspace_id = session.get('workspace_id')
    reply = QuickReply.query.filter_by(id=reply_id, workspace_id=workspace_id).first_or_404()
    data = request.get_json()
    
    if 'title' in data: reply.title = data['title'].strip()
    if 'body' in data: reply.body = data['body'].strip()
    
    db.session.commit()
    return jsonify({'status': 'updated'}), 200

@bp.route('/quick-replies/<int:reply_id>', methods=['DELETE'])
@login_required_api
def delete_quick_reply(reply_id):
    """Hızlı yanıtı sil"""
    workspace_id = session.get('workspace_id')
    reply = QuickReply.query.filter_by(id=reply_id, workspace_id=workspace_id).first_or_404()
    db.session.delete(reply)
    db.session.commit()
    return jsonify({'status': 'deleted'}), 200

# ─── Broadcast (Toplu Mesaj) ─────────────────────────────────────────────────

@bp.route('/broadcast/send', methods=['POST'])
@login_required_api
def broadcast_send():
    """Hedef kitleye toplu mesaj gönder (tüm müşteriler veya etikete göre)."""
    workspace_id = session.get('workspace_id')
    data = request.get_json() or {}
    target = (data.get('target') or 'all').strip()
    tag = (data.get('tag') or '').strip()
    content = (data.get('content') or '').strip()

    if not content:
        return jsonify({'error': 'Mesaj içeriği zorunludur'}), 400

    workspace = Workspace.query.get(workspace_id)
    if not workspace or not workspace.whatsapp_access_token or not workspace.whatsapp_phone_number_id:
        return jsonify({'error': 'WhatsApp kanalı yapılandırılmamış. Ayarlar > Workspace bölümünden Phone Number ID ve Access Token girin.'}), 400

    if target == 'tags' and not tag:
        return jsonify({'error': 'Etiket seçimi zorunludur'}), 400

    if target == 'all':
        customers = Customer.query.filter_by(workspace_id=workspace_id).all()
    else:
        # Etikete göre: bu etikete sahip konuşması olan müşteriler (benzersiz)
        customer_ids = [r[0] for r in db.session.query(Conversation.customer_id).filter(
            Conversation.workspace_id == workspace_id,
            Conversation.tags.isnot(None),
            Conversation.tags.ilike(f'%{tag}%')
        ).distinct().all()]
        customers = Customer.query.filter(
            Customer.workspace_id == workspace_id,
            Customer.id.in_(customer_ids)
        ).all() if customer_ids else []

    if not customers:
        return jsonify({'error': 'Hedef kitle bulunamadı', 'count': 0}), 200

    meta_client = MetaAPIClient(
        access_token=workspace.whatsapp_access_token,
        phone_number_id=workspace.whatsapp_phone_number_id
    )
    sent = 0
    failed = 0
    for c in customers:
        try:
            result = meta_client.send_text_message(c.phone_number, content)
            if result.get('success'):
                sent += 1
            else:
                failed += 1
                logger.warning('Broadcast gönderim hatası %s: %s', c.phone_number, result.get('error'))
        except Exception as e:
            failed += 1
            logger.exception('Broadcast exception %s: %s', c.phone_number, e)
        time.sleep(1)  # Meta rate limit için aralık

    return jsonify({
        'status': 'ok',
        'count': sent,
        'total': len(customers),
        'failed': failed
    }), 200

@bp.route('/stats', methods=['GET'])
@login_required_api
def get_stats():
    """Get dashboard statistics for the specific workspace"""
    workspace_id = session.get('workspace_id')
    
    total_conversations = Conversation.query.filter_by(workspace_id=workspace_id).count()
    open_conversations = Conversation.query.filter_by(workspace_id=workspace_id, status='open').count()
    pending_conversations = Conversation.query.filter_by(workspace_id=workspace_id, status='pending').count()
    resolved_conversations = Conversation.query.filter_by(workspace_id=workspace_id, status='resolved').count()
    total_customers = Customer.query.filter_by(workspace_id=workspace_id).count()
    
    # Message join over conversation to filter by workspace
    total_messages = Message.query.join(Conversation).filter(Conversation.workspace_id == workspace_id).count()
    
    # Today's stats
    today = datetime.utcnow().date()
    today_messages = Message.query.join(Conversation).filter(
        Conversation.workspace_id == workspace_id,
        db.func.date(Message.created_at) == today
    ).count()
    
    return jsonify({
        'total_conversations': total_conversations,
        'open_conversations': open_conversations,
        'pending_conversations': pending_conversations,
        'resolved_conversations': resolved_conversations,
        'total_customers': total_customers,
        'total_messages': total_messages,
        'today_messages': today_messages
    }), 200


# ─── User & Team API ────────────────────────────────────────────────────────────

@bp.route('/me', methods=['GET'])
@login_required_api
def get_current_user_info():
    """Get current logged-in user information"""
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'role': user.role,
        'workspace_id': user.workspace_id
    }), 200


@bp.route('/team', methods=['GET'])
@login_required_api
def get_team_members():
    """Get all team members in current workspace"""
    workspace_id = session.get('workspace_id')
    users = User.query.filter_by(workspace_id=workspace_id).all()
    
    return jsonify([{
        'id': u.id,
        'name': u.name,
        'email': u.email,
        'role': u.role
    } for u in users]), 200


# ─── Analytics Dashboard API ───────────────────────────────────────────────────

@bp.route('/analytics', methods=['GET'])
@login_required_api
def get_analytics():
    """Kapsamlı analytics verisi: KPI, trend, agent perf, tag dağılımı - OPTIMIZED"""
    from datetime import timedelta
    from sqlalchemy import func
    import collections

    workspace_id = session.get('workspace_id')
    date_range = request.args.get('range', 'last7days')
    today = datetime.utcnow().date()
    now = datetime.utcnow()

    # Date calculations for filtering
    if date_range == 'today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif date_range == 'yesterday':
        start_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        now = start_date + timedelta(days=1)
    elif date_range == 'last30days':
        start_date = now - timedelta(days=30)
    elif date_range == 'thisMonth':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else: # last7days default
        start_date = now - timedelta(days=7)

    # ── OPTIMIZED: Tek sorguda tüm conversation istatistikleri ───────────────────
    conv_stats = db.session.query(
        func.count(Conversation.id).label('total'),
        func.sum(db.case((Conversation.status == 'open', 1), else_=0)).label('open'),
        func.sum(db.case((Conversation.status == 'resolved', 1), else_=0)).label('closed'),
        func.sum(db.case((Conversation.status == 'pending', 1), else_=0)).label('pending')
    ).filter(Conversation.workspace_id == workspace_id).first()
    
    total_conv = conv_stats.total or 0
    open_conv = conv_stats.open or 0
    closed_conv = conv_stats.closed or 0
    pending_conv = conv_stats.pending or 0
    
    # ── OPTIMIZED: Basit count sorgular ───────────────────
    total_cust = Customer.query.filter_by(workspace_id=workspace_id).count()
    total_msg = Message.query.join(Conversation).filter(Conversation.workspace_id == workspace_id).count()
    
    # ── Bugünkü istatistikler ───────────────────
    today_start = datetime.combine(today, datetime.min.time())
    today_conv = Conversation.query.filter(
        Conversation.workspace_id == workspace_id,
        Conversation.last_message_at >= today_start
    ).count()
    today_msg = Message.query.join(Conversation).filter(
        Conversation.workspace_id == workspace_id,
        Message.created_at >= today_start
    ).count()

    # ── Haftalık trend (basitleştirilmiş) ───────────────────
    week_start = today - timedelta(days=today.weekday())
    last_week_start = week_start - timedelta(days=7)
    
    this_week_conv = Conversation.query.filter(
        Conversation.workspace_id == workspace_id,
        Conversation.last_message_at >= week_start
    ).count()
    last_week_conv = Conversation.query.filter(
        Conversation.workspace_id == workspace_id,
        Conversation.last_message_at >= last_week_start,
        Conversation.last_message_at < week_start
    ).count()

    # ── SIMPLIFIED: Son 7 günlük trend (14 gün yerine) ───────────────────
    trend = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        
        cnt = Conversation.query.filter(
            Conversation.workspace_id == workspace_id,
            Conversation.last_message_at >= day_start,
            Conversation.last_message_at <= day_end
        ).count()
        msg_cnt = Message.query.join(Conversation).filter(
            Conversation.workspace_id == workspace_id,
            Message.created_at >= day_start,
            Message.created_at <= day_end
        ).count()
        trend.append({
            'date': day.strftime('%d %b'),
            'conversations': cnt,
            'messages': msg_cnt
        })

    # ── SIMPLIFIED: Müşteri büyüme trendi (son 7 gün) ───────────────────────────
    customer_trend = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        cnt = Customer.query.filter(
            Customer.workspace_id == workspace_id,
            Customer.created_at >= day_start,
            Customer.created_at <= day_end
        ).count()
        customer_trend.append({'date': day.strftime('%d %b'), 'count': cnt})

    # ── SIMPLIFIED: Agent stats (sadece temel bilgiler) ───────────────────
    agents = User.query.filter_by(workspace_id=workspace_id).limit(10).all()  # Max 10 agent
    agent_stats = []
    for agent in agents:
        assigned_total = Conversation.query.filter_by(
            workspace_id=workspace_id, assigned_to=agent.id
        ).count()
        assigned_open = Conversation.query.filter_by(
            workspace_id=workspace_id, assigned_to=agent.id, status='open'
        ).count()
        agent_stats.append({
            'id': agent.id,
            'name': agent.name,
            'role': agent.role,
            'total': assigned_total,
            'open': assigned_open,
            'closed': assigned_total - assigned_open,
            'closed_this_week': 0  # Disabled for performance
        })

    # ── DISABLED: Tag distribution (çok yavaş, opsiyonel) ───────────────────
    tags_data = []

    return jsonify({
        'kpis': {
            'total_conversations': total_conv,
            'open_conversations': open_conv,
            'closed_conversations': closed_conv,
            'pending_conversations': pending_conv,
            'total_customers': total_cust,
            'total_messages': total_msg,
            'today_conversations': today_conv,
            'today_messages': today_msg,
            'this_week_conversations': this_week_conv,
            'last_week_conversations': last_week_conv,
        },
        'total_messages': total_msg,
        'new_customers': total_cust,
        'active_conversations': open_conv,
        'traffic': trend,  # Reuse trend data
        'trend': trend,
        'tag_distribution': tags_data,
        'agent_stats': agent_stats,
        'customer_trend': customer_trend
    }), 200


# ─── Debug / Demo Data Endpoint ───────────────────────────────────────────────

def _is_production():
    try:
        return current_app.config.get('ENV') == 'production' or not current_app.debug
    except Exception:
        return True

@bp.route('/debug/populate', methods=['POST'])
@login_required_api
def populate_demo_data():
    """Demo veri oluştur (sadece geliştirme ortamı)"""
    if _is_production():
        return jsonify({'error': 'Bu endpoint sadece geliştirme ortamında kullanılabilir'}), 403
    import random
    from datetime import timedelta
    workspace_id = session.get('workspace_id')

    demo_customers = [
        {'name': 'Ayşe Kaya', 'phone': '+905551234567'},
        {'name': 'Mehmet Yılmaz', 'phone': '+905559876543'},
        {'name': 'Fatma Demir', 'phone': '+905553334444'},
        {'name': 'Ahmet Çelik', 'phone': '+905557778888'},
        {'name': 'Zeynep Arslan', 'phone': '+905552221111'},
    ]
    tags_pool = ['yeni_siparis', 'kargo_sorunu', 'odeme_bekliyor', 'kargolandi', '']
    statuses = ['open', 'open', 'pending', 'resolved']
    messages_pool = [
        'Merhaba, siparişim hakkında bilgi almak istiyorum.',
        'Kargom nerede acaba?',
        'İade etmek istiyorum.',
        'Teşekkürler, harika hizmet!',
        'Ürün hasarlı geldi.',
        'Ne zaman teslim edilecek?',
        'Tamam, anladım. Teşekkürler.',
        'Lütfen hızlı çözüm bulun.',
    ]

    created = 0
    for demo in demo_customers:
        existing = Customer.query.filter_by(workspace_id=workspace_id, phone_number=demo['phone']).first()
        if existing:
            customer = existing
        else:
            customer = Customer(
                workspace_id=workspace_id,
                phone_number=demo['phone'],
                profile_name=demo['name'],
                created_at=datetime.utcnow() - timedelta(days=random.randint(1,60))
            )
            db.session.add(customer)
            db.session.flush()

        # Her müşteri için 1-3 konuşma
        for _ in range(random.randint(1, 3)):
            conv = Conversation(
                workspace_id=workspace_id,
                customer_id=customer.id,
                status=random.choice(statuses),
                tags=random.choice(tags_pool),
                last_message_at=datetime.utcnow() - timedelta(hours=random.randint(1, 72))
            )
            db.session.add(conv)
            db.session.flush()

            # Her konuşmaya 2-5 mesaj
            for i in range(random.randint(2, 5)):
                sender = 'customer' if i % 2 == 0 else 'agent'
                msg = Message(
                    conversation_id=conv.id,
                    sender_type=sender,
                    message_body=random.choice(messages_pool),
                    is_read=(sender == 'agent'),
                    created_at=datetime.utcnow() - timedelta(hours=random.randint(1,48))
                )
                db.session.add(msg)
            created += 1

    db.session.commit()
    return jsonify({'status': 'ok', 'conversations_created': created}), 200

@bp.route('/contacts', methods=['GET'])
@login_required_api
def get_contacts():
    """Get all contacts/customers for current workspace"""
    workspace_id = session.get('workspace_id')
    search = request.args.get('search', '').strip()
    
    query = Customer.query.filter_by(workspace_id=workspace_id)
    
    if search:
        query = query.filter(
            or_(
                Customer.profile_name.ilike(f'%{search}%'),
                Customer.phone_number.ilike(f'%{search}%'),
                Customer.email.ilike(f'%{search}%'),
                Customer.company.ilike(f'%{search}%'),
                Customer.job_title.ilike(f'%{search}%')
            )
        )
    
    customers = query.order_by(Customer.created_at.desc()).all()
    
    # Import CRM models
    from models_crm import Contact as CRMContact
    
    result = []
    for customer in customers:
        # Konuşma sayısı
        conversation_count = Conversation.query.filter_by(
            customer_id=customer.id,
            workspace_id=workspace_id
        ).count()
        
        # Açık konuşma var mı?
        has_open_conversation = Conversation.query.filter_by(
            customer_id=customer.id,
            workspace_id=workspace_id,
            status='open'
        ).first() is not None
        
        # Check if linked to CRM Contact
        crm_contact = None
        crm_contact_obj = CRMContact.query.filter_by(
            workspace_id=workspace_id,
            customer_id=customer.id
        ).first()
        
        if crm_contact_obj:
            crm_contact = {
                'id': crm_contact_obj.id,
                'full_name': crm_contact_obj.full_name,
                'role': crm_contact_obj.role,
                'job_title': crm_contact_obj.job_title,
                'lead_score': crm_contact_obj.lead_score,
                'company_name': crm_contact_obj.company.name if crm_contact_obj.company else None
            }
        
        result.append({
            'id': customer.id,
            'phone_number': customer.phone_number,
            'profile_name': customer.profile_name,
            'email': customer.email,
            'company': customer.company,
            'job_title': customer.job_title,
            'labels': customer.labels,
            'created_at': customer.created_at.isoformat(),
            'conversation_count': conversation_count,
            'has_open_conversation': has_open_conversation,
            'crm_contact': crm_contact
        })
    
    return jsonify({'contacts': result}), 200

@bp.route('/customers', methods=['POST'])
@login_required_api
def create_customer():
    """Yeni müşteri oluştur"""
    workspace_id = session.get('workspace_id')
    data = request.get_json()
    
    phone_number = data.get('phone_number', '').strip()
    profile_name = data.get('profile_name', '').strip()
    email = data.get('email', '').strip()
    company = data.get('company', '').strip()
    job_title = data.get('job_title', '').strip()
    labels = data.get('labels', '').strip()
    
    if not phone_number:
        return jsonify({'error': 'Telefon numarası zorunludur'}), 400
    
    # Aynı telefon numarası var mı kontrol et
    existing = Customer.query.filter_by(
        workspace_id=workspace_id,
        phone_number=phone_number
    ).first()
    
    if existing:
        return jsonify({'error': 'Bu telefon numarası zaten kayıtlı'}), 409
    
    try:
        customer = Customer(
            workspace_id=workspace_id,
            phone_number=phone_number,
            profile_name=profile_name if profile_name else None,
            email=email if email else None,
            company=company if company else None,
            job_title=job_title if job_title else None,
            labels=labels if labels else None
        )
        db.session.add(customer)
        db.session.commit()
        
        return jsonify({
            'status': 'created',
            'customer': {
                'id': customer.id,
                'phone_number': customer.phone_number,
                'profile_name': customer.profile_name,
                'email': customer.email
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Müşteri oluşturulamadı'}), 500

@bp.route('/customers/bulk-delete', methods=['POST'])
@login_required_api
def bulk_delete_customers():
    """Toplu müşteri silme"""
    workspace_id = session.get('workspace_id')
    data = request.get_json()
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({'error': 'ID listesi boş'}), 400
        
    try:
        # Workspace doğrulaması yaparak sil
        deleted_count = Customer.query.filter(
            Customer.id.in_(ids),
            Customer.workspace_id == workspace_id
        ).delete(synchronize_session=False)
        
        db.session.commit()
        return jsonify({'status': 'deleted', 'count': deleted_count}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/customers/<int:customer_id>', methods=['PATCH'])
@login_required_api
def patch_customer(customer_id):
    """Partial update customer"""
    workspace_id = session.get('workspace_id')
    customer = Customer.query.filter_by(id=customer_id, workspace_id=workspace_id).first()
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404
    
    data = request.get_json()
    if 'email' in data: customer.email = data['email']
    if 'company' in data: customer.company = data['company']
    if 'job_title' in data: customer.job_title = data['job_title']
    if 'labels' in data: customer.labels = data['labels']
    if 'profile_name' in data: customer.profile_name = data['profile_name']
    
    db.session.commit()
    return jsonify({'status': 'updated'}), 200

@bp.route('/customers/<int:customer_id>', methods=['DELETE'])
@login_required_api
def delete_customer(customer_id):
    """Delete customer and all related conversations and messages (via cascade)"""
    workspace_id = session.get('workspace_id')
    customer = Customer.query.filter_by(id=customer_id, workspace_id=workspace_id).first()
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404
    
    try:
        db.session.delete(customer)
        db.session.commit()
        return jsonify({'status': 'deleted'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/conversations/<int:conversation_id>/close', methods=['POST'])
@login_required_api
def close_conversation(conversation_id):
    """Konuşmayı kapat (status=resolved)"""
    workspace_id = session.get('workspace_id')
    conv = Conversation.query.filter_by(id=conversation_id, workspace_id=workspace_id).first()
    if not conv:
        return jsonify({'error': 'Conversation not found'}), 404
    
    conv.status = 'resolved'
    db.session.commit()
    return jsonify({'status': 'closed'}), 200

@bp.route('/conversations/<int:conversation_id>/tag', methods=['PUT'])
@login_required_api
def update_conversation_tag(conversation_id):
    """Konuşma etiketini güncelle (eski endpoint uyumluluğu için)"""
    workspace_id = session.get('workspace_id')
    conv = Conversation.query.filter_by(id=conversation_id, workspace_id=workspace_id).first()
    if not conv:
        return jsonify({'error': 'Conversation not found'}), 404
    
    data = request.get_json()
    conv.tags = data.get('tag', '')
    db.session.commit()
    return jsonify({'status': 'updated'}), 200

@bp.route('/me', methods=['GET'])
@login_required_api
def get_current_user():
    """Giriş yapmış kullanıcının bilgilerini döndür"""
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'role': user.role
    }), 200
