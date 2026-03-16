import base64
import hashlib
import json
from datetime import datetime

import requests
from cryptography.fernet import Fernet

from config import Config
from models import db
from models_crm import GoogleIntegration


class GoogleService:
    @staticmethod
    def is_configured() -> bool:
        return bool(Config.GOOGLE_CLIENT_ID and Config.GOOGLE_CLIENT_SECRET and Config.GOOGLE_REDIRECT_URI)

    @staticmethod
    def _validate_configuration():
        if not GoogleService.is_configured():
            raise ValueError('Google OAuth is not configured. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI.')

    @staticmethod
    def _fernet_instance() -> Fernet:
        configured_key = Config.GOOGLE_TOKEN_ENCRYPTION_KEY
        if configured_key:
            key_material = configured_key.encode('utf-8')
        else:
            key_material = Config.SECRET_KEY.encode('utf-8')

        digest = hashlib.sha256(key_material).digest()
        fernet_key = base64.urlsafe_b64encode(digest)
        return Fernet(fernet_key)

    @staticmethod
    def _encrypt_value(value: str | None) -> str | None:
        if not value:
            return None
        token = GoogleService._fernet_instance().encrypt(value.encode('utf-8'))
        return token.decode('utf-8')

    @staticmethod
    def _decrypt_value(value: str | None) -> str | None:
        if not value:
            return None
        raw = GoogleService._fernet_instance().decrypt(value.encode('utf-8'))
        return raw.decode('utf-8')

    @staticmethod
    def _oauth_client_config() -> dict:
        GoogleService._validate_configuration()
        return {
            'web': {
                'client_id': Config.GOOGLE_CLIENT_ID,
                'client_secret': Config.GOOGLE_CLIENT_SECRET,
                'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'redirect_uris': [Config.GOOGLE_REDIRECT_URI],
            }
        }

    @staticmethod
    def _create_oauth_flow(state: str | None = None):
        try:
            from google_auth_oauthlib.flow import Flow
        except ImportError as exc:
            raise RuntimeError('google-auth-oauthlib is not installed') from exc

        flow = Flow.from_client_config(
            GoogleService._oauth_client_config(),
            scopes=Config.GOOGLE_OAUTH_SCOPES,
            state=state,
        )
        flow.redirect_uri = Config.GOOGLE_REDIRECT_URI
        return flow

    @staticmethod
    def generate_authorization_url(state: str):
        flow = GoogleService._create_oauth_flow(state=state)
        authorization_url, returned_state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
        )
        return authorization_url, returned_state

    @staticmethod
    def exchange_code_for_tokens(code: str, state: str):
        if not code:
            raise ValueError('Authorization code is required')

        flow = GoogleService._create_oauth_flow(state=state)
        flow.fetch_token(code=code)
        credentials = flow.credentials

        return {
            'access_token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_expires_at': credentials.expiry,
            'scopes': list(credentials.scopes or Config.GOOGLE_OAUTH_SCOPES),
        }

    @staticmethod
    def fetch_google_email(access_token: str | None) -> str | None:
        if not access_token:
            return None

        try:
            response = requests.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=10,
            )
            if response.ok:
                payload = response.json()
                return payload.get('email')
        except Exception:
            return None
        return None

    @staticmethod
    def upsert_integration(workspace_id: int, user_id: int, token_payload: dict, google_email: str | None = None):
        row = GoogleIntegration.query.filter_by(workspace_id=workspace_id, user_id=user_id).first()
        if not row:
            row = GoogleIntegration(workspace_id=workspace_id, user_id=user_id, access_token='')
            db.session.add(row)

        access_token = token_payload.get('access_token')
        refresh_token = token_payload.get('refresh_token')
        token_expires_at = token_payload.get('token_expires_at')
        scopes = token_payload.get('scopes') or []

        if not access_token:
            raise ValueError('Google access token missing')

        row.access_token = GoogleService._encrypt_value(access_token)
        if refresh_token:
            row.refresh_token = GoogleService._encrypt_value(refresh_token)

        if isinstance(token_expires_at, datetime):
            row.token_expires_at = token_expires_at.replace(tzinfo=None)
        else:
            row.token_expires_at = None

        row.scopes = json.dumps(scopes)
        row.google_email = (google_email or row.google_email or '').strip() or None
        row.is_active = True

        db.session.commit()
        return row

    @staticmethod
    def get_active_integration(workspace_id: int, user_id: int):
        return GoogleIntegration.query.filter_by(
            workspace_id=workspace_id,
            user_id=user_id,
            is_active=True,
        ).first()

    @staticmethod
    def serialize_integration(row: GoogleIntegration | None):
        if not row:
            return {
                'connected': False,
                'google_email': None,
                'token_expires_at': None,
                'scopes': [],
            }

        try:
            scopes = json.loads(row.scopes or '[]')
        except json.JSONDecodeError:
            scopes = []

        now = datetime.utcnow()
        is_expired = bool(row.token_expires_at and row.token_expires_at <= now)

        return {
            'connected': bool(row.is_active),
            'google_email': row.google_email,
            'token_expires_at': row.token_expires_at.isoformat() if row.token_expires_at else None,
            'scopes': scopes if isinstance(scopes, list) else [],
            'is_expired': is_expired,
            'updated_at': row.updated_at.isoformat() if row.updated_at else None,
        }

    @staticmethod
    def disconnect(workspace_id: int, user_id: int) -> bool:
        row = GoogleIntegration.query.filter_by(workspace_id=workspace_id, user_id=user_id, is_active=True).first()
        if not row:
            return False

        row.is_active = False
        row.access_token = ''
        row.refresh_token = None
        row.token_expires_at = None
        db.session.commit()
        return True

    @staticmethod
    def get_decrypted_tokens(row: GoogleIntegration):
        return {
            'access_token': GoogleService._decrypt_value(row.access_token),
            'refresh_token': GoogleService._decrypt_value(row.refresh_token),
            'token_expires_at': row.token_expires_at,
        }