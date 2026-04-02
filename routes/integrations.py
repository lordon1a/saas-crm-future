"""Phase 3 integration routes: Zoom, LinkedIn, Facebook Lead Ads, Google Ads."""
from flask import Blueprint, request, jsonify, session, current_app
from functools import wraps
import secrets
from urllib.parse import parse_qs, urlparse

from models import User
from services.zoom_service import ZoomService
from services.linkedin_service import LinkedInService
from services.ads_sync_service import FacebookLeadAdsService, GoogleAdsService

integrations_bp = Blueprint('integrations', __name__)


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


def _user_id():
    return session.get('user_id')


def _extract_state_from_auth_url(auth_url):
    parsed = urlparse(auth_url)
    values = parse_qs(parsed.query).get('state', [])
    return values[0] if values else None


def _validate_oauth_state(provider: str, state: str):
    expected_state = session.get(f'{provider}_oauth_state')
    if not expected_state:
        return False, 'OAuth session is missing or expired'
    if not secrets.compare_digest(state, expected_state):
        return False, 'Invalid OAuth state'
    return True, None


@integrations_bp.route('/api/v1/integrations/zoom/auth', methods=['GET'])
@login_required
def zoom_auth_url():
    try:
        auth_url = ZoomService.get_oauth_url(_workspace_id(), _user_id())
        state = _extract_state_from_auth_url(auth_url)
        if not state:
            return jsonify({'error': 'Failed to initialize OAuth state'}), 500
        session['zoom_oauth_state'] = state
        return jsonify({'auth_url': auth_url})
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400


@integrations_bp.route('/api/v1/integrations/zoom/callback', methods=['GET'])
@login_required
def zoom_callback():
    code = request.args.get('code')
    state = request.args.get('state', '')
    if not code or not state:
        return jsonify({'error': 'Missing code/state'}), 400

    valid_state, state_error = _validate_oauth_state('zoom', state)
    if not valid_state:
        return jsonify({'error': state_error}), 400

    try:
        workspace_id, user_id, _nonce = state.split(':', 2)
        workspace_id = int(workspace_id)
        user_id = int(user_id)

        if workspace_id != _workspace_id() or user_id != _user_id():
            return jsonify({'error': 'OAuth state does not match active session'}), 403

        session.pop('zoom_oauth_state', None)
        integration = ZoomService.handle_oauth_callback(code, int(workspace_id), int(user_id))
        return jsonify({'success': True, 'integration_id': integration.id})
    except Exception as exc:
        current_app.logger.error('Zoom OAuth callback failed: %s', exc)
        return jsonify({'error': str(exc)}), 400


@integrations_bp.route('/api/v1/integrations/zoom', methods=['DELETE'])
@login_required
def zoom_disconnect():
    ok = ZoomService.disconnect(_workspace_id(), _user_id())
    return jsonify({'success': ok})


@integrations_bp.route('/api/v1/webhooks/zoom/recording', methods=['POST'])
def zoom_recording_webhook():
    payload = request.get_json() or {}
    return jsonify(ZoomService.handle_recording_webhook(payload))


@integrations_bp.route('/api/v1/integrations/linkedin/auth', methods=['GET'])
@login_required
def linkedin_auth_url():
    try:
        auth_url = LinkedInService.get_oauth_url(_workspace_id(), _user_id())
        state = _extract_state_from_auth_url(auth_url)
        if not state:
            return jsonify({'error': 'Failed to initialize OAuth state'}), 500
        session['linkedin_oauth_state'] = state
        return jsonify({'auth_url': auth_url})
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400


@integrations_bp.route('/api/v1/integrations/linkedin/callback', methods=['GET'])
@login_required
def linkedin_callback():
    code = request.args.get('code')
    state = request.args.get('state', '')
    if not code or not state:
        return jsonify({'error': 'Missing code/state'}), 400

    valid_state, state_error = _validate_oauth_state('linkedin', state)
    if not valid_state:
        return jsonify({'error': state_error}), 400

    try:
        workspace_id, user_id, _nonce = state.split(':', 2)
        workspace_id = int(workspace_id)
        user_id = int(user_id)

        if workspace_id != _workspace_id() or user_id != _user_id():
            return jsonify({'error': 'OAuth state does not match active session'}), 403

        session.pop('linkedin_oauth_state', None)
        integration = LinkedInService.handle_oauth_callback(code, int(workspace_id), int(user_id))
        return jsonify({'success': True, 'integration_id': integration.id})
    except Exception as exc:
        current_app.logger.error('LinkedIn OAuth callback failed: %s', exc)
        return jsonify({'error': str(exc)}), 400


@integrations_bp.route('/api/v1/contacts/<int:contact_id>/enrich/linkedin', methods=['POST'])
@login_required
def enrich_contact_linkedin(contact_id):
    try:
        data = LinkedInService.enrich_contact(_workspace_id(), contact_id)
        return jsonify({'success': True, 'data': data})
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 404


@integrations_bp.route('/api/v1/webhooks/facebook/lead', methods=['GET'])
def facebook_lead_verify():
    mode = request.args.get('hub.mode')
    verify_token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode != 'subscribe':
        return jsonify({'error': 'Invalid mode'}), 400

    try:
        return FacebookLeadAdsService.verify_webhook(verify_token, challenge), 200
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 403


@integrations_bp.route('/api/v1/webhooks/facebook/lead', methods=['POST'])
def facebook_lead_event():
    payload = request.get_json() or {}
    result = FacebookLeadAdsService.process_lead_webhook(payload)
    if not result.get('ok'):
        return jsonify(result), 400
    return jsonify(result)


@integrations_bp.route('/api/v1/integrations/facebook/auth', methods=['GET'])
@login_required
def facebook_auth_url():
    try:
        auth_url = FacebookLeadAdsService.get_oauth_url(_workspace_id(), _user_id())
        state = _extract_state_from_auth_url(auth_url)
        if not state:
            return jsonify({'error': 'Failed to initialize OAuth state'}), 500
        session['facebook_oauth_state'] = state
        return jsonify({'auth_url': auth_url})
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400


@integrations_bp.route('/api/v1/integrations/facebook/callback', methods=['GET'])
@login_required
def facebook_callback():
    code = request.args.get('code')
    state = request.args.get('state', '')
    if not code or not state:
        return jsonify({'error': 'Missing code/state'}), 400

    valid_state, state_error = _validate_oauth_state('facebook', state)
    if not valid_state:
        return jsonify({'error': state_error}), 400

    try:
        workspace_id, user_id, _nonce = state.split(':', 2)
        workspace_id = int(workspace_id)
        user_id = int(user_id)

        if workspace_id != _workspace_id() or user_id != _user_id():
            return jsonify({'error': 'OAuth state does not match active session'}), 403

        session.pop('facebook_oauth_state', None)
        integration = FacebookLeadAdsService.handle_oauth_callback(code, workspace_id, user_id)
        return jsonify({'success': True, 'integration_id': integration.id})
    except Exception as exc:
        current_app.logger.error('Facebook OAuth callback failed: %s', exc)
        return jsonify({'error': str(exc)}), 400


@integrations_bp.route('/api/v1/integrations/facebook', methods=['DELETE'])
@login_required
def facebook_disconnect():
    ok = FacebookLeadAdsService.disconnect(_workspace_id())
    return jsonify({'success': ok})


@integrations_bp.route('/api/v1/integrations/google-ads/auth', methods=['GET'])
@login_required
def google_ads_auth_url():
    try:
        auth_url = GoogleAdsService.get_oauth_url(_workspace_id(), _user_id())
        state = _extract_state_from_auth_url(auth_url)
        if not state:
            return jsonify({'error': 'Failed to initialize OAuth state'}), 500
        session['google_ads_oauth_state'] = state
        return jsonify({'auth_url': auth_url})
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400


@integrations_bp.route('/api/v1/integrations/google-ads/callback', methods=['GET'])
@login_required
def google_ads_callback():
    code = request.args.get('code')
    state = request.args.get('state', '')
    if not code or not state:
        return jsonify({'error': 'Missing code/state'}), 400

    valid_state, state_error = _validate_oauth_state('google_ads', state)
    if not valid_state:
        return jsonify({'error': state_error}), 400

    try:
        workspace_id, user_id, _nonce = state.split(':', 2)
        workspace_id = int(workspace_id)
        user_id = int(user_id)

        if workspace_id != _workspace_id() or user_id != _user_id():
            return jsonify({'error': 'OAuth state does not match active session'}), 403

        session.pop('google_ads_oauth_state', None)
        integration = GoogleAdsService.handle_oauth_callback(code, workspace_id, user_id)
        return jsonify({'success': True, 'integration_id': integration.id})
    except Exception as exc:
        current_app.logger.error('Google Ads OAuth callback failed: %s', exc)
        return jsonify({'error': str(exc)}), 400


@integrations_bp.route('/api/v1/integrations/google-ads', methods=['DELETE'])
@login_required
def google_ads_disconnect():
    ok = GoogleAdsService.disconnect(_workspace_id(), _user_id())
    return jsonify({'success': ok})
