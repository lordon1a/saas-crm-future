import hmac
import json
import secrets
import time
from datetime import datetime, timedelta
from hashlib import sha256
from urllib.parse import urlparse

import requests

from config import Config
from models import db
from models_crm import WebhookDelivery, WebhookSubscription


class WebhookService:
    SUPPORTED_EVENTS = {
        'deal.created',
        'deal.updated',
        'task.completed',
        'contact.created',
    }

    @staticmethod
    def _normalize_event_types(event_types):
        if isinstance(event_types, str):
            items = [value.strip() for value in event_types.split(',') if value.strip()]
        elif isinstance(event_types, (list, tuple, set)):
            items = [str(value).strip() for value in event_types if str(value).strip()]
        else:
            items = []

        filtered = [value for value in items if value in WebhookService.SUPPORTED_EVENTS]
        unique = sorted(set(filtered))
        return unique

    @staticmethod
    def _is_valid_target_url(target_url: str) -> bool:
        if not target_url or not isinstance(target_url, str):
            return False

        parsed = urlparse(target_url.strip())
        if parsed.scheme not in {'http', 'https'}:
            return False
        if not parsed.netloc:
            return False
        return True

    @staticmethod
    def _generate_secret() -> str:
        return f"whsec_{secrets.token_urlsafe(32)}"

    @staticmethod
    def _serialize_subscription(subscription: WebhookSubscription):
        return {
            'id': subscription.id,
            'name': subscription.name,
            'target_url': subscription.target_url,
            'event_types': [item for item in (subscription.event_types or '').split(',') if item],
            'is_active': subscription.is_active,
            'created_by': subscription.created_by,
            'created_at': subscription.created_at.isoformat() if subscription.created_at else None,
            'updated_at': subscription.updated_at.isoformat() if subscription.updated_at else None,
        }

    @staticmethod
    def _serialize_delivery(delivery: WebhookDelivery):
        return {
            'id': delivery.id,
            'subscription_id': delivery.subscription_id,
            'event_type': delivery.event_type,
            'status': delivery.status,
            'attempt_count': delivery.attempt_count,
            'max_attempts': delivery.max_attempts,
            'response_status_code': delivery.response_status_code,
            'response_body': delivery.response_body,
            'next_retry_at': delivery.next_retry_at.isoformat() if delivery.next_retry_at else None,
            'delivered_at': delivery.delivered_at.isoformat() if delivery.delivered_at else None,
            'created_at': delivery.created_at.isoformat() if delivery.created_at else None,
            'updated_at': delivery.updated_at.isoformat() if delivery.updated_at else None,
        }

    @staticmethod
    def create_subscription(workspace_id: int, name: str, target_url: str, event_types, created_by: int | None = None):
        normalized_events = WebhookService._normalize_event_types(event_types)
        if not normalized_events:
            raise ValueError('event_types must include at least one supported event')

        if not WebhookService._is_valid_target_url(target_url):
            raise ValueError('target_url must be a valid http(s) URL')

        subscription = WebhookSubscription(
            workspace_id=workspace_id,
            name=name.strip(),
            target_url=target_url.strip(),
            event_types=','.join(normalized_events),
            secret=WebhookService._generate_secret(),
            is_active=True,
            created_by=created_by,
        )
        db.session.add(subscription)
        db.session.commit()
        return subscription

    @staticmethod
    def list_subscriptions(workspace_id: int):
        return WebhookSubscription.query.filter_by(
            workspace_id=workspace_id
        ).order_by(WebhookSubscription.created_at.desc()).all()

    @staticmethod
    def get_subscription(workspace_id: int, subscription_id: int):
        return WebhookSubscription.query.filter_by(
            id=subscription_id,
            workspace_id=workspace_id,
        ).first()

    @staticmethod
    def update_subscription(subscription: WebhookSubscription, **kwargs):
        if 'name' in kwargs and kwargs['name'] is not None:
            name = str(kwargs['name']).strip()
            if not name:
                raise ValueError('name cannot be empty')
            subscription.name = name

        if 'target_url' in kwargs and kwargs['target_url'] is not None:
            target_url = str(kwargs['target_url']).strip()
            if not WebhookService._is_valid_target_url(target_url):
                raise ValueError('target_url must be a valid http(s) URL')
            subscription.target_url = target_url

        if 'event_types' in kwargs and kwargs['event_types'] is not None:
            normalized_events = WebhookService._normalize_event_types(kwargs['event_types'])
            if not normalized_events:
                raise ValueError('event_types must include at least one supported event')
            subscription.event_types = ','.join(normalized_events)

        if 'is_active' in kwargs and kwargs['is_active'] is not None:
            subscription.is_active = bool(kwargs['is_active'])

        if kwargs.get('rotate_secret'):
            subscription.secret = WebhookService._generate_secret()

        db.session.commit()
        return subscription

    @staticmethod
    def delete_subscription(subscription: WebhookSubscription):
        db.session.delete(subscription)
        db.session.commit()

    @staticmethod
    def list_deliveries(workspace_id: int, subscription_id: int, limit: int = 50):
        limit = max(1, min(200, int(limit)))
        rows = WebhookDelivery.query.filter_by(
            workspace_id=workspace_id,
            subscription_id=subscription_id,
        ).order_by(WebhookDelivery.created_at.desc()).limit(limit).all()
        return rows

    @staticmethod
    def _sign_payload(secret: str, payload_json: str) -> str:
        digest = hmac.new(secret.encode('utf-8'), payload_json.encode('utf-8'), sha256).hexdigest()
        return f'sha256={digest}'

    @staticmethod
    def _delivery_request_headers(signature: str):
        return {
            'Content-Type': 'application/json',
            Config.WEBHOOK_SIGNATURE_HEADER: signature,
            'User-Agent': 'WhatsAppCRM-Webhook/1.0',
        }

    @staticmethod
    def _deliver_with_retry(subscription: WebhookSubscription, event_type: str, payload: dict):
        timeout = max(1, int(getattr(Config, 'WEBHOOK_TIMEOUT_SECONDS', 10) or 10))
        max_attempts = max(1, int(getattr(Config, 'WEBHOOK_RETRY_ATTEMPTS', 3) or 3))
        base_seconds = max(1, int(getattr(Config, 'WEBHOOK_RETRY_BASE_SECONDS', 1) or 1))

        payload_json = json.dumps(payload, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
        signature = WebhookService._sign_payload(subscription.secret, payload_json)

        delivery = WebhookDelivery(
            subscription_id=subscription.id,
            workspace_id=subscription.workspace_id,
            event_type=event_type,
            status='pending',
            payload=payload_json,
            signature=signature,
            max_attempts=max_attempts,
        )
        db.session.add(delivery)
        db.session.commit()

        for attempt in range(1, max_attempts + 1):
            delivery.attempt_count = attempt
            try:
                response = requests.post(
                    subscription.target_url,
                    data=payload_json.encode('utf-8'),
                    headers=WebhookService._delivery_request_headers(signature),
                    timeout=timeout,
                )
                delivery.response_status_code = response.status_code
                delivery.response_body = (response.text or '')[:4000]

                if 200 <= response.status_code < 300:
                    delivery.status = 'success'
                    delivery.delivered_at = datetime.utcnow()
                    delivery.next_retry_at = None
                    db.session.commit()
                    return delivery

            except Exception as exc:
                delivery.response_status_code = None
                delivery.response_body = str(exc)[:4000]

            if attempt < max_attempts:
                backoff_seconds = base_seconds * (2 ** (attempt - 1))
                delivery.next_retry_at = datetime.utcnow() + timedelta(seconds=backoff_seconds)
                delivery.status = 'pending'
                db.session.commit()
                time.sleep(backoff_seconds)
            else:
                delivery.status = 'failed'
                delivery.next_retry_at = None
                db.session.commit()

        return delivery

    @staticmethod
    def dispatch_event(workspace_id: int, event_type: str, payload: dict):
        if event_type not in WebhookService.SUPPORTED_EVENTS:
            return []

        subscriptions = WebhookSubscription.query.filter_by(
            workspace_id=workspace_id,
            is_active=True,
        ).all()

        matched = []
        for subscription in subscriptions:
            events = {item for item in (subscription.event_types or '').split(',') if item}
            if event_type not in events:
                continue

            envelope = {
                'event': event_type,
                'workspace_id': workspace_id,
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'data': payload or {},
            }
            delivery = WebhookService._deliver_with_retry(subscription, event_type, envelope)
            matched.append(delivery)

        return matched

    @staticmethod
    def trigger_test_delivery(workspace_id: int, subscription: WebhookSubscription):
        payload = {
            'event': 'webhook.test',
            'workspace_id': workspace_id,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'data': {
                'subscription_id': subscription.id,
                'message': 'Test webhook delivery from WhatsApp CRM',
            },
        }
        return WebhookService._deliver_with_retry(subscription, 'webhook.test', payload)

    @staticmethod
    def serialize_subscription(subscription: WebhookSubscription):
        return WebhookService._serialize_subscription(subscription)

    @staticmethod
    def serialize_delivery(delivery: WebhookDelivery):
        return WebhookService._serialize_delivery(delivery)
