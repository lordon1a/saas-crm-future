"""Audit logging service and decorator utilities."""
import json
import logging
from functools import wraps

from flask import request, session

from models import db
from models_crm import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    """Security audit helpers."""

    @staticmethod
    def log_event(workspace_id, user_id, action, entity_type, entity_id=None, before_data=None, after_data=None, metadata=None):
        """Persist an audit log entry."""
        try:
            row = AuditLog(
                workspace_id=workspace_id,
                user_id=user_id,
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id is not None else None,
                ip_address=request.remote_addr if request else None,
                user_agent=(request.headers.get('User-Agent') or '')[:500] if request else None,
                before_data=json.dumps(before_data, ensure_ascii=False) if before_data is not None else None,
                after_data=json.dumps(after_data, ensure_ascii=False) if after_data is not None else None,
                metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
            )
            db.session.add(row)
            db.session.commit()
            return row
        except Exception as exc:
            db.session.rollback()
            logger.error('Failed to persist audit log: %s', exc)
            return None

    @staticmethod
    def audited(action, entity_type):
        """Decorator to auto-log successful endpoint calls."""
        def decorator(func):
            @wraps(func)
            def wrapped(*args, **kwargs):
                response = func(*args, **kwargs)
                status_code = None
                if isinstance(response, tuple) and len(response) >= 2:
                    status_code = response[1]
                elif hasattr(response, 'status_code'):
                    status_code = response.status_code

                if status_code is None or int(status_code) < 400:
                    AuditService.log_event(
                        workspace_id=session.get('workspace_id'),
                        user_id=session.get('user_id'),
                        action=action,
                        entity_type=entity_type,
                        entity_id=kwargs.get('user_id') or kwargs.get('id'),
                        metadata={'endpoint': request.path, 'method': request.method},
                    )
                return response

            return wrapped

        return decorator
