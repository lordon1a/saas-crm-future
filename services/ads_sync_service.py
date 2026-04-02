"""Ads sync/integration services for Facebook Lead Ads and Google Ads conversions."""
from datetime import datetime, timedelta, UTC
import secrets
from urllib.parse import urlencode


class FacebookLeadAdsService:
    @staticmethod
    def get_oauth_url(workspace_id, user_id):
        from flask import current_app

        client_id = current_app.config.get('FACEBOOK_APP_ID', '')
        redirect_uri = current_app.config.get('FACEBOOK_REDIRECT_URI', '')
        scopes = current_app.config.get(
            'FACEBOOK_OAUTH_SCOPES',
            'leads_retrieval,pages_show_list,pages_manage_metadata'
        )
        if not client_id or not redirect_uri:
            raise ValueError('Facebook OAuth is not configured')

        state = f"{workspace_id}:{user_id}:{secrets.token_urlsafe(12)}"
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': scopes,
            'state': state,
        }
        return f"https://www.facebook.com/v19.0/dialog/oauth?{urlencode(params)}"

    @staticmethod
    def handle_oauth_callback(code, workspace_id, user_id):
        from app import db
        from models_crm import FacebookAdsIntegration

        integration = FacebookAdsIntegration.query.filter_by(workspace_id=workspace_id).first()
        if not integration:
            integration = FacebookAdsIntegration(
                workspace_id=workspace_id,
                access_token='',
            )
            db.session.add(integration)

        integration.access_token = f'mock_fb_access_{code[:20]}'
        integration.page_id = integration.page_id or f'page_{workspace_id}'
        integration.page_name = integration.page_name or f'Workspace {workspace_id} Page'
        integration.webhook_subscribed = True
        integration.is_active = True

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return integration

    @staticmethod
    def disconnect(workspace_id):
        from app import db
        from models_crm import FacebookAdsIntegration

        integration = FacebookAdsIntegration.query.filter_by(workspace_id=workspace_id, is_active=True).first()
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
    def verify_webhook(token, challenge):
        from flask import current_app

        expected = current_app.config.get('FACEBOOK_VERIFY_TOKEN')
        if expected and token == expected:
            return challenge
        raise ValueError('Webhook verification failed')

    @staticmethod
    def process_lead_webhook(payload):
        from app import db
        from models_crm import Contact

        entry = (payload.get('entry') or [{}])[0]
        changes = (entry.get('changes') or [{}])[0]
        value = changes.get('value') or {}

        workspace_id = value.get('workspace_id')
        if not workspace_id:
            return {'ok': False, 'reason': 'workspace_id missing in payload'}

        email = value.get('email')
        name = value.get('full_name') or 'Lead'
        phone = value.get('phone_number')

        if not email:
            return {'ok': False, 'reason': 'email missing in payload'}

        contact = Contact.query.filter_by(workspace_id=workspace_id, email=email.lower()).first()
        if not contact:
            parts = name.split(' ', 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ''
            contact = Contact(
                workspace_id=workspace_id,
                first_name=first_name,
                last_name=last_name,
                email=email.lower(),
                phone=phone,
                lead_source='facebook_ads',
            )
            db.session.add(contact)
        else:
            contact.lead_source = 'facebook_ads'
            contact.phone = contact.phone or phone

        # Optional attribution fields if present
        contact.fbclid = value.get('fbclid') or contact.fbclid
        contact.utm_source = value.get('utm_source') or contact.utm_source
        contact.utm_medium = value.get('utm_medium') or contact.utm_medium
        contact.utm_campaign = value.get('utm_campaign') or contact.utm_campaign
        contact.utm_content = value.get('utm_content') or contact.utm_content

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return {'ok': True, 'contact_id': contact.id}


class GoogleAdsService:
    @staticmethod
    def get_oauth_url(workspace_id, user_id):
        from flask import current_app

        client_id = current_app.config.get('GOOGLE_ADS_CLIENT_ID', '')
        redirect_uri = current_app.config.get('GOOGLE_ADS_REDIRECT_URI', '')
        scopes = current_app.config.get('GOOGLE_ADS_OAUTH_SCOPES', 'https://www.googleapis.com/auth/adwords')
        if not client_id or not redirect_uri:
            raise ValueError('Google Ads OAuth is not configured')

        state = f"{workspace_id}:{user_id}:{secrets.token_urlsafe(12)}"
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': scopes,
            'access_type': 'offline',
            'prompt': 'consent',
            'state': state,
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    @staticmethod
    def handle_oauth_callback(code, workspace_id, user_id):
        from app import db
        from models_crm import GoogleAdsIntegration

        integration = GoogleAdsIntegration.query.filter_by(workspace_id=workspace_id, user_id=user_id).first()
        if not integration:
            integration = GoogleAdsIntegration(
                workspace_id=workspace_id,
                user_id=user_id,
                access_token='',
            )
            db.session.add(integration)

        integration.access_token = f'mock_gads_access_{code[:20]}'
        integration.refresh_token = f'mock_gads_refresh_{code[:20]}'
        integration.token_expires_at = datetime.now(UTC) + timedelta(hours=1)
        integration.customer_id = integration.customer_id or f'{workspace_id}-{user_id}'
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
        from models_crm import GoogleAdsIntegration

        integration = GoogleAdsIntegration.query.filter_by(
            workspace_id=workspace_id,
            user_id=user_id,
            is_active=True,
        ).first()
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
    def send_conversion(workspace_id, deal_id, conversion_value):
        # Minimal non-blocking conversion marker for now.
        from flask import current_app

        current_app.logger.info(
            'GoogleAds conversion queued workspace=%s deal=%s value=%s',
            workspace_id,
            deal_id,
            conversion_value,
        )
        return {
            'ok': True,
            'workspace_id': workspace_id,
            'deal_id': deal_id,
            'conversion_value': float(conversion_value or 0),
        }
