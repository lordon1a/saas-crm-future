"""Call logging API routes."""
import base64
import hashlib
import hmac

from flask import Blueprint, request, jsonify, session, current_app
from functools import wraps

from models import User
from services.call_service import (
    create_call_log,
    list_call_logs,
    get_call_log,
    update_call_log,
    delete_call_log,
    create_from_twilio_event,
    calls_summary,
)

calls_bp = Blueprint('calls', __name__)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        user = User.query.get(user_id)
        if not user:
            session.clear()
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


def _workspace_id():
    return session.get('workspace_id')


def _validate_twilio_signature() -> bool:
    """Validate Twilio webhook signature when auth token is configured."""
    auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')
    if not auth_token:
        return True

    signature = request.headers.get('X-Twilio-Signature', '')
    if not signature:
        return False

    params = request.form.to_dict(flat=True)
    payload = request.url + ''.join(f'{k}{v}' for k, v in sorted(params.items()))
    expected = base64.b64encode(
        hmac.new(auth_token.encode('utf-8'), payload.encode('utf-8'), hashlib.sha1).digest()
    ).decode('utf-8')
    return hmac.compare_digest(signature, expected)


@calls_bp.route('/api/v1/calls', methods=['GET'])
@login_required
def api_list_calls():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    contact_id = request.args.get('contact_id', type=int)

    rows, total = list_call_logs(_workspace_id(), page=page, per_page=per_page, contact_id=contact_id)
    return jsonify({
        'calls': [r.to_dict() for r in rows],
        'total': total,
        'page': page,
        'per_page': per_page,
    })


@calls_bp.route('/api/v1/calls', methods=['POST'])
@login_required
def api_create_call():
    data = request.get_json() or {}
    try:
        row = create_call_log(_workspace_id(), session.get('user_id'), data)
        return jsonify({'call': row.to_dict()}), 201
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400


@calls_bp.route('/api/v1/calls/<int:call_id>', methods=['GET'])
@login_required
def api_get_call(call_id):
    row = get_call_log(_workspace_id(), call_id)
    if not row:
        return jsonify({'error': 'Call not found'}), 404
    return jsonify({'call': row.to_dict()})


@calls_bp.route('/api/v1/calls/<int:call_id>', methods=['PATCH'])
@login_required
def api_update_call(call_id):
    row = update_call_log(_workspace_id(), call_id, request.get_json() or {})
    if not row:
        return jsonify({'error': 'Call not found'}), 404
    return jsonify({'call': row.to_dict()})


@calls_bp.route('/api/v1/calls/<int:call_id>', methods=['DELETE'])
@login_required
def api_delete_call(call_id):
    ok = delete_call_log(_workspace_id(), call_id)
    if not ok:
        return jsonify({'error': 'Call not found'}), 404
    return jsonify({'success': True})


@calls_bp.route('/api/v1/contacts/<int:contact_id>/calls', methods=['GET'])
@login_required
def api_contact_calls(contact_id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    rows, total = list_call_logs(_workspace_id(), page=page, per_page=per_page, contact_id=contact_id)
    return jsonify({'calls': [r.to_dict() for r in rows], 'total': total})


@calls_bp.route('/api/v1/webhooks/twilio/call', methods=['POST'])
def webhook_twilio_call():
    if not _validate_twilio_signature():
        return jsonify({'error': 'Invalid Twilio signature'}), 403

    workspace_id = request.args.get('workspace_id', type=int)
    logged_by = request.args.get('logged_by', type=int)
    if not workspace_id or not logged_by:
        return jsonify({'error': 'workspace_id and logged_by query params are required'}), 400

    payload = request.form.to_dict() or request.get_json() or {}
    row = create_from_twilio_event(workspace_id, logged_by, payload)
    return jsonify({'ok': True, 'call': row.to_dict()})


@calls_bp.route('/api/v1/analytics/calls/summary', methods=['GET'])
@login_required
def api_calls_summary():
    days = request.args.get('days', 7, type=int)
    return jsonify(calls_summary(_workspace_id(), days=days))
