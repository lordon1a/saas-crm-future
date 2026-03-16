from datetime import datetime
import os

from flask import Blueprint, request, jsonify, render_template, g, send_file

from config import Config
from models import db, Conversation, Message
from models_crm import (
    CustomerUser,
    PortalBranding,
    Company,
    Contact,
    Deal,
    DealStage,
    Task,
    Milestone,
    Activity,
    Document,
    DocumentVersion,
)
from services.auth_manager import AuthManager
from services.portal_auth import PortalAuth


bp = Blueprint('portal', __name__, url_prefix='/portal')

DEFAULT_PORTAL_BRANDING = {
    'logo_url': '',
    'primary_color': '#7c3aed',
    'secondary_color': '#8b5cf6',
    'custom_domain': '',
    'custom_css': '',
}


def _token_exp_seconds() -> int:
    return max(1, int(Config.PORTAL_JWT_EXP_HOURS)) * 3600


def _extract_bearer_token() -> str | None:
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    return auth_header.replace('Bearer ', '', 1).strip()


def _normalize_hex_color(value: str | None, fallback: str) -> str:
    raw = (value or '').strip().lower()
    if len(raw) == 7 and raw.startswith('#'):
        try:
            int(raw[1:], 16)
            return raw
        except ValueError:
            return fallback
    return fallback


def _sanitize_custom_css(value: str | None) -> str:
    if not value:
        return ''
    return value.replace('<', '').replace('>', '').strip()


def _serialize_branding(branding: PortalBranding | None) -> dict:
    if not branding:
        return dict(DEFAULT_PORTAL_BRANDING)

    return {
        'logo_url': branding.logo_url or '',
        'primary_color': _normalize_hex_color(branding.primary_color, DEFAULT_PORTAL_BRANDING['primary_color']),
        'secondary_color': _normalize_hex_color(branding.secondary_color, DEFAULT_PORTAL_BRANDING['secondary_color']),
        'custom_domain': branding.custom_domain or '',
        'custom_css': _sanitize_custom_css(branding.custom_css),
    }


def _request_host_name() -> str:
    host = (request.host or '').strip().lower()
    if ':' in host:
        return host.split(':', 1)[0]
    return host


def _page_branding() -> dict:
    host = _request_host_name()
    if host and host not in {'localhost', '127.0.0.1'}:
        by_domain = PortalBranding.query.filter_by(custom_domain=host).first()
        if by_domain:
            return _serialize_branding(by_domain)
    return dict(DEFAULT_PORTAL_BRANDING)


def _render_portal_page(template_name: str):
    return render_template(template_name, portal_branding=_page_branding())


def portal_auth_required(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_bearer_token()
        if not token:
            return jsonify({'error': 'Portal auth token required'}), 401

        payload = PortalAuth.decode_token(token, Config.PORTAL_JWT_SECRET)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401

        user_id = payload.get('sub')
        workspace_id = payload.get('workspace_id')
        company_id = payload.get('company_id')

        customer_user = CustomerUser.query.filter_by(
            id=user_id,
            workspace_id=workspace_id,
            company_id=company_id,
            is_active=True,
        ).first()

        if not customer_user:
            return jsonify({'error': 'Portal user not found'}), 401

        g.portal_user = customer_user
        return f(*args, **kwargs)

    return decorated


def _company_customer_ids(workspace_id: int, company_id: int) -> list[int]:
    rows = Contact.query.filter(
        Contact.workspace_id == workspace_id,
        Contact.company_id == company_id,
        Contact.customer_id.isnot(None),
    ).all()
    return [row.customer_id for row in rows if row.customer_id]


def _company_active_deal(workspace_id: int, company_id: int) -> Deal | None:
    return Deal.query.filter_by(
        workspace_id=workspace_id,
        company_id=company_id,
        status='open',
    ).order_by(Deal.updated_at.desc(), Deal.created_at.desc()).first()


def _serialize_deal_summary(deal: Deal | None) -> dict | None:
    if not deal:
        return None

    total_stages = max(1, DealStage.query.filter_by(pipeline_id=deal.pipeline_id).count())
    stage_order = deal.stage.order if deal.stage else 0
    progress_percentage = round((stage_order / total_stages) * 100, 2) if stage_order else 0

    return {
        'id': deal.id,
        'name': deal.name,
        'status': deal.status,
        'value': float(deal.value),
        'expected_close_date': deal.expected_close_date.isoformat() if deal.expected_close_date else None,
        'pipeline': deal.pipeline.name if deal.pipeline else None,
        'stage': {
            'id': deal.stage.id if deal.stage else None,
            'name': deal.stage.name if deal.stage else None,
            'order': stage_order,
            'total_stages': total_stages,
            'progress_percentage': progress_percentage,
        },
        'updated_at': deal.updated_at.isoformat() if deal.updated_at else None,
    }


def _approval_subject(document_id: int, deal_id: int | None) -> str:
    return f'PORTAL_APPROVAL document={document_id} deal={deal_id or 0}'


def _is_document_approved(workspace_id: int, company_id: int, document_id: int) -> bool:
    prefix = f'PORTAL_APPROVAL document={document_id} '
    existing = Activity.query.filter(
        Activity.workspace_id == workspace_id,
        Activity.company_id == company_id,
        Activity.activity_type == 'customer_approval',
        Activity.subject.like(f'{prefix}%'),
    ).first()
    return existing is not None


# ---------------------------------------------------------------------------
# Portal UI Pages
# ---------------------------------------------------------------------------


@bp.route('', methods=['GET'])
def portal_home():
    return _render_portal_page('portal/login.html')


@bp.route('/login', methods=['GET'])
def portal_login_page():
    return _render_portal_page('portal/login.html')


@bp.route('/dashboard', methods=['GET'])
def portal_dashboard_page():
    return _render_portal_page('portal/dashboard.html')


@bp.route('/documents', methods=['GET'])
def portal_documents_page():
    return _render_portal_page('portal/documents.html')


@bp.route('/messages', methods=['GET'])
def portal_messages_page():
    return _render_portal_page('portal/messages.html')


# ---------------------------------------------------------------------------
# Portal Auth API
# ---------------------------------------------------------------------------


@bp.route('/register', methods=['POST'])
def portal_register():
    data = request.get_json(silent=True) or {}

    company_id = data.get('company_id')
    contact_id = data.get('contact_id')
    email = (data.get('email') or '').strip().lower()
    full_name = (data.get('full_name') or '').strip()
    password = data.get('password') or ''

    if not company_id or not email or not full_name or not password:
        return jsonify({'error': 'company_id, full_name, email ve password zorunludur'}), 400

    if len(password) < 8:
        return jsonify({'error': 'Password en az 8 karakter olmalıdır'}), 400

    company = Company.query.filter_by(id=company_id).first()
    if not company:
        return jsonify({'error': 'Company not found'}), 404

    if contact_id:
        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=company.workspace_id,
            company_id=company.id,
        ).first()
        if not contact:
            return jsonify({'error': 'Contact does not belong to company'}), 400

    existing = CustomerUser.query.filter_by(email=email).first()
    if existing:
        return jsonify({'error': 'Email already registered'}), 409

    customer_user = CustomerUser(
        workspace_id=company.workspace_id,
        company_id=company.id,
        contact_id=contact_id,
        email=email,
        full_name=full_name,
        password_hash=AuthManager.hash_password(password),
        is_active=True,
    )
    db.session.add(customer_user)
    db.session.commit()

    return jsonify({
        'id': customer_user.id,
        'email': customer_user.email,
        'company_id': customer_user.company_id,
        'status': 'created',
    }), 201


@bp.route('/login', methods=['POST'])
def portal_login():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({'error': 'Email ve password zorunludur'}), 400

    customer_user = CustomerUser.query.filter_by(email=email, is_active=True).first()
    if not customer_user or not AuthManager.verify_password(customer_user.password_hash, password):
        return jsonify({'error': 'Invalid credentials'}), 401

    customer_user.last_login_at = datetime.utcnow()
    db.session.commit()

    token = PortalAuth.encode_token(
        {
            'sub': customer_user.id,
            'workspace_id': customer_user.workspace_id,
            'company_id': customer_user.company_id,
            'typ': 'customer_portal',
        },
        Config.PORTAL_JWT_SECRET,
        _token_exp_seconds(),
    )

    return jsonify({
        'token': token,
        'token_type': 'Bearer',
        'expires_in': _token_exp_seconds(),
        'user': {
            'id': customer_user.id,
            'full_name': customer_user.full_name,
            'email': customer_user.email,
            'company_id': customer_user.company_id,
            'workspace_id': customer_user.workspace_id,
        },
    }), 200


@bp.route('/api/me', methods=['GET'])
@portal_auth_required
def portal_me():
    user = g.portal_user
    return jsonify({
        'id': user.id,
        'full_name': user.full_name,
        'email': user.email,
        'company_id': user.company_id,
        'workspace_id': user.workspace_id,
        'company_name': user.company.name if user.company else None,
    }), 200


@bp.route('/api/branding', methods=['GET'])
@portal_auth_required
def portal_branding():
    user = g.portal_user
    branding = PortalBranding.query.filter_by(workspace_id=user.workspace_id).first()
    payload = _serialize_branding(branding)
    payload['workspace_id'] = user.workspace_id
    return jsonify(payload), 200


@bp.route('/api/deal-summary', methods=['GET'])
@portal_auth_required
def portal_deal_summary():
    user = g.portal_user
    deal = _company_active_deal(user.workspace_id, user.company_id)

    return jsonify({
        'deal': _serialize_deal_summary(deal),
    }), 200


# ---------------------------------------------------------------------------
# Portal Data API (isolated by company)
# ---------------------------------------------------------------------------


@bp.route('/api/tasks', methods=['GET'])
@portal_auth_required
def portal_tasks():
    user = g.portal_user
    tasks = Task.query.filter_by(
        workspace_id=user.workspace_id,
        company_id=user.company_id,
        is_customer_facing=True,
    ).order_by(Task.due_date.asc().nullslast(), Task.created_at.desc()).all()

    return jsonify({
        'tasks': [
            {
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'status': task.status,
                'priority': task.priority,
                'due_date': task.due_date.isoformat() if task.due_date else None,
                'milestone_id': task.milestone_id,
                'created_at': task.created_at.isoformat(),
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            }
            for task in tasks
        ]
    }), 200


@bp.route('/api/tasks/<int:task_id>', methods=['PATCH'])
@portal_auth_required
def portal_update_task(task_id):
    user = g.portal_user
    data = request.get_json(silent=True) or {}
    new_status = (data.get('status') or '').strip().lower()

    allowed_statuses = {'not_started', 'in_progress', 'completed'}
    if new_status not in allowed_statuses:
        return jsonify({'error': 'Invalid status'}), 400

    task = Task.query.filter_by(
        id=task_id,
        workspace_id=user.workspace_id,
        company_id=user.company_id,
        is_customer_facing=True,
    ).first()

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    previous_status = task.status
    task.status = new_status
    task.completed_at = datetime.utcnow() if new_status == 'completed' else None
    db.session.commit()

    if previous_status != 'completed' and task.status == 'completed':
        try:
            from services.webhook_service import WebhookService
            WebhookService.dispatch_event(user.workspace_id, 'task.completed', {
                'task_id': task.id,
                'title': task.title,
                'company_id': task.company_id,
                'deal_id': task.deal_id,
                'milestone_id': task.milestone_id,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'updated_at': task.updated_at.isoformat() if task.updated_at else None,
                'source': 'customer_portal',
            })
        except Exception:
            pass

    return jsonify({
        'id': task.id,
        'status': task.status,
        'completed_at': task.completed_at.isoformat() if task.completed_at else None,
    }), 200


@bp.route('/api/milestones', methods=['GET'])
@portal_auth_required
def portal_milestones():
    user = g.portal_user

    milestones = Milestone.query.filter_by(
        workspace_id=user.workspace_id,
        company_id=user.company_id,
    ).order_by(Milestone.due_date.asc().nullslast(), Milestone.created_at.desc()).all()

    result = []
    for milestone in milestones:
        milestone_tasks = Task.query.filter_by(
            workspace_id=user.workspace_id,
            company_id=user.company_id,
            milestone_id=milestone.id,
            is_customer_facing=True,
        ).all()

        total = len(milestone_tasks)
        completed = len([task for task in milestone_tasks if task.status == 'completed'])
        progress = round((completed / total * 100), 2) if total else 0

        result.append({
            'id': milestone.id,
            'name': milestone.name,
            'due_date': milestone.due_date.isoformat() if milestone.due_date else None,
            'status': milestone.status,
            'progress': {
                'total_tasks': total,
                'completed_tasks': completed,
                'progress_percentage': progress,
            },
        })

    return jsonify({'milestones': result}), 200


@bp.route('/api/documents', methods=['GET'])
@portal_auth_required
def portal_documents():
    user = g.portal_user
    active_deal = _company_active_deal(user.workspace_id, user.company_id)

    documents = Document.query.filter_by(
        workspace_id=user.workspace_id,
        company_id=user.company_id,
        is_customer_visible=True,
    ).order_by(Document.created_at.desc()).all()

    result = []
    for document in documents:
        latest_version = DocumentVersion.query.filter_by(document_id=document.id).order_by(
            DocumentVersion.version_number.desc()
        ).first()
        requires_approval = (document.category or '').lower() in {'proposal', 'contract'}
        result.append({
            'id': document.id,
            'name': document.name,
            'category': document.category,
            'created_at': document.created_at.isoformat(),
            'version': latest_version.version_number if latest_version else None,
            'file_size': latest_version.file_size if latest_version else None,
            'requires_approval': requires_approval,
            'is_approved': _is_document_approved(user.workspace_id, user.company_id, document.id),
            'linked_deal_id': document.deal_id or (active_deal.id if active_deal else None),
        })

    return jsonify({'documents': result}), 200


@bp.route('/api/documents/<int:document_id>/download', methods=['GET'])
@portal_auth_required
def portal_download_document(document_id):
    user = g.portal_user

    document = Document.query.filter_by(
        id=document_id,
        workspace_id=user.workspace_id,
        company_id=user.company_id,
        is_customer_visible=True,
    ).first()

    if not document:
        return jsonify({'error': 'Document not found'}), 404

    version = DocumentVersion.query.filter_by(document_id=document.id).order_by(
        DocumentVersion.version_number.desc()
    ).first()

    if not version:
        return jsonify({'error': 'Document file not found'}), 404

    file_path = os.path.abspath(version.file_path)
    if not os.path.exists(file_path):
        return jsonify({'error': 'Document file not found'}), 404

    return send_file(file_path, as_attachment=True, download_name=document.name)


@bp.route('/api/documents/<int:document_id>/approve', methods=['POST'])
@portal_auth_required
def portal_approve_document(document_id):
    user = g.portal_user
    data = request.get_json(silent=True) or {}

    document = Document.query.filter_by(
        id=document_id,
        workspace_id=user.workspace_id,
        company_id=user.company_id,
        is_customer_visible=True,
    ).first()

    if not document:
        return jsonify({'error': 'Document not found'}), 404

    category = (document.category or '').lower()
    if category not in {'proposal', 'contract'}:
        return jsonify({'error': 'Only proposal/contract documents can be approved'}), 400

    requested_deal_id = data.get('deal_id')
    if requested_deal_id:
        deal = Deal.query.filter_by(
            id=requested_deal_id,
            workspace_id=user.workspace_id,
            company_id=user.company_id,
        ).first()
    elif document.deal_id:
        deal = Deal.query.filter_by(
            id=document.deal_id,
            workspace_id=user.workspace_id,
            company_id=user.company_id,
        ).first()
    else:
        deal = _company_active_deal(user.workspace_id, user.company_id)

    approval_subject = _approval_subject(document.id, deal.id if deal else None)
    existing_approval = Activity.query.filter_by(
        workspace_id=user.workspace_id,
        company_id=user.company_id,
        activity_type='customer_approval',
        subject=approval_subject,
    ).first()

    if existing_approval:
        return jsonify({
            'status': 'already_approved',
            'approved_at': existing_approval.created_at.isoformat(),
            'deal': _serialize_deal_summary(deal),
        }), 200

    note = (data.get('note') or '').strip()
    approval_body = f'Approved by {user.full_name} <{user.email}>'
    if note:
        approval_body = f'{approval_body} | note: {note}'

    approval_activity = Activity(
        workspace_id=user.workspace_id,
        activity_type='customer_approval',
        company_id=user.company_id,
        deal_id=deal.id if deal else document.deal_id,
        user_id=None,
        subject=approval_subject,
        body=approval_body,
        created_at=datetime.utcnow(),
    )
    db.session.add(approval_activity)

    stage_transition = None
    if deal and deal.status == 'open' and deal.stage:
        next_stage = DealStage.query.filter(
            DealStage.pipeline_id == deal.pipeline_id,
            DealStage.order > deal.stage.order,
        ).order_by(DealStage.order.asc()).first()

        if next_stage:
            previous_stage_name = deal.stage.name
            deal.stage_id = next_stage.id
            deal.updated_at = datetime.utcnow()
            stage_transition = {
                'from': previous_stage_name,
                'to': next_stage.name,
            }

            stage_activity = Activity(
                workspace_id=user.workspace_id,
                activity_type='system',
                company_id=user.company_id,
                deal_id=deal.id,
                user_id=None,
                subject=f'PORTAL_STAGE_ADVANCE deal={deal.id}',
                body=f'Deal stage moved from {previous_stage_name} to {next_stage.name} after customer approval',
                created_at=datetime.utcnow(),
            )
            db.session.add(stage_activity)

    db.session.commit()

    return jsonify({
        'status': 'approved',
        'document_id': document.id,
        'stage_transition': stage_transition,
        'deal': _serialize_deal_summary(deal),
    }), 200


@bp.route('/api/messages', methods=['GET'])
@portal_auth_required
def portal_messages_list():
    user = g.portal_user
    customer_ids = _company_customer_ids(user.workspace_id, user.company_id)

    if not customer_ids:
        return jsonify({'conversations': []}), 200

    conversations = Conversation.query.filter(
        Conversation.workspace_id == user.workspace_id,
        Conversation.customer_id.in_(customer_ids),
    ).order_by(Conversation.last_message_at.desc()).all()

    result = []
    for conversation in conversations:
        last_message = Message.query.filter_by(conversation_id=conversation.id).order_by(Message.created_at.desc()).first()
        result.append({
            'id': conversation.id,
            'customer_id': conversation.customer_id,
            'customer_name': conversation.customer.profile_name if conversation.customer else None,
            'status': conversation.status,
            'tags': conversation.tags,
            'last_message': last_message.message_body if last_message else '',
            'last_message_at': conversation.last_message_at.isoformat(),
            'message_count': Message.query.filter_by(conversation_id=conversation.id).count(),
        })

    return jsonify({'conversations': result}), 200


@bp.route('/api/messages/<int:conversation_id>', methods=['GET'])
@portal_auth_required
def portal_messages_detail(conversation_id):
    user = g.portal_user
    customer_ids = _company_customer_ids(user.workspace_id, user.company_id)

    conversation = Conversation.query.filter(
        Conversation.id == conversation_id,
        Conversation.workspace_id == user.workspace_id,
        Conversation.customer_id.in_(customer_ids),
    ).first()

    if not conversation:
        return jsonify({'error': 'Conversation not found'}), 404

    messages = Message.query.filter_by(conversation_id=conversation.id).order_by(Message.created_at.asc()).all()
    data = [
        {
            'id': message.id,
            'sender_type': message.sender_type,
            'message_body': message.message_body,
            'is_read': message.is_read,
            'created_at': message.created_at.isoformat(),
        }
        for message in messages
    ]

    return jsonify({
        'conversation_id': conversation.id,
        'customer_name': conversation.customer.profile_name if conversation.customer else None,
        'messages': data,
    }), 200


@bp.route('/api/messages/<int:conversation_id>', methods=['POST'])
@portal_auth_required
def portal_send_message(conversation_id):
    user = g.portal_user
    customer_ids = _company_customer_ids(user.workspace_id, user.company_id)

    conversation = Conversation.query.filter(
        Conversation.id == conversation_id,
        Conversation.workspace_id == user.workspace_id,
        Conversation.customer_id.in_(customer_ids),
    ).first()

    if not conversation:
        return jsonify({'error': 'Conversation not found'}), 404

    data = request.get_json(silent=True) or {}
    message_body = (data.get('message_body') or '').strip()
    if not message_body:
        return jsonify({'error': 'message_body is required'}), 400

    now = datetime.utcnow()
    message = Message(
        conversation_id=conversation.id,
        sender_type='customer',
        sender_id=None,
        message_body=message_body,
        meta_message_id=f'portal-{conversation.id}-{int(now.timestamp())}',
        is_read=False,
        created_at=now,
    )

    conversation.last_message_at = now
    db.session.add(message)
    db.session.commit()

    return jsonify({
        'status': 'sent',
        'message': {
            'id': message.id,
            'conversation_id': message.conversation_id,
            'sender_type': message.sender_type,
            'message_body': message.message_body,
            'created_at': message.created_at.isoformat(),
        }
    }), 201
