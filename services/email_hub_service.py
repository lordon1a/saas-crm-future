import json
import logging
import re
import smtplib
from datetime import datetime
from email.message import EmailMessage

from jinja2 import Template

from config import Config
from models import Conversation, Customer, Message, db
from models_crm import (
    Activity,
    EmailSendQueue,
    EmailSequence,
    EmailSequenceStep,
    EmailSync,
    EmailTemplate,
    OutboundEmail,
)
from services.email_tracking_service import EmailTrackingService

logger = logging.getLogger(__name__)

_VARIABLE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


class BaseEmailProvider:
    name = 'base'

    def send(self, to_email, subject, body_text, body_html):
        raise NotImplementedError


class SMTPEmailProvider(BaseEmailProvider):
    name = 'smtp'

    def send(self, to_email, subject, body_text, body_html):
        if not Config.SMTP_HOST or not Config.SMTP_FROM_EMAIL:
            raise ValueError('SMTP is not configured')

        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = Config.SMTP_FROM_EMAIL
        msg['To'] = to_email
        msg.set_content(body_text or '')
        if body_html:
            msg.add_alternative(body_html, subtype='html')

        with smtplib.SMTP(host=Config.SMTP_HOST, port=int(Config.SMTP_PORT), timeout=15) as smtp:
            if Config.SMTP_TLS:
                smtp.starttls()
            if Config.SMTP_USER:
                smtp.login(Config.SMTP_USER, Config.SMTP_PASSWORD or '')
            smtp.send_message(msg)

        # SMTP does not guarantee a provider message id in this flow.
        return None


class LogEmailProvider(BaseEmailProvider):
    name = 'log'

    def send(self, to_email, subject, body_text, body_html):
        logger.info('LogEmailProvider send to=%s subject=%s', to_email, subject)
        return f'log-{int(datetime.utcnow().timestamp())}'


class EmailHubService:
    @staticmethod
    def _provider():
        provider_name = (getattr(Config, 'EMAIL_PROVIDER', '') or '').strip().lower()
        if provider_name == 'log':
            return LogEmailProvider()
        return SMTPEmailProvider()

    @staticmethod
    def extract_variables(template_text):
        return sorted(set(_VARIABLE_PATTERN.findall(template_text or '')))

    @staticmethod
    def validate_variables(template_text, variables):
        required = EmailHubService.extract_variables(template_text)
        provided = set((variables or {}).keys())
        missing = [name for name in required if name not in provided]
        if missing:
            raise ValueError('Missing template variables: ' + ', '.join(missing))
        return required

    @staticmethod
    def render_template_text(template_text, variables):
        EmailHubService.validate_variables(template_text, variables)
        return Template(template_text or '').render(**(variables or {}))

    @staticmethod
    def create_template(workspace_id, user_id, name, subject_template, body_template):
        if not name:
            raise ValueError('Template name is required')
        if not subject_template:
            raise ValueError('Template subject is required')
        if not body_template:
            raise ValueError('Template body is required')

        variables = sorted(
            set(EmailHubService.extract_variables(subject_template))
            | set(EmailHubService.extract_variables(body_template))
        )

        row = EmailTemplate(
            workspace_id=workspace_id,
            name=name.strip(),
            subject_template=subject_template,
            body_template=body_template,
            variables_json=json.dumps(variables),
            created_by=user_id,
        )
        db.session.add(row)
        db.session.commit()
        return row

    @staticmethod
    def list_templates(workspace_id):
        rows = EmailTemplate.query.filter_by(workspace_id=workspace_id).order_by(EmailTemplate.created_at.desc()).all()
        payload = []
        for row in rows:
            try:
                variables = json.loads(row.variables_json or '[]')
            except Exception:
                variables = []
            payload.append({
                'id': row.id,
                'name': row.name,
                'subject_template': row.subject_template,
                'body_template': row.body_template,
                'variables': variables,
                'is_active': bool(row.is_active),
                'created_at': row.created_at.isoformat() if row.created_at else None,
            })
        return payload

    @staticmethod
    def create_sequence(workspace_id, user_id, name, description, steps):
        if not name:
            raise ValueError('Sequence name is required')

        sequence = EmailSequence(
            workspace_id=workspace_id,
            name=name.strip(),
            description=(description or '').strip() or None,
            created_by=user_id,
        )
        db.session.add(sequence)
        db.session.flush()

        for index, step in enumerate(steps or [], start=1):
            row = EmailSequenceStep(
                sequence_id=sequence.id,
                step_order=int(step.get('step_order') or index),
                delay_hours=max(0, int(step.get('delay_hours') or 0)),
                template_id=step.get('template_id'),
                subject_override=step.get('subject_override'),
                body_override=step.get('body_override'),
            )
            db.session.add(row)

        db.session.commit()
        return sequence

    @staticmethod
    def list_sequences(workspace_id):
        rows = EmailSequence.query.filter_by(workspace_id=workspace_id).order_by(EmailSequence.created_at.desc()).all()
        payload = []
        for row in rows:
            steps = sorted(row.steps, key=lambda s: (s.step_order, s.id))
            payload.append({
                'id': row.id,
                'name': row.name,
                'description': row.description,
                'is_active': bool(row.is_active),
                'steps': [
                    {
                        'id': s.id,
                        'step_order': s.step_order,
                        'delay_hours': s.delay_hours,
                        'template_id': s.template_id,
                        'subject_override': s.subject_override,
                        'body_override': s.body_override,
                    }
                    for s in steps
                ],
            })
        return payload

    @staticmethod
    def queue_outbound_email(
        workspace_id,
        user_id,
        to_email,
        subject,
        body_text,
        body_html,
        contact_id=None,
        company_id=None,
        deal_id=None,
    ):
        if not to_email:
            raise ValueError('Recipient email is required')
        if not subject:
            raise ValueError('Email subject is required')

        provider = EmailHubService._provider()

        outbound = OutboundEmail(
            workspace_id=workspace_id,
            user_id=user_id,
            contact_id=contact_id,
            company_id=company_id,
            deal_id=deal_id,
            to_email=to_email.strip().lower(),
            subject=subject.strip(),
            body_text=body_text,
            body_html=body_html,
            provider=provider.name,
            status='queued',
        )
        db.session.add(outbound)
        db.session.flush()

        payload = {
            'to_email': outbound.to_email,
            'subject': outbound.subject,
            'body_text': outbound.body_text,
            'body_html': outbound.body_html,
        }
        queue_row = EmailSendQueue(
            workspace_id=workspace_id,
            outbound_email_id=outbound.id,
            provider=provider.name,
            status='queued',
            payload_json=json.dumps(payload),
        )
        db.session.add(queue_row)
        db.session.commit()

        return EmailHubService.process_queue_item(queue_row.id)

    @staticmethod
    def process_queue_item(queue_id):
        queue_row = EmailSendQueue.query.get(queue_id)
        if not queue_row:
            raise ValueError('Queue item not found')

        outbound = queue_row.outbound_email
        provider = EmailHubService._provider()
        queue_row.status = 'processing'
        queue_row.attempt_count += 1

        try:
            tracking = EmailTrackingService.create_tracking(
                workspace_id=outbound.workspace_id,
                recipient_email=outbound.to_email,
                subject=outbound.subject,
                contact_id=outbound.contact_id,
            )
            outbound.tracking_id = tracking.tracking_id

            body_html = outbound.body_html or ''
            if body_html:
                base_url = (getattr(Config, 'APP_BASE_URL', 'http://localhost:5000') or 'http://localhost:5000').rstrip('/')
                body_html = EmailTrackingService.add_tracking_pixel(body_html, tracking.tracking_id, base_url)
                body_html = EmailTrackingService.rewrite_links(body_html, tracking.tracking_id, base_url)

            message_id = provider.send(
                to_email=outbound.to_email,
                subject=outbound.subject,
                body_text=outbound.body_text,
                body_html=body_html,
            )

            outbound.status = 'sent'
            outbound.provider_message_id = message_id
            outbound.sent_at = datetime.utcnow()
            queue_row.status = 'sent'
            queue_row.processed_at = datetime.utcnow()

            activity = Activity(
                workspace_id=outbound.workspace_id,
                activity_type='email',
                contact_id=outbound.contact_id,
                company_id=outbound.company_id,
                deal_id=outbound.deal_id,
                user_id=outbound.user_id,
                subject=f'Email: {outbound.subject[:200]}',
                body=(outbound.body_text or outbound.body_html or '')[:2000],
                extra_data=json.dumps({
                    'outbound_email_id': outbound.id,
                    'to_email': outbound.to_email,
                    'provider': outbound.provider,
                    'status': outbound.status,
                    'tracking_id': outbound.tracking_id,
                }),
            )
            db.session.add(activity)
            db.session.commit()

            return {
                'id': outbound.id,
                'status': outbound.status,
                'tracking_id': outbound.tracking_id,
                'provider_message_id': outbound.provider_message_id,
            }
        except Exception as exc:
            db.session.rollback()
            queue_row = EmailSendQueue.query.get(queue_id)
            outbound = queue_row.outbound_email if queue_row else None
            if queue_row and outbound:
                queue_row.status = 'failed'
                queue_row.last_error = str(exc)[:2000]
                queue_row.processed_at = datetime.utcnow()
                outbound.status = 'failed'
                outbound.error_message = str(exc)[:2000]
                db.session.commit()
            raise

    @staticmethod
    def render_template_preview(workspace_id, template_id, variables):
        row = EmailTemplate.query.filter_by(workspace_id=workspace_id, id=template_id).first()
        if not row:
            raise ValueError('Template not found')
        subject = EmailHubService.render_template_text(row.subject_template, variables)
        body = EmailHubService.render_template_text(row.body_template, variables)
        return {'subject': subject, 'body': body}

    @staticmethod
    def _conversation_preview(conversation_id):
        msg = Message.query.filter_by(conversation_id=conversation_id).order_by(Message.created_at.desc()).first()
        return msg.message_body if msg else ''

    @staticmethod
    def _conversation_unread(conversation_id):
        return Message.query.filter_by(conversation_id=conversation_id, sender_type='customer', is_read=False).count()

    @staticmethod
    def get_unified_inbox(workspace_id, channel='all', limit=50, offset=0):
        channel = (channel or 'all').strip().lower()
        if channel not in {'all', 'whatsapp', 'telegram', 'email'}:
            channel = 'all'

        whatsapp_items = []
        telegram_items = []
        email_items = []

        open_count = 0
        pending_count = 0

        if channel in {'all', 'whatsapp', 'telegram'}:
            conversations = Conversation.query.filter_by(workspace_id=workspace_id).order_by(Conversation.last_message_at.desc()).all()
            open_count = Conversation.query.filter_by(workspace_id=workspace_id, status='open').count()
            pending_count = Conversation.query.filter_by(workspace_id=workspace_id, status='pending').count()

            customer_ids = [conv.customer_id for conv in conversations if conv.customer_id]
            customers = Customer.query.filter(Customer.id.in_(customer_ids)).all() if customer_ids else []
            customer_map = {c.id: c for c in customers}

            for conv in conversations:
                customer = customer_map.get(conv.customer_id)
                latest_msg = Message.query.filter_by(conversation_id=conv.id).order_by(Message.created_at.desc()).first()
                latest_channel = (getattr(latest_msg, 'channel', None) or 'whatsapp').lower()
                if latest_channel not in {'whatsapp', 'telegram'}:
                    latest_channel = 'whatsapp'

                if channel == 'whatsapp' and latest_channel != 'whatsapp':
                    continue
                if channel == 'telegram' and latest_channel != 'telegram':
                    continue

                item = {
                    'item_id': f'wa-{conv.id}',
                    'item_type': 'telegram' if latest_channel == 'telegram' else 'whatsapp',
                    'conversation_id': conv.id,
                    'status': conv.status,
                    'tags': conv.tags,
                    'counterparty_name': (customer.profile_name if customer else None) or (customer.phone_number if customer else 'Unknown'),
                    'counterparty_phone': customer.phone_number if customer else None,
                    'counterparty_email': customer.email if customer else None,
                    'preview': EmailHubService._conversation_preview(conv.id),
                    'unread_count': EmailHubService._conversation_unread(conv.id),
                    'created_at': conv.last_message_at.isoformat() if conv.last_message_at else None,
                }
                if item['item_type'] == 'telegram':
                    telegram_items.append(item)
                else:
                    whatsapp_items.append(item)

        if channel in {'all', 'email'}:
            synced = EmailSync.query.filter_by(workspace_id=workspace_id).order_by(EmailSync.received_at.desc()).all()
            outbound_rows = OutboundEmail.query.filter_by(workspace_id=workspace_id).order_by(OutboundEmail.created_at.desc()).all()

            for row in synced:
                email_items.append({
                    'item_id': f'es-{row.id}',
                    'item_type': 'email',
                    'email_source': 'synced',
                    'email_id': row.id,
                    'direction': 'sent' if row.is_sent else 'received',
                    'subject': row.subject,
                    'counterparty_email': row.from_email,
                    'counterparty_name': row.from_email,
                    'preview': row.body_snippet or row.subject or '',
                    'has_attachments': bool(row.has_attachments),
                    'contact_id': row.contact_id,
                    'company_id': row.company_id,
                    'created_at': (row.received_at or row.synced_at).isoformat() if (row.received_at or row.synced_at) else None,
                })

            for row in outbound_rows:
                email_items.append({
                    'item_id': f'out-{row.id}',
                    'item_type': 'email',
                    'email_source': 'outbound',
                    'email_id': row.id,
                    'direction': 'sent',
                    'subject': row.subject,
                    'counterparty_email': row.to_email,
                    'counterparty_name': row.to_email,
                    'preview': (row.body_text or row.body_html or '')[:160],
                    'status': row.status,
                    'tracking_id': row.tracking_id,
                    'contact_id': row.contact_id,
                    'company_id': row.company_id,
                    'deal_id': row.deal_id,
                    'created_at': (row.sent_at or row.created_at).isoformat() if (row.sent_at or row.created_at) else None,
                })

        items = whatsapp_items + telegram_items + email_items
        items.sort(key=lambda x: (x.get('created_at') or '', x.get('item_id') or ''), reverse=True)

        total = len(items)
        paged_items = items[offset:offset + limit]

        return {
            'items': paged_items,
            'counts': {
                'total': total,
                'open': open_count,
                'pending': pending_count,
                'whatsapp': len(whatsapp_items),
                'telegram': len(telegram_items),
                'email': len(email_items),
            },
            'channel': channel,
            'limit': limit,
            'offset': offset,
        }
