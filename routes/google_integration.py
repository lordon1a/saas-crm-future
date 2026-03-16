import secrets
import time
from urllib.parse import urlencode

from flask import Blueprint, jsonify, redirect, request, session

from config import Config
from services.google_service import GoogleService


bp = Blueprint('google_integration', __name__)


def _agent_session_required(f):
    from functools import wraps

    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get('user_id') or not session.get('workspace_id'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)

    return wrapped


def _clear_oauth_session_state():
    session.pop('google_oauth_state', None)
    session.pop('google_oauth_workspace_id', None)
    session.pop('google_oauth_user_id', None)
    session.pop('google_oauth_expires_at', None)


@bp.route('/api/settings/google/status', methods=['GET'])
@_agent_session_required
def google_status():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    row = GoogleService.get_active_integration(workspace_id, user_id)
    payload = GoogleService.serialize_integration(row)
    payload['configured'] = GoogleService.is_configured()
    payload['redirect_uri'] = Config.GOOGLE_REDIRECT_URI
    return jsonify(payload), 200


@bp.route('/api/settings/google/connect', methods=['POST'])
@_agent_session_required
def google_connect():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')

    if not GoogleService.is_configured():
        return jsonify({'error': 'Google OAuth is not configured'}), 400

    state = secrets.token_urlsafe(32)
    auth_url, returned_state = GoogleService.generate_authorization_url(state)

    ttl = max(60, int(getattr(Config, 'GOOGLE_OAUTH_STATE_TTL_SECONDS', 600) or 600))
    session['google_oauth_state'] = returned_state
    session['google_oauth_workspace_id'] = workspace_id
    session['google_oauth_user_id'] = user_id
    session['google_oauth_expires_at'] = int(time.time()) + ttl

    return jsonify({'authorization_url': auth_url}), 200


@bp.route('/api/settings/google/disconnect', methods=['DELETE'])
@_agent_session_required
def google_disconnect():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    removed = GoogleService.disconnect(workspace_id, user_id)
    return jsonify({'status': 'disconnected' if removed else 'not_connected'}), 200


@bp.route('/integrations/google/callback', methods=['GET'])
def google_callback():
    if not session.get('user_id') or not session.get('workspace_id'):
        return redirect('/settings?google_error=unauthorized')

    incoming_error = request.args.get('error')
    if incoming_error:
        _clear_oauth_session_state()
        return redirect(f"/settings?{urlencode({'google_error': incoming_error})}")

    state = request.args.get('state', '')
    code = request.args.get('code', '')

    expected_state = session.get('google_oauth_state')
    expected_workspace_id = session.get('google_oauth_workspace_id')
    expected_user_id = session.get('google_oauth_user_id')
    expires_at = session.get('google_oauth_expires_at')

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
        return redirect('/settings?google_error=invalid_state')

    try:
        token_payload = GoogleService.exchange_code_for_tokens(code=code, state=state)
        google_email = GoogleService.fetch_google_email(token_payload.get('access_token'))
        GoogleService.upsert_integration(
            workspace_id=session.get('workspace_id'),
            user_id=session.get('user_id'),
            token_payload=token_payload,
            google_email=google_email,
        )
    except Exception as exc:
        _clear_oauth_session_state()
        return redirect(f"/settings?{urlencode({'google_error': str(exc)[:120]})}")

    _clear_oauth_session_state()
    return redirect('/settings?google_connected=1')



@bp.route('/api/settings/google/sync/gmail', methods=['POST'])
@_agent_session_required
def sync_gmail():
    """Trigger Gmail sync"""
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    
    from services.gmail_sync_service import GmailSyncService
    
    max_results = request.json.get('max_results', 50) if request.json else 50
    result = GmailSyncService.sync_recent_emails(workspace_id, user_id, max_results)
    
    return jsonify(result), 200


@bp.route('/api/settings/google/sync/calendar', methods=['POST'])
@_agent_session_required
def sync_calendar():
    """Trigger Calendar sync"""
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    
    from services.calendar_sync_service import CalendarSyncService
    
    data = request.json or {}
    days_back = data.get('days_back', 7)
    days_forward = data.get('days_forward', 30)
    
    result = CalendarSyncService.sync_recent_events(workspace_id, user_id, days_back, days_forward)
    
    return jsonify(result), 200


@bp.route('/api/settings/google/emails', methods=['GET'])
@_agent_session_required
def get_synced_emails():
    """Get synced emails"""
    workspace_id = session.get('workspace_id')
    
    from models_crm import EmailSync
    
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    emails = EmailSync.query.filter_by(
        workspace_id=workspace_id
    ).order_by(EmailSync.received_at.desc()).limit(limit).offset(offset).all()
    
    return jsonify({
        'emails': [
            {
                'id': e.id,
                'subject': e.subject,
                'from_email': e.from_email,
                'received_at': e.received_at.isoformat() if e.received_at else None,
                'snippet': e.body_snippet,
                'contact_id': e.contact_id,
                'has_attachments': e.has_attachments
            }
            for e in emails
        ],
        'total': EmailSync.query.filter_by(workspace_id=workspace_id).count()
    }), 200


@bp.route('/api/settings/google/events', methods=['GET'])
@_agent_session_required
def get_synced_events():
    """Get synced calendar events"""
    workspace_id = session.get('workspace_id')
    
    from models_crm import CalendarSync
    
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    events = CalendarSync.query.filter_by(
        workspace_id=workspace_id
    ).order_by(CalendarSync.start_time.desc()).limit(limit).offset(offset).all()
    
    return jsonify({
        'events': [
            {
                'id': e.id,
                'summary': e.summary,
                'start_time': e.start_time.isoformat() if e.start_time else None,
                'end_time': e.end_time.isoformat() if e.end_time else None,
                'location': e.location,
                'contact_id': e.contact_id,
                'event_status': e.event_status
            }
            for e in events
        ],
        'total': CalendarSync.query.filter_by(workspace_id=workspace_id).count()
    }), 200



# ============================================================================
# GOOGLE DRIVE ENDPOINTS
# ============================================================================

@bp.route('/api/settings/google/drive/files', methods=['GET'])
@_agent_session_required
def list_drive_files():
    """List files from Google Drive"""
    from services.google_drive_service import GoogleDriveService
    from models_crm import GoogleIntegration
    
    workspace_id = session.get('workspace_id')
    page_token = request.args.get('pageToken')
    search = request.args.get('search', '').strip()
    
    # Get Google integration
    integration = GoogleIntegration.query.filter_by(workspace_id=workspace_id).first()
    if not integration or not integration.access_token:
        return jsonify({'error': 'Google not connected'}), 400
    
    # Decrypt access token
    access_token = GoogleService.decrypt_token(integration.access_token)
    
    # List or search files
    if search:
        files = GoogleDriveService.search_files(access_token, search)
        return jsonify({'files': files, 'nextPageToken': None}), 200
    else:
        result = GoogleDriveService.list_files(access_token, page_token=page_token)
        return jsonify(result), 200


@bp.route('/api/settings/google/drive/attach', methods=['POST'])
@_agent_session_required
def attach_drive_file():
    """Attach a Google Drive file to an entity (deal, task, etc.)"""
    from models_crm import DriveAttachment
    from models import db
    
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json()
    
    drive_file_id = data.get('driveFileId')
    entity_type = data.get('entityType')  # 'deal', 'task', 'contact', 'company'
    entity_id = data.get('entityId')
    file_name = data.get('fileName')
    mime_type = data.get('mimeType')
    file_size = data.get('fileSize')
    thumbnail_url = data.get('thumbnailUrl')
    web_view_link = data.get('webViewLink')
    notes = data.get('notes', '')
    
    if not all([drive_file_id, entity_type, entity_id, file_name]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Check if already attached
    existing = DriveAttachment.query.filter_by(
        workspace_id=workspace_id,
        drive_file_id=drive_file_id,
        entity_type=entity_type,
        entity_id=entity_id
    ).first()
    
    if existing:
        return jsonify({'error': 'File already attached'}), 409
    
    # Create attachment
    attachment = DriveAttachment(
        workspace_id=workspace_id,
        drive_file_id=drive_file_id,
        file_name=file_name,
        mime_type=mime_type,
        file_size=file_size,
        thumbnail_url=thumbnail_url,
        web_view_link=web_view_link,
        entity_type=entity_type,
        entity_id=entity_id,
        attached_by=user_id,
        notes=notes
    )
    
    db.session.add(attachment)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'attachment': {
            'id': attachment.id,
            'fileName': attachment.file_name,
            'mimeType': attachment.mime_type,
            'webViewLink': attachment.web_view_link,
            'attachedAt': attachment.attached_at.isoformat()
        }
    }), 201


@bp.route('/api/settings/google/drive/attachments', methods=['GET'])
@_agent_session_required
def get_drive_attachments():
    """Get Drive attachments for an entity"""
    from models_crm import DriveAttachment
    
    workspace_id = session.get('workspace_id')
    entity_type = request.args.get('entityType')
    entity_id = request.args.get('entityId', type=int)
    
    if not entity_type or not entity_id:
        return jsonify({'error': 'Missing entityType or entityId'}), 400
    
    attachments = DriveAttachment.query.filter_by(
        workspace_id=workspace_id,
        entity_type=entity_type,
        entity_id=entity_id
    ).order_by(DriveAttachment.attached_at.desc()).all()
    
    return jsonify({
        'attachments': [{
            'id': a.id,
            'driveFileId': a.drive_file_id,
            'fileName': a.file_name,
            'mimeType': a.mime_type,
            'fileSize': a.file_size,
            'thumbnailUrl': a.thumbnail_url,
            'webViewLink': a.web_view_link,
            'attachedAt': a.attached_at.isoformat(),
            'notes': a.notes
        } for a in attachments]
    }), 200


@bp.route('/api/settings/google/drive/attachments/<int:attachment_id>', methods=['DELETE'])
@_agent_session_required
def delete_drive_attachment(attachment_id):
    """Delete a Drive attachment"""
    from models_crm import DriveAttachment
    from models import db
    
    workspace_id = session.get('workspace_id')
    
    attachment = DriveAttachment.query.filter_by(
        id=attachment_id,
        workspace_id=workspace_id
    ).first()
    
    if not attachment:
        return jsonify({'error': 'Attachment not found'}), 404
    
    db.session.delete(attachment)
    db.session.commit()
    
    return jsonify({'status': 'deleted'}), 200
