from functools import wraps

from flask import Blueprint, jsonify, request, session

from services.email_hub_service import EmailHubService
from models_crm import EmailSequenceEnrollment


email_hub_bp = Blueprint('email_hub', __name__, url_prefix='/api/v1/email')


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        return f(*args, **kwargs)

    return decorated


def write_access_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        role = (session.get('user_role') or '').lower()
        if role in {'read-only', 'readonly'}:
            return jsonify({'success': False, 'error': 'Write permission required'}), 403
        return f(*args, **kwargs)

    return decorated


@email_hub_bp.route('/templates', methods=['GET'])
@login_required
def list_templates():
    workspace_id = session.get('workspace_id')
    rows = EmailHubService.list_templates(workspace_id)
    return jsonify({'success': True, 'data': rows})


@email_hub_bp.route('/templates', methods=['POST'])
@write_access_required
def create_template():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    payload = request.get_json(silent=True) or {}

    try:
        row = EmailHubService.create_template(
            workspace_id=workspace_id,
            user_id=user_id,
            name=(payload.get('name') or '').strip(),
            subject_template=(payload.get('subject_template') or '').strip(),
            body_template=(payload.get('body_template') or '').strip(),
            design_json=payload.get('design_json'),
            editor_type=(payload.get('editor_type') or 'html').strip(),
        )
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400

    return jsonify({'success': True, 'data': {'id': row.id}}), 201


@email_hub_bp.route('/templates/<int:template_id>', methods=['GET'])
@login_required
def get_template(template_id):
    workspace_id = session.get('workspace_id')
    row = EmailHubService.get_template(workspace_id, template_id)
    if not row:
        return jsonify({'success': False, 'error': 'Template not found'}), 404

    return jsonify({'success': True, 'data': {
        'id': row.id,
        'name': row.name,
        'subject_template': row.subject_template,
        'body_template': row.body_template,
        'design_json': row.design_json,
        'editor_type': row.editor_type or 'html',
        'is_active': bool(row.is_active),
        'created_at': row.created_at.isoformat() if row.created_at else None,
    }})


@email_hub_bp.route('/templates/<int:template_id>', methods=['PATCH'])
@write_access_required
def update_template(template_id):
    workspace_id = session.get('workspace_id')
    payload = request.get_json(silent=True) or {}

    try:
        row = EmailHubService.update_template(
            workspace_id=workspace_id,
            template_id=template_id,
            name=payload.get('name'),
            subject_template=payload.get('subject_template'),
            body_template=payload.get('body_template'),
            design_json=payload.get('design_json'),
            editor_type=payload.get('editor_type'),
            is_active=payload.get('is_active'),
        )
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 404
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500

    return jsonify({'success': True, 'data': {
        'id': row.id,
        'name': row.name,
        'subject_template': row.subject_template,
        'body_template': row.body_template,
        'design_json': row.design_json,
        'editor_type': row.editor_type or 'html',
        'is_active': bool(row.is_active),
    }})


@email_hub_bp.route('/templates/<int:template_id>/render', methods=['POST'])
@login_required
def render_template(template_id):
    workspace_id = session.get('workspace_id')
    payload = request.get_json(silent=True) or {}
    variables = payload.get('variables') or {}

    try:
        rendered = EmailHubService.render_template_preview(workspace_id, template_id, variables)
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400

    return jsonify({'success': True, 'data': rendered})


@email_hub_bp.route('/sequences', methods=['GET'])
@login_required
def list_sequences():
    workspace_id = session.get('workspace_id')
    rows = EmailHubService.list_sequences(workspace_id)
    return jsonify({'success': True, 'data': rows})


@email_hub_bp.route('/sequences', methods=['POST'])
@write_access_required
def create_sequence():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    payload = request.get_json(silent=True) or {}

    try:
        row = EmailHubService.create_sequence(
            workspace_id=workspace_id,
            user_id=user_id,
            name=(payload.get('name') or '').strip(),
            description=payload.get('description'),
            steps=payload.get('steps') or [],
        )
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400

    return jsonify({'success': True, 'data': {'id': row.id}}), 201


@email_hub_bp.route('/send', methods=['POST'])
@write_access_required
def send_email():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    payload = request.get_json(silent=True) or {}

    try:
        result = EmailHubService.queue_outbound_email(
            workspace_id=workspace_id,
            user_id=user_id,
            to_email=(payload.get('to_email') or '').strip(),
            subject=(payload.get('subject') or '').strip(),
            body_text=payload.get('body_text') or '',
            body_html=payload.get('body_html') or '',
            contact_id=payload.get('contact_id'),
            company_id=payload.get('company_id'),
            deal_id=payload.get('deal_id'),
        )
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500

    return jsonify({'success': True, 'data': result})


@email_hub_bp.route('/unified-inbox', methods=['GET'])
@login_required
def unified_inbox():
    workspace_id = session.get('workspace_id')
    channel = request.args.get('channel', 'all')
    limit = min(request.args.get('limit', 50, type=int), 200)
    offset = request.args.get('offset', 0, type=int)

    payload = EmailHubService.get_unified_inbox(
        workspace_id=workspace_id,
        channel=channel,
        limit=limit,
        offset=offset,
    )
    return jsonify({'success': True, 'data': payload})


@email_hub_bp.route('/sequences/<int:sequence_id>/enroll', methods=['POST'])
@login_required
def enroll_contact_in_sequence(sequence_id):
    """Enroll a contact in an email sequence."""
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    payload = request.get_json(silent=True) or {}
    contact_id = payload.get('contact_id')

    if not contact_id:
        return jsonify({'success': False, 'error': 'contact_id is required'}), 400

    try:
        enrollment = EmailHubService.enroll_contact(
            workspace_id=workspace_id,
            sequence_id=sequence_id,
            contact_id=contact_id,
            enrolled_by=user_id,
        )
        return jsonify({'success': True, 'data': {'id': enrollment.id}}), 201
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@email_hub_bp.route('/enrollments/<int:enrollment_id>', methods=['DELETE'])
@login_required
def unenroll_contact(enrollment_id):
    """Unenroll a contact from a sequence."""
    payload = request.get_json(silent=True) or {}
    reason = payload.get('reason', 'manual')

    try:
        enrollment = EmailHubService.unenroll_contact(
            enrollment_id=enrollment_id,
            reason=reason,
        )
        return jsonify({'success': True, 'data': {'id': enrollment.id}})
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@email_hub_bp.route('/sequences/<int:sequence_id>/enrollments', methods=['GET'])
@login_required
def list_sequence_enrollments(sequence_id):
    """List all enrollments for a specific sequence."""
    workspace_id = session.get('workspace_id')

    enrollments = EmailSequenceEnrollment.query.filter_by(
        workspace_id=workspace_id,
        sequence_id=sequence_id,
    ).order_by(EmailSequenceEnrollment.enrolled_at.desc()).all()

    return jsonify({'success': True, 'data': [e.to_dict() for e in enrollments]})


@email_hub_bp.route('/contacts/<int:contact_id>/enrollments', methods=['GET'])
@login_required
def list_contact_enrollments(contact_id):
    """List all sequence enrollments for a specific contact."""
    workspace_id = session.get('workspace_id')

    enrollments = EmailSequenceEnrollment.query.filter_by(
        workspace_id=workspace_id,
        contact_id=contact_id,
    ).order_by(EmailSequenceEnrollment.enrolled_at.desc()).all()

    return jsonify({'success': True, 'data': [e.to_dict() for e in enrollments]})
