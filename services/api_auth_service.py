import hmac
import json
import secrets
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from functools import wraps
from hashlib import sha256

from flask import g, jsonify, request

from config import Config
from models import db
from models_crm import APIKey, OAuthClient, OAuthAuthorizationCode, OAuthAccessToken


_RATE_LIMIT_MEMORY_LOCK = threading.Lock()
_RATE_LIMIT_MEMORY_BUCKETS: dict[str, deque[float]] = {}


def _rate_limit_config():
    max_requests = int(getattr(Config, 'PUBLIC_API_RATE_LIMIT_PER_HOUR', 1000) or 1000)
    window_seconds = int(getattr(Config, 'PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS', 3600) or 3600)

    max_requests = max(1, max_requests)
    window_seconds = max(1, window_seconds)
    return max_requests, window_seconds


def _rate_limit_consume(key: str):
    max_requests, window_seconds = _rate_limit_config()
    now = time.time()
    cutoff = now - window_seconds

    with _RATE_LIMIT_MEMORY_LOCK:
        bucket = _RATE_LIMIT_MEMORY_BUCKETS.get(key)
        if bucket is None:
            bucket = deque()
            _RATE_LIMIT_MEMORY_BUCKETS[key] = bucket

        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= max_requests:
            retry_after = max(1, int((bucket[0] + window_seconds) - now))
            return False, retry_after, max_requests, window_seconds

        bucket.append(now)
        return True, None, max_requests, window_seconds


def _rate_limit_response(retry_after: int, max_requests: int, window_seconds: int):
    response = jsonify({
        'error': 'rate_limit_exceeded',
        'message': f'Rate limit exceeded: {max_requests} requests per {window_seconds} seconds',
    })
    response.status_code = 429
    response.headers['Retry-After'] = str(retry_after)
    response.headers['X-RateLimit-Limit'] = str(max_requests)
    response.headers['X-RateLimit-Window-Seconds'] = str(window_seconds)
    return response


def _apply_rate_limit(auth_type: str, workspace_id: int, principal_id: int):
    key = f"{auth_type}:{workspace_id}:{principal_id}"
    allowed, retry_after, max_requests, window_seconds = _rate_limit_consume(key)
    if allowed:
        return None
    return _rate_limit_response(retry_after, max_requests, window_seconds)


class APIAuthService:
    @staticmethod
    def _hash_secret(secret_value: str) -> str:
        return sha256(secret_value.encode('utf-8')).hexdigest()

    @staticmethod
    def _normalize_scopes(scopes) -> str:
        if scopes is None:
            return 'read'
        if isinstance(scopes, str):
            cleaned = [s.strip() for s in scopes.split(',') if s.strip()]
            return ','.join(cleaned) if cleaned else 'read'
        if isinstance(scopes, (list, tuple, set)):
            cleaned = [str(s).strip() for s in scopes if str(s).strip()]
            return ','.join(cleaned) if cleaned else 'read'
        return 'read'

    @staticmethod
    def _has_scope(granted_scopes: str, required_scope: str | None) -> bool:
        if not required_scope:
            return True
        granted = {scope.strip() for scope in (granted_scopes or '').split(',') if scope.strip()}
        return required_scope in granted or 'admin' in granted

    @staticmethod
    def generate_api_key(workspace_id: int, name: str, created_by: int | None = None, scopes=None, expires_at=None):
        secret = f"wcrm_{secrets.token_urlsafe(32)}"
        prefix = secret[:16]
        record = APIKey(
            workspace_id=workspace_id,
            name=name,
            key_prefix=prefix,
            key_hash=APIAuthService._hash_secret(secret),
            scopes=APIAuthService._normalize_scopes(scopes),
            created_by=created_by,
            is_active=True,
            expires_at=expires_at,
        )
        db.session.add(record)
        db.session.commit()
        return record, secret

    @staticmethod
    def validate_api_key(api_key: str, required_scope: str | None = None):
        if not api_key or len(api_key) < 16:
            return None

        key_hash = APIAuthService._hash_secret(api_key)
        record = APIKey.query.filter_by(key_hash=key_hash, is_active=True).first()
        if not record:
            return None

        if record.expires_at and record.expires_at < datetime.utcnow():
            return None

        if not APIAuthService._has_scope(record.scopes, required_scope):
            return None

        record.last_used_at = datetime.utcnow()
        db.session.commit()
        return record

    @staticmethod
    def deactivate_api_key(workspace_id: int, api_key_id: int):
        record = APIKey.query.filter_by(
            id=api_key_id,
            workspace_id=workspace_id,
        ).first()
        if not record:
            return None

        record.is_active = False
        db.session.commit()
        return record

    @staticmethod
    def create_oauth_client(workspace_id: int, name: str, redirect_uris, created_by: int | None = None, scopes=None):
        client_id = f"cli_{secrets.token_urlsafe(20)}"
        client_secret = f"sec_{secrets.token_urlsafe(32)}"

        client = OAuthClient(
            workspace_id=workspace_id,
            name=name,
            client_id=client_id,
            client_secret_hash=APIAuthService._hash_secret(client_secret),
            redirect_uris=json.dumps(redirect_uris or []),
            scopes=APIAuthService._normalize_scopes(scopes),
            created_by=created_by,
            is_active=True,
        )
        db.session.add(client)
        db.session.commit()
        return client, client_secret

    @staticmethod
    def get_oauth_client(client_id: str):
        return OAuthClient.query.filter_by(client_id=client_id, is_active=True).first()

    @staticmethod
    def deactivate_oauth_client(workspace_id: int, client_row_id: int):
        client = OAuthClient.query.filter_by(
            id=client_row_id,
            workspace_id=workspace_id,
        ).first()
        if not client:
            return None, 0

        revoked_count = 0
        now = datetime.utcnow()

        if client.is_active:
            client.is_active = False

        tokens = OAuthAccessToken.query.filter_by(
            client_id=client.id,
        ).filter(OAuthAccessToken.revoked_at.is_(None)).all()

        for token in tokens:
            token.revoked_at = now
            revoked_count += 1

        db.session.commit()
        return client, revoked_count

    @staticmethod
    def validate_oauth_client_secret(client: OAuthClient, client_secret: str) -> bool:
        if not client or not client_secret:
            return False
        return hmac.compare_digest(client.client_secret_hash, APIAuthService._hash_secret(client_secret))

    @staticmethod
    def validate_redirect_uri(client: OAuthClient, redirect_uri: str) -> bool:
        if not client or not redirect_uri:
            return False
        allowed = json.loads(client.redirect_uris or '[]')
        return redirect_uri in allowed

    @staticmethod
    def issue_authorization_code(client: OAuthClient, workspace_id: int, user_id: int, redirect_uri: str, scopes=None):
        raw_code = f"code_{secrets.token_urlsafe(28)}"
        code = OAuthAuthorizationCode(
            workspace_id=workspace_id,
            client_id=client.id,
            user_id=user_id,
            code_hash=APIAuthService._hash_secret(raw_code),
            redirect_uri=redirect_uri,
            scopes=APIAuthService._normalize_scopes(scopes) or client.scopes,
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        )
        db.session.add(code)
        db.session.commit()
        return raw_code

    @staticmethod
    def exchange_authorization_code(client: OAuthClient, raw_code: str, redirect_uri: str):
        if not client or not raw_code or not redirect_uri:
            return None

        code_hash = APIAuthService._hash_secret(raw_code)
        code_row = OAuthAuthorizationCode.query.filter_by(
            client_id=client.id,
            code_hash=code_hash,
            redirect_uri=redirect_uri,
        ).first()

        if not code_row:
            return None
        if code_row.used_at is not None:
            return None
        if code_row.expires_at < datetime.utcnow():
            return None

        raw_token = f"atk_{secrets.token_urlsafe(32)}"
        token_row = OAuthAccessToken(
            workspace_id=code_row.workspace_id,
            client_id=client.id,
            user_id=code_row.user_id,
            token_hash=APIAuthService._hash_secret(raw_token),
            scopes=code_row.scopes,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )

        code_row.used_at = datetime.utcnow()
        db.session.add(token_row)
        db.session.commit()

        return {
            'access_token': raw_token,
            'token_type': 'Bearer',
            'expires_in': 3600,
            'scope': token_row.scopes,
            'workspace_id': token_row.workspace_id,
        }

    @staticmethod
    def validate_oauth_access_token(raw_token: str, required_scope: str | None = None):
        if not raw_token:
            return None

        token_hash = APIAuthService._hash_secret(raw_token)
        token_row = OAuthAccessToken.query.filter_by(token_hash=token_hash).first()
        if not token_row:
            return None
        if token_row.revoked_at is not None:
            return None
        if token_row.expires_at < datetime.utcnow():
            return None
        if not APIAuthService._has_scope(token_row.scopes, required_scope):
            return None

        return token_row

    @staticmethod
    def revoke_oauth_access_token(client: OAuthClient, raw_token: str):
        if not client or not raw_token:
            return False

        token_hash = APIAuthService._hash_secret(raw_token)
        token_row = OAuthAccessToken.query.filter_by(
            client_id=client.id,
            token_hash=token_hash,
        ).first()

        if not token_row:
            return False

        if token_row.revoked_at is None:
            token_row.revoked_at = datetime.utcnow()
            db.session.commit()

        return True


def _extract_bearer_token() -> str | None:
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    return auth_header.replace('Bearer ', '', 1).strip()


def api_auth_required(required_scope: str | None = 'read'):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            api_key_value = request.headers.get('X-API-Key', '').strip()
            if api_key_value:
                api_key = APIAuthService.validate_api_key(api_key_value, required_scope)
                if api_key:
                    rate_limited = _apply_rate_limit('api_key', api_key.workspace_id, api_key.id)
                    if rate_limited:
                        return rate_limited

                    g.api_auth_type = 'api_key'
                    g.api_workspace_id = api_key.workspace_id
                    g.api_principal_id = api_key.id
                    g.api_scopes = api_key.scopes
                    return f(*args, **kwargs)

            bearer = _extract_bearer_token()
            if bearer:
                token = APIAuthService.validate_oauth_access_token(bearer, required_scope)
                if token:
                    rate_limited = _apply_rate_limit('oauth_token', token.workspace_id, token.id)
                    if rate_limited:
                        return rate_limited

                    g.api_auth_type = 'oauth_token'
                    g.api_workspace_id = token.workspace_id
                    g.api_principal_id = token.user_id
                    g.api_scopes = token.scopes
                    return f(*args, **kwargs)

            return jsonify({'error': 'Invalid API credentials'}), 401

        return wrapped

    return decorator
