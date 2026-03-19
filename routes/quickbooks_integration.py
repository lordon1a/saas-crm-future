import secrets
import time
from urllib.parse import urlencode

from flask import Blueprint, jsonify, redirect, request, session

from config import Config
from services.quickbooks_service import QuickBooksService


bp = Blueprint('quickbooks_integration', __name__)


def _agent_session_required(f):
    from functools import wraps

    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get('user_id') or not session.get('workspace_id'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)

    return wrapped


def _clear_oauth_session_state():
    session.pop('quickbooks_oauth_state', None)
    session.pop('quickbooks_oauth_workspace_id', None)
    session.pop('quickbooks_oauth_user_id', None)
    session.pop('quickbooks_oauth_expires_at', None)


@bp.route('/api/settings/quickbooks/status', methods=['GET'])
@_agent_session_required
def quickbooks_status():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    row = QuickBooksService.get_active_integration(workspace_id, user_id)
    payload = QuickBooksService.serialize_integration(row)
    payload['configured'] = QuickBooksService.is_configured()
    payload['redirect_uri'] = Config.QUICKBOOKS_REDIRECT_URI
    return jsonify(payload), 200


@bp.route('/api/settings/quickbooks/connect', methods=['POST'])
@_agent_session_required
def quickbooks_connect():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')

    if not QuickBooksService.is_configured():
        return jsonify({'error': 'QuickBooks OAuth is not configured'}), 400

    state = secrets.token_urlsafe(32)
    authorization_url = QuickBooksService.generate_authorization_url(state)

    session['quickbooks_oauth_state'] = state
    session['quickbooks_oauth_workspace_id'] = workspace_id
    session['quickbooks_oauth_user_id'] = user_id
    session['quickbooks_oauth_expires_at'] = int(time.time()) + 600

    return jsonify({'authorization_url': authorization_url}), 200


@bp.route('/integrations/quickbooks/callback', methods=['GET'])
def quickbooks_callback():
    if not session.get('user_id') or not session.get('workspace_id'):
        return redirect('/settings?quickbooks_error=unauthorized')

    incoming_error = request.args.get('error')
    if incoming_error:
        _clear_oauth_session_state()
        return redirect(f"/settings?{urlencode({'quickbooks_error': incoming_error})}")

    state = request.args.get('state', '')
    code = request.args.get('code', '')
    realm_id = request.args.get('realmId', '')

    expected_state = session.get('quickbooks_oauth_state')
    expected_workspace_id = session.get('quickbooks_oauth_workspace_id')
    expected_user_id = session.get('quickbooks_oauth_user_id')
    expires_at = session.get('quickbooks_oauth_expires_at')

    now_ts = int(time.time())
    if (
        not expected_state
        or state != expected_state
        or expected_workspace_id != session.get('workspace_id')
        or expected_user_id != session.get('user_id')
        or not expires_at
        or now_ts > int(expires_at)
    ):
        _clear_oauth_session_state()
        return redirect('/settings?quickbooks_error=invalid_state')

    try:
        token_payload = QuickBooksService.exchange_code_for_tokens(code=code)
        QuickBooksService.upsert_integration(
            workspace_id=session.get('workspace_id'),
            user_id=session.get('user_id'),
            token_payload=token_payload,
            realm_id=realm_id,
        )
    except Exception as exc:
        _clear_oauth_session_state()
        return redirect(f"/settings?{urlencode({'quickbooks_error': str(exc)[:120]})}")

    _clear_oauth_session_state()
    return redirect('/settings?quickbooks_connected=1')


@bp.route('/api/settings/quickbooks/disconnect', methods=['DELETE'])
@_agent_session_required
def quickbooks_disconnect():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    removed = QuickBooksService.disconnect(workspace_id, user_id)
    return jsonify({'status': 'disconnected' if removed else 'not_connected'}), 200


@bp.route('/api/settings/quickbooks/sync/invoices', methods=['POST'])
@_agent_session_required
def quickbooks_sync_invoices():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    result = QuickBooksService.sync_pending_invoices(workspace_id, user_id)
    return jsonify(result), 200


@bp.route('/api/settings/quickbooks/invoices', methods=['GET'])
@_agent_session_required
def quickbooks_invoices():
    workspace_id = session.get('workspace_id')
    limit = request.args.get('limit', default=20, type=int)
    return jsonify({'invoices': QuickBooksService.list_invoices(workspace_id, limit)}), 200


@bp.route('/api/settings/quickbooks/errors', methods=['GET'])
@_agent_session_required
def quickbooks_errors():
    workspace_id = session.get('workspace_id')
    limit = request.args.get('limit', default=20, type=int)
    return jsonify({'errors': QuickBooksService.list_errors(workspace_id, limit)}), 200


@bp.route('/api/v1/quickbooks/deals/<int:deal_id>/invoice', methods=['GET'])
@_agent_session_required
def quickbooks_deal_invoice(deal_id):
    workspace_id = session.get('workspace_id')
    payload = QuickBooksService.get_deal_invoice(workspace_id, deal_id)
    if not payload:
        return jsonify({'invoice': None}), 200
    return jsonify({'invoice': payload}), 200
