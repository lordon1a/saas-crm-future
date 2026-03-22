import json
import logging
import re
import smtplib
from datetime import datetime, timedelta
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
    DEFAULT_FIRST_RESPONSE_SLA_MINUTES = 15
    SLA_AT_RISK_THRESHOLD_MINUTES = 5

    @staticmethod
    def _provider():
        provider_name = (getattr(Config, 'EMAIL_PROVIDER', '') or '').strip().lower()
        if provider_name == 'log':
            return LogEmailProvider()
        return SMTPEmailProvider()

    @staticmethod
    def send_invitation_email(workspace_name, inviter_name, invitee_email, role, token, expires_at):
        """
        Send team member invitation email.
        Handles SMTP not configured gracefully - logs instead of failing.
        
        Validates: Requirements 14.1, 14.2, 14.3, 14.4, 14.5, 20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.7
        """
        try:
            # Check if SMTP is configured
            if not Config.SMTP_HOST or not Config.SMTP_FROM_EMAIL:
                logger.info(
                    'SMTP not configured. Invitation email not sent. '
                    'workspace=%s invitee=%s role=%s token=%s',
                    workspace_name, invitee_email, role, token
                )
                return None

            # Build invitation link
            base_url = Config.APP_BASE_URL
            invitation_link = f"{base_url}/accept-invitation?token={token}"
            
            # Format expiration date
            expires_str = expires_at.strftime('%B %d, %Y at %I:%M %p UTC') if expires_at else 'N/A'
            
            # HTML email template
            html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Team Invitation</title>
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f4f4; padding: 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background-color: #4F46E5; padding: 30px 40px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: bold;">
                                You're Invited!
                            </h1>
                        </td>
                    </tr>
                    
                    <!-- Body -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.5; color: #333333;">
                                Hi there,
                            </p>
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.5; color: #333333;">
                                <strong>{inviter_name}</strong> has invited you to join <strong>{workspace_name}</strong> as a <strong>{role}</strong>.
                            </p>
                            <p style="margin: 0 0 30px; font-size: 16px; line-height: 1.5; color: #333333;">
                                Click the button below to accept the invitation and create your account:
                            </p>
                            
                            <!-- CTA Button -->
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <a href="{invitation_link}" style="display: inline-block; padding: 14px 40px; background-color: #4F46E5; color: #ffffff; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: bold;">
                                            Accept Invitation
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            
                            <p style="margin: 30px 0 10px; font-size: 14px; line-height: 1.5; color: #666666;">
                                Or copy and paste this link into your browser:
                            </p>
                            <p style="margin: 0 0 20px; font-size: 14px; line-height: 1.5; color: #4F46E5; word-break: break-all;">
                                {invitation_link}
                            </p>
                            
                            <p style="margin: 30px 0 0; font-size: 14px; line-height: 1.5; color: #999999;">
                                This invitation expires on <strong>{expires_str}</strong>.
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9fafb; padding: 20px 40px; text-align: center; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0; font-size: 12px; color: #999999;">
                                If you didn't expect this invitation, you can safely ignore this email.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
            """
            
            # Plain text fallback
            text_body = f"""
You're Invited to {workspace_name}!

{inviter_name} has invited you to join {workspace_name} as a {role}.

Accept your invitation by visiting this link:
{invitation_link}

This invitation expires on {expires_str}.

If you didn't expect this invitation, you can safely ignore this email.
            """
            
            subject = f"You're invited to join {workspace_name}"
            
            provider = EmailHubService._provider()
            message_id = provider.send(
                to_email=invitee_email,
                subject=subject,
                body_text=text_body.strip(),
                body_html=html_body
            )
            
            logger.info(
                'Invitation email sent successfully. workspace=%s invitee=%s message_id=%s',
                workspace_name, invitee_email, message_id
            )
            return message_id
            
        except Exception as exc:
            # Log error but don't fail - graceful degradation
            logger.error(
                'Failed to send invitation email. workspace=%s invitee=%s error=%s',
                workspace_name, invitee_email, str(exc)
            )
            return None

    @staticmethod
    def send_assignment_notification(assignee_email, assignee_name, entity_type, entity_name, assigner_name, entity_link):
        """
        Send assignment notification email to team member.
        Handles SMTP not configured gracefully - logs instead of failing.
        
        Validates: Requirements 14.1, 14.2, 14.3, 14.4, 14.5, 14.6
        """
        try:
            # Check if SMTP is configured
            if not Config.SMTP_HOST or not Config.SMTP_FROM_EMAIL:
                logger.info(
                    'SMTP not configured. Assignment notification not sent. '
                    'assignee=%s entity_type=%s entity_name=%s',
                    assignee_email, entity_type, entity_name
                )
                return None

            # HTML email template
            html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>New Assignment</title>
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f4f4; padding: 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background-color: #10B981; padding: 30px 40px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: bold;">
                                New Assignment
                            </h1>
                        </td>
                    </tr>
                    
                    <!-- Body -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.5; color: #333333;">
                                Hi {assignee_name},
                            </p>
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.5; color: #333333;">
                                <strong>{assigner_name}</strong> has assigned a <strong>{entity_type}</strong> to you:
                            </p>
                            <p style="margin: 0 0 30px; font-size: 18px; line-height: 1.5; color: #4F46E5; font-weight: bold;">
                                {entity_name}
                            </p>
                            
                            <!-- CTA Button -->
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <a href="{entity_link}" style="display: inline-block; padding: 14px 40px; background-color: #10B981; color: #ffffff; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: bold;">
                                            View {entity_type}
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            
                            <p style="margin: 30px 0 10px; font-size: 14px; line-height: 1.5; color: #666666;">
                                Or copy and paste this link into your browser:
                            </p>
                            <p style="margin: 0; font-size: 14px; line-height: 1.5; color: #10B981; word-break: break-all;">
                                {entity_link}
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9fafb; padding: 20px 40px; text-align: center; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0; font-size: 12px; color: #999999;">
                                You're receiving this because you were assigned to this {entity_type}.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
            """
            
            # Plain text fallback
            text_body = f"""
New Assignment

Hi {assignee_name},

{assigner_name} has assigned a {entity_type} to you:

{entity_name}

View the {entity_type} here:
{entity_link}

You're receiving this because you were assigned to this {entity_type}.
            """
            
            subject = f"New {entity_type} assigned: {entity_name}"
            
            provider = EmailHubService._provider()
            message_id = provider.send(
                to_email=assignee_email,
                subject=subject,
                body_text=text_body.strip(),
                body_html=html_body
            )
            
            logger.info(
                'Assignment notification sent successfully. assignee=%s entity_type=%s message_id=%s',
                assignee_email, entity_type, message_id
            )
            return message_id
            
        except Exception as exc:
            # Log error but don't fail - graceful degradation
            logger.error(
                'Failed to send assignment notification. assignee=%s entity_type=%s error=%s',
                assignee_email, entity_type, str(exc)
            )
            return None

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
    def _conversation_sla_snapshot(conversation_id, now_utc):
        """
        Compute first-response SLA status for a conversation without schema changes.
        """
        first_customer_msg = Message.query.filter_by(
            conversation_id=conversation_id,
            sender_type='customer',
        ).order_by(Message.created_at.asc()).first()

        if not first_customer_msg or not first_customer_msg.created_at:
            return {
                'has_sla': False,
                'status': 'na',
                'minutes_target': EmailHubService.DEFAULT_FIRST_RESPONSE_SLA_MINUTES,
                'first_customer_at': None,
                'first_agent_at': None,
                'remaining_seconds': None,
                'breach_seconds': None,
            }

        first_agent_msg = Message.query.filter(
            Message.conversation_id == conversation_id,
            Message.sender_type != 'customer',
            Message.created_at >= first_customer_msg.created_at
        ).order_by(Message.created_at.asc()).first()

        target_delta = timedelta(minutes=EmailHubService.DEFAULT_FIRST_RESPONSE_SLA_MINUTES)
        due_at = first_customer_msg.created_at + target_delta

        if first_agent_msg and first_agent_msg.created_at:
            response_seconds = int((first_agent_msg.created_at - first_customer_msg.created_at).total_seconds())
            breach_seconds = max(0, int((first_agent_msg.created_at - due_at).total_seconds()))
            status = 'breached' if breach_seconds > 0 else 'met'
            return {
                'has_sla': True,
                'status': status,
                'minutes_target': EmailHubService.DEFAULT_FIRST_RESPONSE_SLA_MINUTES,
                'first_customer_at': first_customer_msg.created_at.isoformat(),
                'first_agent_at': first_agent_msg.created_at.isoformat(),
                'remaining_seconds': 0 if status == 'met' else None,
                'breach_seconds': breach_seconds,
                'response_seconds': response_seconds,
            }

        remaining_seconds = int((due_at - now_utc).total_seconds())
        if remaining_seconds <= 0:
            status = 'overdue'
            breach_seconds = abs(remaining_seconds)
            remaining_seconds = 0
        elif remaining_seconds <= int(EmailHubService.SLA_AT_RISK_THRESHOLD_MINUTES * 60):
            status = 'at_risk'
            breach_seconds = None
        else:
            status = 'ok'
            breach_seconds = None

        return {
            'has_sla': True,
            'status': status,
            'minutes_target': EmailHubService.DEFAULT_FIRST_RESPONSE_SLA_MINUTES,
            'first_customer_at': first_customer_msg.created_at.isoformat(),
            'first_agent_at': None,
            'remaining_seconds': remaining_seconds,
            'breach_seconds': breach_seconds,
        }

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
        sla_overdue_count = 0
        sla_at_risk_count = 0
        now_utc = datetime.utcnow()

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
                    'primary_channel': latest_channel,
                    'conversation_id': conv.id,
                    'conversation_public_id': conv.public_id,
                    'status': conv.status,
                    'tags': conv.tags,
                    'counterparty_name': (customer.profile_name if customer else None) or (customer.phone_number if customer else 'Unknown'),
                    'counterparty_phone': customer.phone_number if customer else None,
                    'counterparty_email': customer.email if customer else None,
                    'preview': EmailHubService._conversation_preview(conv.id),
                    'unread_count': EmailHubService._conversation_unread(conv.id),
                    'created_at': conv.last_message_at.isoformat() if conv.last_message_at else None,
                }
                item['sla'] = EmailHubService._conversation_sla_snapshot(conv.id, now_utc)
                if item['sla']['status'] in {'overdue', 'breached'}:
                    sla_overdue_count += 1
                elif item['sla']['status'] == 'at_risk':
                    sla_at_risk_count += 1
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
                    'primary_channel': 'email',
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
                    'sla': {'has_sla': False, 'status': 'na'},
                })

            for row in outbound_rows:
                email_items.append({
                    'item_id': f'out-{row.id}',
                    'item_type': 'email',
                    'primary_channel': 'email',
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
                    'sla': {'has_sla': False, 'status': 'na'},
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
                'sla_overdue': sla_overdue_count,
                'sla_at_risk': sla_at_risk_count,
            },
            'channel': channel,
            'limit': limit,
            'offset': offset,
        }


    @staticmethod
    def send_password_reset_email(user_email, user_name, reset_token):
        """
        Send password reset email with secure token link.
        Handles SMTP not configured gracefully - logs instead of failing.
        """
        try:
            # Check if SMTP is configured
            if not Config.SMTP_HOST or not Config.SMTP_FROM_EMAIL:
                logger.info(
                    'SMTP not configured. Password reset email not sent. '
                    'email=%s token=%s',
                    user_email, reset_token[:10] + '...'
                )
                return None

            # Build reset link
            base_url = Config.APP_BASE_URL
            reset_link = f"{base_url}/reset-password?token={reset_token}"
            
            # HTML email template
            html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Password Reset</title>
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f4f4; padding: 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background-color: #EF4444; padding: 30px 40px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: bold;">
                                Password Reset Request
                            </h1>
                        </td>
                    </tr>
                    
                    <!-- Body -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.5; color: #333333;">
                                Hi {user_name},
                            </p>
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.5; color: #333333;">
                                We received a request to reset your password. Click the button below to create a new password:
                            </p>
                            
                            <!-- CTA Button -->
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <a href="{reset_link}" style="display: inline-block; padding: 14px 40px; background-color: #EF4444; color: #ffffff; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: bold;">
                                            Reset Password
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            
                            <p style="margin: 30px 0 10px; font-size: 14px; line-height: 1.5; color: #666666;">
                                Or copy and paste this link into your browser:
                            </p>
                            <p style="margin: 0 0 20px; font-size: 14px; line-height: 1.5; color: #EF4444; word-break: break-all;">
                                {reset_link}
                            </p>
                            
                            <div style="margin: 30px 0; padding: 20px; background-color: #FEF2F2; border-left: 4px solid #EF4444; border-radius: 4px;">
                                <p style="margin: 0 0 10px; font-size: 14px; line-height: 1.5; color: #991B1B; font-weight: bold;">
                                    Security Notice:
                                </p>
                                <p style="margin: 0; font-size: 14px; line-height: 1.5; color: #991B1B;">
                                    This link will expire in 1 hour for security reasons.
                                </p>
                            </div>
                            
                            <p style="margin: 20px 0 0; font-size: 14px; line-height: 1.5; color: #666666;">
                                If you didn't request a password reset, please ignore this email. Your password will remain unchanged.
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9fafb; padding: 20px 40px; text-align: center; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0; font-size: 12px; color: #999999;">
                                For security reasons, never share this link with anyone.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
            """
            
            # Plain text fallback
            text_body = f"""
Password Reset Request

Hi {user_name},

We received a request to reset your password. Click the link below to create a new password:

{reset_link}

This link will expire in 1 hour for security reasons.

If you didn't request a password reset, please ignore this email. Your password will remain unchanged.

For security reasons, never share this link with anyone.
            """
            
            subject = "Password Reset Request"
            
            provider = EmailHubService._provider()
            message_id = provider.send(
                to_email=user_email,
                subject=subject,
                body_text=text_body.strip(),
                body_html=html_body
            )
            
            logger.info(
                'Password reset email sent successfully. email=%s message_id=%s',
                user_email, message_id
            )
            return message_id
            
        except Exception as exc:
            # Log error but don't fail - graceful degradation
            logger.error(
                'Failed to send password reset email. email=%s error=%s',
                user_email, str(exc)
            )
            return None
