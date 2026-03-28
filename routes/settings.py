from flask import Blueprint, request, jsonify, session, current_app
from models import db, Workspace, User, MessageTemplate
from models_crm import PortalBranding, AuditLog, WorkspacePreference
from services.auth_manager import AuthManager
from services.audit_service import AuditService
from services.security_service import SecurityService
from services.telegram_service import TelegramService
import re
from datetime import datetime
import os

bp = Blueprint('settings', __name__, url_prefix='/api/settings')

DEFAULT_PORTAL_BRANDING = {
    'logo_url': '',
    'primary_color': '#7c3aed',
    'secondary_color': '#8b5cf6',
    'custom_domain': '',
    'custom_css': '',
}


def _normalize_hex_color(value, fallback):
    raw = (value or '').strip().lower()
    if re.fullmatch(r'#[0-9a-f]{6}', raw):
        return raw
    return fallback


def _serialize_portal_branding(row):
    if not row:
        return dict(DEFAULT_PORTAL_BRANDING)

    return {
        'logo_url': row.logo_url or '',
        'primary_color': _normalize_hex_color(row.primary_color, DEFAULT_PORTAL_BRANDING['primary_color']),
        'secondary_color': _normalize_hex_color(row.secondary_color, DEFAULT_PORTAL_BRANDING['secondary_color']),
        'custom_domain': row.custom_domain or '',
        'custom_css': row.custom_css or '',
    }

def login_required_api(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id') or not session.get('workspace_id'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('user_role') != 'admin':
            return jsonify({'error': 'Admin yetkisi gereklidir'}), 403
        return f(*args, **kwargs)
    return decorated


def security_manage_required(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        if not workspace_id or not user_id:
            return jsonify({'error': 'Unauthorized'}), 401

        if session.get('user_role') == 'admin':
            return f(*args, **kwargs)

        permissions = SecurityService.get_user_permissions(workspace_id, user_id)
        if 'security.manage' not in permissions:
            return jsonify({'error': 'Security yetkisi gereklidir'}), 403
        return f(*args, **kwargs)

    return decorated


def _initials(name):
    parts = [p for p in (name or '').strip().split(' ') if p]
    if not parts:
        return 'U'
    if len(parts) == 1:
        return parts[0][:1].upper()
    return f"{parts[0][:1]}{parts[-1][:1]}".upper()


def _safe_iso(dt):
    if not dt:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return None


def _topbar_recent_items(workspace_id, limit=8):
    """Build mixed recent items list for topbar search dropdown."""
    from models_crm import Contact, Company, Deal, Task, Document

    items = []

    contacts = Contact.query.filter_by(workspace_id=workspace_id) \
        .order_by(Contact.updated_at.desc(), Contact.created_at.desc()) \
        .limit(4).all()
    for c in contacts:
        items.append({
            'type': 'contact',
            'title': c.full_name,
            'subtitle': c.email or c.phone or 'Kisi',
            'url': f'/contacts/{c.id}',
            'icon': 'fa-user',
            'timestamp': _safe_iso(c.updated_at or c.created_at),
        })

    documents = Document.query.filter_by(workspace_id=workspace_id) \
        .order_by(Document.created_at.desc()) \
        .limit(2).all()
    for d in documents:
        items.append({
            'type': 'document',
            'title': d.name,
            'subtitle': 'Dokuman',
            'url': '/documents',
            'icon': 'fa-file-image',
            'timestamp': _safe_iso(d.created_at),
        })

    # Include recent uploaded contact files from filesystem uploads/contacts/{contact_id}
    uploads_root = os.path.join('uploads', 'contacts')
    if os.path.isdir(uploads_root):
        # OPTIMIZED: Only get contact IDs that have files, then fetch names
        contact_dirs = []
        try:
            for item in os.listdir(uploads_root):
                item_path = os.path.join(uploads_root, item)
                if os.path.isdir(item_path) and item.isdigit():
                    contact_dirs.append(int(item))
        except Exception:
            pass
        
        contact_names = {}
        if contact_dirs:
            contacts_with_files = Contact.query.filter(
                Contact.id.in_(contact_dirs),
                Contact.workspace_id == workspace_id
            ).with_entities(Contact.id, Contact.first_name, Contact.last_name).all()
            contact_names = {
                c.id: f"{c.first_name} {c.last_name}".strip() 
                for c in contacts_with_files
            }
        
        file_items = []
        for contact_id in contact_names.keys():
            contact_dir = os.path.join(uploads_root, str(contact_id))
            if not os.path.isdir(contact_dir):
                continue
            try:
                for filename in os.listdir(contact_dir):
                    full_path = os.path.join(contact_dir, filename)
                    if not os.path.isfile(full_path):
                        continue
                    display_name = filename.split('_', 1)[1] if '_' in filename else filename
                    mtime = datetime.utcfromtimestamp(os.path.getmtime(full_path)).isoformat()
                    file_items.append({
                        'type': 'contact_file',
                        'title': display_name,
                        'subtitle': f"Dosya • {contact_names.get(contact_id, 'Kisi')}",
                        'url': f'/contacts/{contact_id}?tab=files',
                        'icon': 'fa-file',
                        'timestamp': mtime,
                    })
            except Exception:
                continue

        file_items.sort(key=lambda i: i.get('timestamp') or '', reverse=True)
        items.extend(file_items[:2])

    deals = Deal.query.options(db.joinedload(Deal.company)).filter_by(workspace_id=workspace_id) \
        .order_by(Deal.updated_at.desc(), Deal.created_at.desc()) \
        .limit(2).all()
    for deal in deals:
        company_name = deal.company.name if deal.company else None
        value = float(deal.value) if deal.value is not None else 0
        subtitle = f"{value:,.0f} tl"
        if company_name:
            subtitle = f"{subtitle} • {company_name}"
        items.append({
            'type': 'deal',
            'title': deal.name,
            'subtitle': subtitle,
            'url': '/pipeline',
            'icon': 'fa-circle-dollar-to-slot',
            'timestamp': _safe_iso(deal.updated_at or deal.created_at),
        })

    tasks = Task.query.filter_by(workspace_id=workspace_id) \
        .order_by(Task.updated_at.desc(), Task.created_at.desc()) \
        .limit(2).all()
    for task in tasks:
        items.append({
            'type': 'task',
            'title': task.title,
            'subtitle': task.status or 'Gorev',
            'url': '/tasks',
            'icon': 'fa-paperclip',
            'timestamp': _safe_iso(task.updated_at or task.created_at),
        })

    items.sort(key=lambda i: i.get('timestamp') or '', reverse=True)
    return items[:limit]


def _topbar_search(workspace_id, query, limit=12):
    """Search across core CRM entities for topbar search."""
    from models_crm import Contact, Company, Deal, Task, Document

    q = (query or '').strip()
    if not q:
        return []

    like = f"%{q}%"
    results = []

    contacts = Contact.query.filter(
        Contact.workspace_id == workspace_id,
        db.or_(
            Contact.first_name.ilike(like),
            Contact.last_name.ilike(like),
            Contact.email.ilike(like),
            Contact.phone.ilike(like),
        )
    ).order_by(Contact.updated_at.desc(), Contact.created_at.desc()).limit(5).all()
    for c in contacts:
        results.append({
            'type': 'contact',
            'title': c.full_name,
            'subtitle': c.email or c.phone or 'Kisi',
            'url': f'/contacts/{c.id}',
            'icon': 'fa-user',
            'timestamp': _safe_iso(c.updated_at or c.created_at),
        })

    companies = Company.query.filter(
        Company.workspace_id == workspace_id,
        db.or_(
            Company.name.ilike(like),
            Company.website.ilike(like),
            Company.phone.ilike(like),
        )
    ).order_by(Company.updated_at.desc(), Company.created_at.desc()).limit(3).all()
    for c in companies:
        results.append({
            'type': 'company',
            'title': c.name,
            'subtitle': c.industry or c.website or 'Sirket',
            'url': '/companies',
            'icon': 'fa-building',
            'timestamp': _safe_iso(c.updated_at or c.created_at),
        })

    documents = Document.query.filter(
        Document.workspace_id == workspace_id,
        Document.name.ilike(like)
    ).order_by(Document.created_at.desc()).limit(2).all()
    for d in documents:
        results.append({
            'type': 'document',
            'title': d.name,
            'subtitle': 'Dokuman',
            'url': '/documents',
            'icon': 'fa-file-image',
            'timestamp': _safe_iso(d.created_at),
        })

    # Search uploaded contact files from filesystem uploads/contacts/{contact_id}
    uploads_root = os.path.join('uploads', 'contacts')
    if os.path.isdir(uploads_root):
        # OPTIMIZED: Only get contact IDs that have files, then fetch names
        contact_dirs = []
        try:
            for item in os.listdir(uploads_root):
                item_path = os.path.join(uploads_root, item)
                if os.path.isdir(item_path) and item.isdigit():
                    contact_dirs.append(int(item))
        except Exception:
            pass
        
        contact_names = {}
        if contact_dirs:
            contacts_with_files = Contact.query.filter(
                Contact.id.in_(contact_dirs),
                Contact.workspace_id == workspace_id
            ).with_entities(Contact.id, Contact.first_name, Contact.last_name).all()
            contact_names = {
                c.id: f"{c.first_name} {c.last_name}".strip() 
                for c in contacts_with_files
            }

        file_hits = []
        q_lower = q.lower()
        for contact_id in contact_names.keys():
            contact_dir = os.path.join(uploads_root, str(contact_id))
            if not os.path.isdir(contact_dir):
                continue
            try:
                for filename in os.listdir(contact_dir):
                    full_path = os.path.join(contact_dir, filename)
                    if not os.path.isfile(full_path):
                        continue
                    display_name = filename.split('_', 1)[1] if '_' in filename else filename
                    if q_lower not in display_name.lower():
                        continue
                    mtime = datetime.utcfromtimestamp(os.path.getmtime(full_path)).isoformat()
                    file_hits.append({
                        'type': 'contact_file',
                        'title': display_name,
                        'subtitle': f"Dosya • {contact_names.get(contact_id, 'Kisi')}",
                        'url': f'/contacts/{contact_id}?tab=files',
                        'icon': 'fa-file',
                        'timestamp': mtime,
                    })
            except Exception:
                continue

        file_hits.sort(key=lambda i: i.get('timestamp') or '', reverse=True)
        results.extend(file_hits[:4])

    deals = Deal.query.options(db.joinedload(Deal.company)).filter(
        Deal.workspace_id == workspace_id,
        Deal.name.ilike(like)
    ).order_by(Deal.updated_at.desc(), Deal.created_at.desc()).limit(3).all()
    for deal in deals:
        company_name = deal.company.name if deal.company else None
        value = float(deal.value) if deal.value is not None else 0
        subtitle = f"{value:,.0f} tl"
        if company_name:
            subtitle = f"{subtitle} • {company_name}"
        results.append({
            'type': 'deal',
            'title': deal.name,
            'subtitle': subtitle,
            'url': '/pipeline',
            'icon': 'fa-circle-dollar-to-slot',
            'timestamp': _safe_iso(deal.updated_at or deal.created_at),
        })

    tasks = Task.query.filter(
        Task.workspace_id == workspace_id,
        db.or_(
            Task.title.ilike(like),
            Task.description.ilike(like),
        )
    ).order_by(Task.updated_at.desc(), Task.created_at.desc()).limit(3).all()
    for task in tasks:
        results.append({
            'type': 'task',
            'title': task.title,
            'subtitle': task.status or 'Gorev',
            'url': '/tasks',
            'icon': 'fa-paperclip',
            'timestamp': _safe_iso(task.updated_at or task.created_at),
        })

    results.sort(key=lambda i: i.get('timestamp') or '', reverse=True)
    return results[:limit]

# ─── Workspace Genel Bilgi ──────────────────────────────────────────────────

@bp.route('/workspace', methods=['GET'])
@login_required_api
def get_workspace():
    """Mevcut workspace bilgilerini döndür"""
    workspace_id = session.get('workspace_id')
    ws = Workspace.query.get_or_404(workspace_id)
    return jsonify({
        'id': ws.id,
        'company_name': ws.company_name,
        'whatsapp_phone_number_id': ws.whatsapp_phone_number_id or '',
        'whatsapp_access_token': '***' if ws.whatsapp_access_token else '',
        'telegram_bot_token': '***' if ws.telegram_bot_token else '',
        'waba_id': ws.waba_id or '',
        'created_at': ws.created_at.isoformat()
    }), 200

@bp.route('/workspace', methods=['PUT'])
@login_required_api
@admin_required
def update_workspace():
    """Workspace bilgilerini güncelle (şirket adı + WhatsApp API credentials)"""
    workspace_id = session.get('workspace_id')
    ws = Workspace.query.get_or_404(workspace_id)
    data = request.get_json()

    if 'company_name' in data and data['company_name'].strip():
        ws.company_name = data['company_name'].strip()

    if 'whatsapp_phone_number_id' in data:
        ws.whatsapp_phone_number_id = data['whatsapp_phone_number_id'].strip() or None

    if 'whatsapp_access_token' in data and data['whatsapp_access_token'] != '***':
        ws.whatsapp_access_token = data['whatsapp_access_token'].strip() or None

    if 'telegram_bot_token' in data and data['telegram_bot_token'] != '***':
        ws.telegram_bot_token = data['telegram_bot_token'].strip() or None

    if 'waba_id' in data:
        ws.waba_id = data['waba_id'].strip() or None

    db.session.commit()
    return jsonify({'status': 'updated', 'company_name': ws.company_name}), 200


@bp.route('/telegram/status', methods=['GET'])
@login_required_api
def get_telegram_status():
    workspace_id = session.get('workspace_id')
    ws = Workspace.query.get_or_404(workspace_id)
    return jsonify({
        'connected': bool(ws.telegram_bot_token),
        'has_token': bool(ws.telegram_bot_token),
    }), 200


@bp.route('/telegram/config', methods=['PUT'])
@login_required_api
@admin_required
def save_telegram_config():
    workspace_id = session.get('workspace_id')
    ws = Workspace.query.get_or_404(workspace_id)
    data = request.get_json(silent=True) or {}
    token = (data.get('telegram_bot_token') or '').strip()
    ws.telegram_bot_token = token or None
    db.session.commit()
    return jsonify({'status': 'updated', 'connected': bool(ws.telegram_bot_token)}), 200


@bp.route('/telegram/set-webhook', methods=['POST'])
@login_required_api
@admin_required
def set_telegram_webhook():
    workspace_id = session.get('workspace_id')
    ws = Workspace.query.get_or_404(workspace_id)
    if not ws.telegram_bot_token:
        return jsonify({'error': 'Telegram Bot Token gerekli'}), 400

    payload = request.get_json(silent=True) or {}
    base_url = (payload.get('base_url') or request.url_root.rstrip('/')).rstrip('/')
    webhook_url = f"{base_url}/api/v1/webhooks/telegram?workspace_id={workspace_id}"
    secret_token = f'tg_ws_{workspace_id}'

    service = TelegramService(ws.telegram_bot_token)
    result = service.set_webhook(webhook_url, secret_token=secret_token)
    if not result.get('success'):
        return jsonify({'error': result.get('error', 'Webhook kurulamadı')}), 500

    return jsonify({
        'status': 'ok',
        'webhook_url': webhook_url,
    }), 200

@bp.route('/workspace/test-whatsapp', methods=['POST'])
@login_required_api
@admin_required
def test_whatsapp_connection():
    """WhatsApp API bağlantısını test et"""
    workspace_id = session.get('workspace_id')
    ws = Workspace.query.get_or_404(workspace_id)
    
    if not ws.whatsapp_phone_number_id or not ws.whatsapp_access_token:
        return jsonify({'success': False, 'error': 'Eksik yapılandırma (Phone Number ID veya Access Token yok)'}), 400
        
    import requests
    from config import Config
    
    url = f"{Config.META_API_BASE_URL}/{ws.whatsapp_phone_number_id}"
    headers = {'Authorization': f'Bearer {ws.whatsapp_access_token}'}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.ok:
            data = response.json()
            return jsonify({
                'success': True,
                'data': {
                    'verified_name': data.get('verified_name'),
                    'display_phone_number': data.get('display_phone_number'),
                    'quality_rating': data.get('quality_rating')
                }
            }), 200
        else:
            error_data = response.json().get('error', {})
            return jsonify({
                'success': False,
                'error': error_data.get('message', 'Bilinmeyen Meta API hatası')
            }), response.status_code
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/workspace/preferences', methods=['GET'])
@login_required_api
def get_workspace_preferences():
    """Workspace UI preference values used by frontend feature toggles."""
    workspace_id = session.get('workspace_id')
    pref = WorkspacePreference.query.filter_by(workspace_id=workspace_id).first()

    return jsonify({
        'show_dashboard_insights': bool(pref.show_dashboard_insights) if pref else False,
    }), 200


@bp.route('/workspace/preferences', methods=['PUT'])
@login_required_api
@admin_required
def update_workspace_preferences():
    """Update workspace-level UI preferences."""
    workspace_id = session.get('workspace_id')
    data = request.get_json(silent=True) or {}

    pref = WorkspacePreference.query.filter_by(workspace_id=workspace_id).first()
    if not pref:
        pref = WorkspacePreference(workspace_id=workspace_id)
        db.session.add(pref)

    if 'show_dashboard_insights' in data:
        pref.show_dashboard_insights = bool(data.get('show_dashboard_insights'))

    db.session.commit()
    return jsonify({
        'status': 'updated',
        'show_dashboard_insights': bool(pref.show_dashboard_insights),
    }), 200


@bp.route('/topbar', methods=['GET'])
@login_required_api
def get_topbar_config():
    """Return topbar/profile metadata used by modern list pages."""
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')

    ws = Workspace.query.get_or_404(workspace_id)
    user = User.query.get_or_404(user_id)

    return jsonify({
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role,
            'initials': _initials(user.name),
        },
        'workspace': {
            'id': ws.id,
            'company_name': ws.company_name,
        },
        'search_placeholder': "CRM'de ara",
        'account_menu': [
            {'group': 'HESABIM', 'label': 'Kisisel tercihler', 'icon': 'fa-user-circle', 'url': '/account'},
            {'group': 'HESABIM', 'label': 'Tavsiye programi', 'icon': 'fa-gift', 'url': '/settings'},
            {'group': 'SIRKET HAKKINDA GENEL BILGILER', 'label': 'Sirket ayarlari', 'icon': 'fa-cog', 'url': '/settings'},
            {'group': 'SIRKET HAKKINDA GENEL BILGILER', 'label': 'Kullanicilari yonet', 'icon': 'fa-users', 'url': '/settings'},
            {'group': 'SIRKET HAKKINDA GENEL BILGILER', 'label': 'Faturalama', 'icon': 'fa-receipt', 'url': '/settings'},
            {'group': 'SIRKET HAKKINDA GENEL BILGILER', 'label': 'Araclar ve uygulamalar', 'icon': 'fa-th', 'url': '/channels'},
            {'group': 'SESSION', 'label': 'Cikis', 'icon': 'fa-sign-out-alt', 'url': '/logout'},
        ],
    }), 200


@bp.route('/topbar/recent', methods=['GET'])
@login_required_api
def get_topbar_recent():
    workspace_id = session.get('workspace_id')
    limit = min(max(request.args.get('limit', 8, type=int), 1), 20)
    return jsonify({
        'items': _topbar_recent_items(workspace_id, limit=limit),
    }), 200


@bp.route('/topbar/search', methods=['GET'])
@login_required_api
def search_topbar():
    workspace_id = session.get('workspace_id')
    q = (request.args.get('q') or '').strip()

    if len(q) < 2:
        return jsonify({
            'query': q,
            'items': _topbar_recent_items(workspace_id, limit=8),
            'mode': 'recent',
        }), 200

    return jsonify({
        'query': q,
        'items': _topbar_search(workspace_id, q, limit=12),
        'mode': 'search',
    }), 200


@bp.route('/portal-branding', methods=['GET'])
@login_required_api
def get_portal_branding():
    """Get workspace portal branding configuration"""
    workspace_id = session.get('workspace_id')
    branding = PortalBranding.query.filter_by(workspace_id=workspace_id).first()

    payload = _serialize_portal_branding(branding)
    payload['workspace_id'] = workspace_id
    return jsonify(payload), 200


@bp.route('/portal-branding', methods=['PUT'])
@login_required_api
@admin_required
def update_portal_branding():
    """Update white-label branding settings for customer portal"""
    workspace_id = session.get('workspace_id')
    data = request.get_json(silent=True) or {}

    branding = PortalBranding.query.filter_by(workspace_id=workspace_id).first()
    if not branding:
        branding = PortalBranding(workspace_id=workspace_id)
        db.session.add(branding)

    branding.logo_url = (data.get('logo_url') or '').strip() or None
    branding.primary_color = _normalize_hex_color(
        data.get('primary_color'),
        DEFAULT_PORTAL_BRANDING['primary_color']
    )
    branding.secondary_color = _normalize_hex_color(
        data.get('secondary_color'),
        DEFAULT_PORTAL_BRANDING['secondary_color']
    )

    custom_domain = (data.get('custom_domain') or '').strip().lower()
    if custom_domain and not re.fullmatch(r'[a-z0-9.-]+', custom_domain):
        return jsonify({'error': 'Geçersiz domain formatı'}), 400
    branding.custom_domain = custom_domain or None

    custom_css = data.get('custom_css')
    branding.custom_css = custom_css.strip() if isinstance(custom_css, str) else None

    db.session.commit()

    payload = _serialize_portal_branding(branding)
    payload['workspace_id'] = workspace_id
    return jsonify(payload), 200

# ─── Takım Üyesi Yönetimi ───────────────────────────────────────────────────

@bp.route('/team', methods=['GET'])
@login_required_api
def get_team():
    """Workspace'teki tüm kullanıcıları listele"""
    workspace_id = session.get('workspace_id')
    users = User.query.filter_by(workspace_id=workspace_id).with_entities(
        User.id, User.name, User.email, User.role
    ).all()
    return jsonify([{
        'id': u.id,
        'name': u.name,
        'email': u.email,
        'role': u.role
    } for u in users]), 200

@bp.route('/team', methods=['POST'])
@login_required_api
@admin_required
def invite_team_member():
    """Yeni takım üyesi ekle (admin yetkisi gerekir)"""
    workspace_id = session.get('workspace_id')
    data = request.get_json()

    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', 'agent')

    if not all([name, email, password]):
        return jsonify({'error': 'Ad, email ve şifre zorunludur'}), 400

    if role not in ['admin', 'agent']:
        return jsonify({'error': 'Geçersiz rol'}), 400

    if len(password) < 8:
        return jsonify({'error': 'Şifre en az 8 karakter olmalıdır'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Bu email zaten kullanımda'}), 409

    user = User(
        workspace_id=workspace_id,
        name=name,
        email=email,
        password_hash=AuthManager.hash_password(password),
        role=role
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({
        'status': 'created',
        'user': {'id': user.id, 'name': user.name, 'email': user.email, 'role': user.role}
    }), 201

@bp.route('/team/<int:user_id>', methods=['PUT'])
@login_required_api
@admin_required
def update_team_member(user_id):
    """Takım üyesinin rolünü güncelle"""
    workspace_id = session.get('workspace_id')
    user = User.query.filter_by(id=user_id, workspace_id=workspace_id).first_or_404()

    if user.id == session.get('user_id'):
        return jsonify({'error': 'Kendi rolünüzü değiştiremezsiniz'}), 400

    data = request.get_json()
    role = data.get('role')
    if role not in ['admin', 'agent']:
        return jsonify({'error': 'Geçersiz rol'}), 400

    user.role = role
    db.session.commit()
    return jsonify({'status': 'updated'}), 200

@bp.route('/team/<int:user_id>', methods=['DELETE'])
@login_required_api
@admin_required
def remove_team_member(user_id):
    """Takım üyesini workspace'ten çıkar"""
    workspace_id = session.get('workspace_id')
    user = User.query.filter_by(id=user_id, workspace_id=workspace_id).first_or_404()

    if user.id == session.get('user_id'):
        return jsonify({'error': 'Kendinizi silemezsiniz'}), 400

    db.session.delete(user)
    db.session.commit()
    return jsonify({'status': 'deleted'}), 200

# ─── Şablonlu Mesajlar ──────────────────────────────────────────────────────

@bp.route('/templates', methods=['GET'])
@login_required_api
def get_templates():
    """Workspace şablonlarını listele"""
    workspace_id = session.get('workspace_id')
    templates = MessageTemplate.query.filter_by(workspace_id=workspace_id).order_by(MessageTemplate.created_at.desc()).all()
    return jsonify([{
        'id': t.id,
        'name': t.name,
        'body': t.body,
        'category': t.category,
        'language': t.language,
        'created_at': t.created_at.isoformat()
    } for t in templates]), 200

@bp.route('/templates', methods=['POST'])
@login_required_api
def create_template():
    """Yeni şablon oluştur"""
    workspace_id = session.get('workspace_id')
    data = request.get_json()

    name = data.get('name', '').strip()
    body = data.get('body', '').strip()
    category = data.get('category', 'custom')
    language = data.get('language', 'tr')

    if not name or not body:
        return jsonify({'error': 'Şablon adı ve içeriği zorunludur'}), 400

    template = MessageTemplate(
        workspace_id=workspace_id,
        name=name,
        body=body,
        category=category,
        language=language,
        created_by=session.get('user_id')
    )
    db.session.add(template)
    db.session.commit()

    return jsonify({
        'id': template.id,
        'name': template.name,
        'body': template.body,
        'category': template.category
    }), 201

@bp.route('/templates/<int:template_id>', methods=['PUT'])
@login_required_api
def update_template(template_id):
    """Şablonu güncelle"""
    workspace_id = session.get('workspace_id')
    template = MessageTemplate.query.filter_by(id=template_id, workspace_id=workspace_id).first_or_404()
    data = request.get_json()

    if 'name' in data: template.name = data['name'].strip()
    if 'body' in data: template.body = data['body'].strip()
    if 'category' in data: template.category = data['category']

    db.session.commit()
    return jsonify({'status': 'updated'}), 200

@bp.route('/templates/<int:template_id>', methods=['DELETE'])
@login_required_api
def delete_template(template_id):
    """Şablonu sil"""
    workspace_id = session.get('workspace_id')
    template = MessageTemplate.query.filter_by(id=template_id, workspace_id=workspace_id).first_or_404()
    db.session.delete(template)
    db.session.commit()
    return jsonify({'status': 'deleted'}), 200

# ─── Profil Ayarları ────────────────────────────────────────────────────────

@bp.route('/profile', methods=['GET'])
@login_required_api
def get_profile():
    """Mevcut kullanıcının profil bilgilerini döndür"""
    user_id = session.get('user_id')
    user = User.query.get_or_404(user_id)
    return jsonify({
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'role': user.role
    }), 200

@bp.route('/profile', methods=['PUT'])
@login_required_api
def update_profile():
    """Profil bilgilerini güncelle (ad soyad)"""
    user_id = session.get('user_id')
    user = User.query.get_or_404(user_id)
    data = request.get_json()

    if 'name' in data and data['name'].strip():
        user.name = data['name'].strip()
        db.session.commit()
        
        # Mark onboarding step as complete
        from services.onboarding_service import OnboardingService
        workspace_id = session.get('workspace_id')
        OnboardingService.complete_step(workspace_id, 'profile_setup')
        
        # Session'daki name'i de güncellemek gerekebilir (opsiyonel)
        return jsonify({'status': 'updated', 'name': user.name}), 200
    
    return jsonify({'error': 'Geçersiz veri'}), 400

@bp.route('/profile/password', methods=['PUT'])
@login_required_api
def change_password():
    """Şifre değiştir"""
    user_id = session.get('user_id')
    user = User.query.get_or_404(user_id)
    data = request.get_json()

    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return jsonify({'error': 'Mevcut ve yeni şifre gereklidir'}), 400

    if not AuthManager.verify_password(user.password_hash, current_password):
        return jsonify({'error': 'Mevcut şifre hatalı'}), 400

    if len(new_password) < 8:
        return jsonify({'error': 'Yeni şifre en az 8 karakter olmalıdır'}), 400

    user.password_hash = AuthManager.hash_password(new_password)
    db.session.commit()

    return jsonify({'status': 'updated'}), 200


# ─── Security & Compliance (Phase 9) ───────────────────────────────────────

@bp.route('/security/overview', methods=['GET'])
@login_required_api
def get_security_overview():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    SecurityService.ensure_rbac_seed(workspace_id)
    return jsonify({
        'permissions': list(SecurityService.get_user_permissions(workspace_id, user_id)),
        'two_factor_enabled': SecurityService.get_2fa_status(user_id),
        'ip_whitelist_count': len(SecurityService.list_ip_whitelist(workspace_id)),
    }), 200


@bp.route('/security/roles', methods=['GET'])
@login_required_api
@security_manage_required
def get_security_roles():
    workspace_id = session.get('workspace_id')
    SecurityService.ensure_rbac_seed(workspace_id)
    return jsonify({'roles': SecurityService.list_roles(workspace_id)}), 200


@bp.route('/security/users/<int:user_id>/role', methods=['PUT'])
@login_required_api
@security_manage_required
@AuditService.audited('security.role.assign', 'user')
def assign_security_role(user_id):
    workspace_id = session.get('workspace_id')
    data = request.get_json(silent=True) or {}
    role_name = (data.get('role_name') or '').strip()
    if not role_name:
        return jsonify({'error': 'role_name zorunludur'}), 400

    user = User.query.filter_by(id=user_id, workspace_id=workspace_id).first()
    if not user:
        return jsonify({'error': 'Kullanıcı bulunamadı'}), 404

    try:
        SecurityService.ensure_rbac_seed(workspace_id)
        SecurityService.assign_role(workspace_id, user_id, role_name)
        return jsonify({'status': 'updated'}), 200
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 404
    except Exception:
        return jsonify({'error': 'Rol atama başarısız'}), 500


@bp.route('/security/2fa/status', methods=['GET'])
@login_required_api
def get_two_factor_status():
    return jsonify({'enabled': SecurityService.get_2fa_status(session.get('user_id'))}), 200


@bp.route('/security/2fa/setup', methods=['POST'])
@login_required_api
@AuditService.audited('security.2fa.setup', 'user')
def setup_two_factor():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    email = session.get('user_email')
    data = SecurityService.setup_2fa(workspace_id, user_id, email)
    return jsonify(data), 200


@bp.route('/security/2fa/enable', methods=['POST'])
@login_required_api
@AuditService.audited('security.2fa.enable', 'user')
def enable_two_factor():
    data = request.get_json(silent=True) or {}
    token = (data.get('token') or '').strip()
    if not token:
        return jsonify({'error': 'token zorunludur'}), 400

    ok = SecurityService.verify_and_enable_2fa(session.get('user_id'), token)
    if not ok:
        return jsonify({'error': 'Kod doğrulanamadı'}), 400
    return jsonify({'status': 'enabled'}), 200


@bp.route('/security/2fa/disable', methods=['POST'])
@login_required_api
@AuditService.audited('security.2fa.disable', 'user')
def disable_two_factor():
    SecurityService.disable_2fa(session.get('user_id'))
    return jsonify({'status': 'disabled'}), 200


@bp.route('/security/ip-whitelist', methods=['GET'])
@login_required_api
@security_manage_required
def get_ip_whitelist():
    workspace_id = session.get('workspace_id')
    return jsonify({'items': SecurityService.list_ip_whitelist(workspace_id)}), 200


@bp.route('/security/ip-whitelist', methods=['POST'])
@login_required_api
@security_manage_required
@AuditService.audited('security.ip_whitelist.add', 'workspace')
def add_ip_whitelist():
    workspace_id = session.get('workspace_id')
    data = request.get_json(silent=True) or {}
    ip_address = (data.get('ip_address') or '').strip()
    label = (data.get('label') or '').strip()
    if not ip_address:
        return jsonify({'error': 'ip_address zorunludur'}), 400
    try:
        row = SecurityService.add_ip_whitelist(workspace_id, ip_address, label, session.get('user_id'))
        return jsonify({'id': row.id}), 201
    except Exception:
        return jsonify({'error': 'IP kaydedilemedi'}), 400


@bp.route('/security/ip-whitelist/<int:row_id>', methods=['DELETE'])
@login_required_api
@security_manage_required
@AuditService.audited('security.ip_whitelist.delete', 'workspace')
def delete_ip_whitelist(row_id):
    workspace_id = session.get('workspace_id')
    if not SecurityService.delete_ip_whitelist(workspace_id, row_id):
        return jsonify({'error': 'Kayıt bulunamadı'}), 404
    return jsonify({'status': 'deleted'}), 200


@bp.route('/security/compliance-report', methods=['GET'])
@login_required_api
@security_manage_required
def get_compliance_report():
    workspace_id = session.get('workspace_id')
    days = request.args.get('days', default=30, type=int)
    days = max(1, min(days, 365))
    return jsonify(SecurityService.get_compliance_report(workspace_id, days=days)), 200


@bp.route('/security/gdpr/export', methods=['POST'])
@login_required_api
@security_manage_required
@AuditService.audited('security.gdpr.export', 'user')
def gdpr_export():
    workspace_id = session.get('workspace_id')
    data = request.get_json(silent=True) or {}
    target_user_id = data.get('target_user_id') or session.get('user_id')
    req = SecurityService.create_gdpr_export(workspace_id, session.get('user_id'), target_user_id)
    return jsonify({
        'id': req.id,
        'status': req.status,
        'result_json': req.result_json,
    }), 200


@bp.route('/security/gdpr/delete', methods=['POST'])
@login_required_api
@security_manage_required
@AuditService.audited('security.gdpr.delete', 'user')
def gdpr_delete():
    workspace_id = session.get('workspace_id')
    data = request.get_json(silent=True) or {}
    target_user_id = data.get('target_user_id')
    if not target_user_id:
        return jsonify({'error': 'target_user_id zorunludur'}), 400
    req = SecurityService.create_gdpr_delete(workspace_id, session.get('user_id'), target_user_id)
    return jsonify({'id': req.id, 'status': req.status}), 200


@bp.route('/security/audit-logs', methods=['GET'])
@login_required_api
@security_manage_required
def get_audit_logs():
    workspace_id = session.get('workspace_id')
    limit = request.args.get('limit', default=100, type=int)
    limit = max(1, min(limit, 500))
    logs = AuditLog.query.filter_by(workspace_id=workspace_id).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return jsonify({
        'items': [
            {
                'id': row.id,
                'user_id': row.user_id,
                'action': row.action,
                'entity_type': row.entity_type,
                'entity_id': row.entity_id,
                'ip_address': row.ip_address,
                'created_at': row.created_at.isoformat() if row.created_at else None,
            }
            for row in logs
        ]
    }), 200


# ─── AI Settings (per-workspace API keys) ─────────────────────────────────

def _ai_fernet():
    """Create Fernet instance for AI key encryption using app SECRET_KEY."""
    import hashlib, base64
    from cryptography.fernet import Fernet
    from config import Config
    key_material = Config.SECRET_KEY.encode('utf-8')
    digest = hashlib.sha256(key_material).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _ai_encrypt(value):
    if not value:
        return None
    return _ai_fernet().encrypt(value.encode('utf-8')).decode('utf-8')


def _ai_decrypt(value):
    if not value:
        return None
    try:
        return _ai_fernet().decrypt(value.encode('utf-8')).decode('utf-8')
    except Exception:
        return None


def _mask_key(key):
    """Mask API key for safe display: sk-abc...xyz"""
    if not key:
        return ''
    if len(key) <= 8:
        return key[:2] + '***'
    return key[:6] + '***' + key[-4:]


@bp.route('/ai', methods=['GET'])
@login_required_api
def get_ai_settings():
    """Get AI provider settings for current workspace (keys masked)."""
    from models_crm import AISettings
    workspace_id = session.get('workspace_id')

    rows = AISettings.query.filter_by(workspace_id=workspace_id).all()
    providers = []
    for row in rows:
        decrypted = _ai_decrypt(row.api_key_encrypted)
        providers.append({
            'provider': row.provider,
            'api_key_masked': _mask_key(decrypted),
            'has_key': bool(decrypted),
            'model_name': row.model_name or '',
            'is_active': row.is_active,
        })

    return jsonify({'providers': providers}), 200


@bp.route('/ai', methods=['PUT'])
@login_required_api
@admin_required
def update_ai_settings():
    """Save or update an AI provider API key for the workspace."""
    from models_crm import AISettings
    workspace_id = session.get('workspace_id')
    data = request.get_json(silent=True) or {}

    provider = (data.get('provider') or '').strip().lower()
    if provider not in ('groq', 'gemini', 'anthropic', 'openai', 'openrouter', 'minimax'):
        return jsonify({'error': 'Geçersiz provider (groq/gemini/anthropic/openai/openrouter/minimax)'}), 400

    api_key = (data.get('api_key') or '').strip()
    model_name = (data.get('model_name') or '').strip()
    is_active = data.get('is_active', True)

    row = AISettings.query.filter_by(workspace_id=workspace_id, provider=provider).first()
    if not row:
        row = AISettings(workspace_id=workspace_id, provider=provider)
        db.session.add(row)

    if api_key and api_key != '***':
        row.api_key_encrypted = _ai_encrypt(api_key)
    row.model_name = model_name or None
    row.is_active = bool(is_active)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

    decrypted = _ai_decrypt(row.api_key_encrypted)
    return jsonify({
        'status': 'updated',
        'provider': row.provider,
        'api_key_masked': _mask_key(decrypted),
        'has_key': bool(decrypted),
        'model_name': row.model_name or '',
        'is_active': row.is_active,
    }), 200


@bp.route('/ai/<provider>', methods=['DELETE'])
@login_required_api
@admin_required
def delete_ai_settings(provider):
    """Remove an AI provider API key from the workspace."""
    from models_crm import AISettings
    workspace_id = session.get('workspace_id')
    row = AISettings.query.filter_by(workspace_id=workspace_id, provider=provider).first()
    if not row:
        return jsonify({'error': 'Kayıt bulunamadı'}), 404

    try:
        db.session.delete(row)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

    return jsonify({'status': 'deleted'}), 200


@bp.route('/ai/test', methods=['POST'])
@login_required_api
@admin_required
def test_ai_key():
    """Test an AI provider API key before saving."""
    data = request.get_json(silent=True) or {}
    provider = (data.get('provider') or '').strip().lower()
    api_key = (data.get('api_key') or '').strip()
    model_name = (data.get('model_name') or '').strip()

    if not api_key:
        return jsonify({'success': False, 'error': 'API key gerekli'}), 400

    try:
        if provider == 'groq':
            from groq import Groq
            client = Groq(api_key=api_key)
            groq_model = model_name or 'llama-3.1-70b-versatile'
            completion = client.chat.completions.create(
                model=groq_model,
                messages=[{'role': 'user', 'content': 'Say hello in one word'}],
                max_tokens=10,
                temperature=1
            )
            return jsonify({'success': True, 'message': f'{groq_model} bağlantısı başarılı'}), 200

        elif provider == 'gemini':
            from google import genai
            client = genai.Client(api_key=api_key)
            gem_model = model_name or 'gemini-2.5-flash'
            resp = client.models.generate_content(
                model=gem_model,
                contents=[{'role': 'user', 'parts': [{'text': 'Say hello in one word'}]}],
            )
            return jsonify({'success': True, 'message': f'{gem_model} bağlantısı başarılı'}), 200

        elif provider == 'anthropic':
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            ant_model = model_name or 'claude-3-5-sonnet-latest'
            resp = client.messages.create(
                model=ant_model,
                max_tokens=10,
                messages=[{'role': 'user', 'content': 'Say hello in one word'}]
            )
            return jsonify({'success': True, 'message': f'{ant_model} bağlantısı başarılı'}), 200

        elif provider == 'openrouter':
            import requests
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            }
            or_model = model_name or 'openrouter/auto'
            payload = {
                'model': or_model,
                'messages': [{'role': 'user', 'content': 'Say hello in one word'}],
                'max_tokens': 10,
            }
            resp = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=10
            )
            resp.raise_for_status()
            return jsonify({'success': True, 'message': f'{or_model} bağlantısı başarılı'}), 200

        elif provider == 'minimax':
            import requests
            headers = {
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            }
            min_model = model_name or 'MiniMax-M2.7'
            payload = {
                'model': min_model,
                'max_tokens': 10,
                'messages': [{'role': 'user', 'content': 'Say hello in one word'}]
            }
            resp = requests.post(
                'https://api.minimax.io/anthropic/v1/messages',
                headers=headers,
                json=payload,
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            # MiniMax returns Anthropic-compatible format
            if data.get('content') and len(data['content']) > 0:
                content_block = data['content'][0]
                response_text = content_block.get('text', content_block.get('content', 'Connection successful'))
            else:
                response_text = 'Connection successful'
            return jsonify({'success': True, 'message': f'{min_model} bağlantısı başarılı: {response_text[:30]}'}), 200

        else:
            return jsonify({'success': False, 'error': f'Test desteklenmiyor: {provider}'}), 400

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


# ─── Avatar Upload ───────────────────────────────────────────────────────────

ALLOWED_AVATAR_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2 MB

@bp.route('/avatar', methods=['POST'])
@login_required_api
def upload_avatar():
    if 'avatar' not in request.files:
        return jsonify({'error': 'Dosya bulunamadı'}), 400
    file = request.files['avatar']
    if not file or file.filename == '':
        return jsonify({'error': 'Geçersiz dosya'}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        return jsonify({'error': 'Desteklenmeyen format. JPG, PNG veya GIF kullanın.'}), 400

    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_AVATAR_SIZE:
        return jsonify({'error': 'Dosya 2 MB sınırını aşıyor'}), 400

    user_id = session.get('user_id')
    filename = f'user_{user_id}.{ext}'
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'avatars')
    os.makedirs(upload_dir, exist_ok=True)

    # Remove old avatar files for this user
    for old_ext in ALLOWED_AVATAR_EXTENSIONS:
        old_path = os.path.join(upload_dir, f'user_{user_id}.{old_ext}')
        if os.path.exists(old_path) and old_ext != ext:
            os.remove(old_path)

    save_path = os.path.join(upload_dir, filename)
    file.save(save_path)

    url = f'/static/uploads/avatars/{filename}'
    user = User.query.get(user_id)
    user.avatar_url = url
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

    return jsonify({'success': True, 'url': url}), 200


# ─── Personal Preferences ────────────────────────────────────────────────────

@bp.route('/preferences', methods=['GET'])
@login_required_api
def get_preferences():
    user_id = session.get('user_id')
    user = User.query.get_or_404(user_id)
    return jsonify({
        'name': user.name,
        'email': user.email,
        'avatar_url': user.avatar_url,
        'timezone': user.timezone or 'auto',
        'date_format': user.date_format or 'DD/MM/YYYY',
        'language': user.language or 'tr',
        'currency': user.currency or 'TRY',
        'pref_activity_after_win': bool(user.pref_activity_after_win),
        'pref_detail_deal': bool(user.pref_detail_deal) if user.pref_detail_deal is not None else True,
        'pref_detail_contact': bool(user.pref_detail_contact) if user.pref_detail_contact is not None else True,
        'pref_detail_org': bool(user.pref_detail_org) if user.pref_detail_org is not None else True,
        'pref_us_phone': bool(user.pref_us_phone),
        'pref_email_new_tab': bool(user.pref_email_new_tab),
        'pref_win_celebration': bool(user.pref_win_celebration) if user.pref_win_celebration is not None else True,
        'pref_auto_labels': bool(user.pref_auto_labels),
    }), 200


@bp.route('/preferences', methods=['PUT'])
@login_required_api
def update_preferences():
    user_id = session.get('user_id')
    user = User.query.get_or_404(user_id)
    data = request.get_json() or {}

    string_fields = ['timezone', 'date_format', 'language', 'currency']
    bool_fields = [
        'pref_activity_after_win', 'pref_detail_deal', 'pref_detail_contact',
        'pref_detail_org', 'pref_us_phone', 'pref_email_new_tab',
        'pref_win_celebration', 'pref_auto_labels',
    ]

    if 'name' in data and data['name'].strip():
        user.name = data['name'].strip()

    for field in string_fields:
        if field in data:
            setattr(user, field, str(data[field]))

    for field in bool_fields:
        if field in data:
            setattr(user, field, bool(data[field]))

    try:
        db.session.commit()
        return jsonify({'status': 'updated'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
