"""Zoom integration service (OAuth and meeting creation)."""
from datetime import datetime, timedelta
import secrets
from urllib.parse import urlencode


class ZoomService:
    @staticmethod
    def get_oauth_url(workspace_id, user_id):
        from flask import current_app

        client_id = current_app.config.get('ZOOM_CLIENT_ID', '')
        redirect_uri = current_app.config.get('ZOOM_REDIRECT_URI', '')
        if not client_id or not redirect_uri:
            raise ValueError('Zoom OAuth is not configured')

        state = f"{workspace_id}:{user_id}:{secrets.token_urlsafe(12)}"
        params = {
            'response_type': 'code',
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'state': state,
        }
        return f"https://zoom.us/oauth/authorize?{urlencode(params)}"

    @staticmethod
    def handle_oauth_callback(code, workspace_id, user_id):
        # Token exchange is mocked for now unless backend credentials are configured.
        from app import db
        from models_crm import ZoomIntegration

        integration = ZoomIntegration.query.filter_by(workspace_id=workspace_id, user_id=user_id).first()
        if not integration:
            integration = ZoomIntegration(workspace_id=workspace_id, user_id=user_id, access_token='')
            db.session.add(integration)

        integration.access_token = f'mock_access_{code[:12]}'
        integration.refresh_token = f'mock_refresh_{code[:12]}'
        integration.token_expires_at = datetime.utcnow() + timedelta(hours=1)
        integration.zoom_user_id = f'user_{user_id}'
        integration.zoom_email = None
        integration.is_active = True

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return integration

    @staticmethod
    def disconnect(workspace_id, user_id):
        from app import db
        from models_crm import ZoomIntegration

        integration = ZoomIntegration.query.filter_by(workspace_id=workspace_id, user_id=user_id).first()
        if not integration:
            return False

        integration.is_active = False
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        return True

    @staticmethod
    def create_meeting(workspace_id, user_id, topic, start_time, duration_minutes):
        from models_crm import ZoomIntegration

        integration = ZoomIntegration.query.filter_by(
            workspace_id=workspace_id,
            user_id=user_id,
            is_active=True,
        ).first()
        if not integration:
            raise ValueError('Zoom integration is not connected')

        meeting_id = secrets.token_hex(6)
        join_url = f"https://zoom.us/j/{meeting_id}?pwd={secrets.token_urlsafe(8)}"
        return {
            'zoom_meeting_id': meeting_id,
            'zoom_join_url': join_url,
            'topic': topic,
            'start_time': start_time.isoformat(),
            'duration_minutes': duration_minutes,
        }

    @staticmethod
    def handle_recording_webhook(payload):
        # Placeholder handler for webhook acknowledgements.
        return {
            'ok': True,
            'meeting_id': payload.get('payload', {}).get('object', {}).get('id')
        }
