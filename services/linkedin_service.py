"""LinkedIn integration and enrichment service."""
from datetime import datetime, timedelta
import secrets
from urllib.parse import urlencode


class LinkedInService:
    @staticmethod
    def get_oauth_url(workspace_id, user_id):
        from flask import current_app

        client_id = current_app.config.get('LINKEDIN_CLIENT_ID', '')
        redirect_uri = current_app.config.get('LINKEDIN_REDIRECT_URI', '')
        if not client_id or not redirect_uri:
            raise ValueError('LinkedIn OAuth is not configured')

        state = f"{workspace_id}:{user_id}:{secrets.token_urlsafe(12)}"
        params = {
            'response_type': 'code',
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'scope': 'r_liteprofile r_emailaddress',
            'state': state,
        }
        return f"https://www.linkedin.com/oauth/v2/authorization?{urlencode(params)}"

    @staticmethod
    def handle_oauth_callback(code, workspace_id, user_id):
        from app import db
        from models_crm import LinkedInIntegration

        integration = LinkedInIntegration.query.filter_by(workspace_id=workspace_id, user_id=user_id).first()
        if not integration:
            integration = LinkedInIntegration(workspace_id=workspace_id, user_id=user_id, access_token='')
            db.session.add(integration)

        integration.access_token = f'mock_access_{code[:12]}'
        integration.refresh_token = f'mock_refresh_{code[:12]}'
        integration.token_expires_at = datetime.utcnow() + timedelta(hours=1)
        integration.linkedin_member_id = f'ln_{user_id}'
        integration.is_active = True

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return integration

    @staticmethod
    def enrich_contact(workspace_id, contact_id):
        from app import db
        from models_crm import Contact

        contact = Contact.query.filter_by(id=contact_id, workspace_id=workspace_id, is_deleted=False).first()
        if not contact:
            raise ValueError('Contact not found')

        if not contact.linkedin_url and contact.first_name:
            slug_last = (contact.last_name or '').replace(' ', '-').lower()
            slug_first = (contact.first_name or '').replace(' ', '-').lower()
            contact.linkedin_url = f'https://www.linkedin.com/in/{slug_first}-{slug_last}'.rstrip('-')

        contact.linkedin_enriched_at = datetime.utcnow()

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return {
            'contact_id': contact.id,
            'linkedin_url': contact.linkedin_url,
            'linkedin_enriched_at': contact.linkedin_enriched_at.isoformat() if contact.linkedin_enriched_at else None,
        }
