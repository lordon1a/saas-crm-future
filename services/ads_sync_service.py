"""Ads sync/integration services for Facebook Lead Ads and Google Ads conversions."""
import json


class FacebookLeadAdsService:
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
