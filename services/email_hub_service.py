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
    Contact,
    EmailSendQueue,
    EmailSequence,
    EmailSequenceEnrollment,
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


class GmailEmailProvider(BaseEmailProvider):
    name = 'gmail'

    def __init__(self, google_integration):
        self.google_integration = google_integration

    def send(self, to_email, subject, body_text, body_html):
        """Send email via Gmail API"""
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
        from services.google_service import GoogleService
        import base64
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        # Get decrypted tokens
        tokens = GoogleService.get_decrypted_tokens(self.google_integration)
        
        # Build credentials
        credentials = Credentials(
            token=tokens['access_token'],
            refresh_token=tokens['refresh_token'],
            token_uri='https://oauth2.googleapis.com/token',
            client_id=None,
            client_secret=None,
            scopes=json.loads(self.google_integration.scopes or '[]')
        )
        
        # Build Gmail service
        service = build('gmail', 'v1', credentials=credentials)
        
        # Create message
        if body_html:
            message = MIMEMultipart('alternative')
            message.attach(MIMEText(body_text or '', 'plain'))
            message.attach(MIMEText(body_html, 'html'))
        else:
            message = MIMEText(body_text or '', 'plain')
        
        message['To'] = to_email
        message['From'] = self.google_integration.google_email
        message['Subject'] = subject
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        # Send via Gmail API
        result = service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()
        
        return result.get('id')  # Gmail message ID


class EmailHubService:
    DEFAULT_FIRST_RESPONSE_SLA_MINUTES = 15
    SLA_AT_RISK_THRESHOLD_MINUTES = 5

    @staticmethod
    def _provider(workspace_id=None, user_id=None):
        """
        Get email provider based on config.
        For 'gmail' provider, requires workspace_id and user_id to fetch GoogleIntegration.
        """
        provider_name = (getattr(Config, 'EMAIL_PROVIDER', '') or '').strip().lower()
        
        if provider_name == 'log':
            return LogEmailProvider()
        
        if provider_name == 'gmail':
            # Gmail API provider - requires Google OAuth integration
            if not workspace_id or not user_id:
                logger.warning("Gmail provider requires workspace_id and user_id, falling back to SMTP")
                return SMTPEmailProvider()
            
            from models_crm import GoogleIntegration
            google_integration = GoogleIntegration.query.filter_by(
                workspace_id=workspace_id,
                user_id=user_id,
                is_active=True
            ).first()
            
            if not google_integration:
                logger.warning(f"No active Google integration found for workspace={workspace_id} user={user_id}, falling back to SMTP")
                return SMTPEmailProvider()
            
            return GmailEmailProvider(google_integration)
        
        # Default: SMTP
        return SMTPEmailProvider()

    @staticmethod
    def send_invitation_email(workspace_name, inviter_name, invitee_email, role, token, expires_at, workspace_id=None, user_id=None):
        """
        Send team member invitation email.
        Handles SMTP not configured gracefully - logs instead of failing.
        
        Args:
            workspace_name: Name of the workspace
            inviter_name: Name of the person sending invitation
            invitee_email: Email address of invitee
            role: Role being offered
            token: Invitation token
            expires_at: Expiration datetime
            workspace_id: Optional workspace ID for Gmail API provider
            user_id: Optional user ID for Gmail API provider
        
        Validates: Requirements 14.1, 14.2, 14.3, 14.4, 14.5, 20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.7
        """
        try:
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
            
            provider = EmailHubService._provider(workspace_id=workspace_id, user_id=user_id)
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
    def create_template(
        workspace_id,
        user_id,
        name,
        subject_template,
        body_template,
        design_json=None,
        editor_type='html',
    ):
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
            design_json=design_json,
            editor_type=editor_type or 'html',
            created_by=user_id,
        )
        try:
            db.session.add(row)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        return row

    @staticmethod
    def get_template(workspace_id, template_id):
        return EmailTemplate.query.filter_by(workspace_id=workspace_id, id=template_id).first()

    @staticmethod
    def update_template(
        workspace_id,
        template_id,
        name=None,
        subject_template=None,
        body_template=None,
        design_json=None,
        editor_type=None,
        is_active=None,
    ):
        row = EmailTemplate.query.filter_by(workspace_id=workspace_id, id=template_id).first()
        if not row:
            raise ValueError('Template not found')

        if name is not None:
            row.name = (name or '').strip()
        if subject_template is not None:
            row.subject_template = subject_template
        if body_template is not None:
            row.body_template = body_template
        if design_json is not None:
            row.design_json = design_json
        if editor_type is not None:
            row.editor_type = editor_type
        if is_active is not None:
            row.is_active = bool(is_active)

        variables = sorted(
            set(EmailHubService.extract_variables(row.subject_template))
            | set(EmailHubService.extract_variables(row.body_template))
        )
        row.variables_json = json.dumps(variables)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
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
                'design_json': row.design_json,
                'editor_type': row.editor_type or 'html',
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

        provider = EmailHubService._provider(workspace_id=workspace_id, user_id=user_id)

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
        provider = EmailHubService._provider(workspace_id=outbound.workspace_id, user_id=outbound.user_id)
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
    
    @staticmethod
    def send_workflow_email(workspace_id: int, to_email: str, subject: str, body: str, from_name: str = None) -> dict:
        """
        Send email from workflow automation.
        Used by WorkflowService to send emails triggered by workflows.
        
        Args:
            workspace_id: Workspace ID for tracking/logging
            to_email: Recipient email address
            subject: Email subject
            body: Email body (HTML supported)
            from_name: Optional sender name
        
        Returns:
            dict with 'success' bool and 'message_id' or 'error'
        """
        try:
            # Check if SMTP is configured
            if not Config.SMTP_HOST or not Config.SMTP_FROM_EMAIL:
                logger.warning(
                    'SMTP not configured. Workflow email not sent. to=%s subject=%s',
                    to_email, subject
                )
                return {'success': False, 'error': 'SMTP not configured'}
            
            # Build HTML email
            html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            {body}
        </div>
        <div style="text-align: center; margin-top: 20px; padding: 20px; color: #666; font-size: 12px;">
            <p>Bu email otomatik olarak gönderilmiştir.</p>
            <p>Sleek CRM - Otomasyon Sistemi</p>
        </div>
    </div>
</body>
</html>
            """
            
            # Plain text fallback - strip HTML tags using regex
            text_body = re.sub(r'<[^>]*>', '', body).strip()
            
            # Get provider and send
            provider = EmailHubService._provider()
            message_id = provider.send(
                to_email=to_email,
                subject=subject,
                body_text=text_body,
                body_html=html_body
            )
            
            logger.info(
                'Workflow email sent successfully. to=%s subject=%s message_id=%s workspace=%s',
                to_email, subject, message_id, workspace_id
            )
            
            return {'success': True, 'message_id': message_id}
            
        except Exception as exc:
            logger.error(
                'Failed to send workflow email. to=%s subject=%s error=%s',
                to_email, subject, str(exc)
            )
            return {'success': False, 'error': str(exc)}

    @staticmethod
    def enroll_contact(workspace_id, sequence_id, contact_id, enrolled_by):
        """
        Creates EmailSequenceEnrollment, sets next_send_at = now + step[0].delay_hours.
        Raises error if same contact is already active in this sequence.
        
        Args:
            workspace_id: Workspace ID
            sequence_id: EmailSequence ID
            contact_id: Contact ID to enroll
            enrolled_by: User ID who enrolled the contact
            
        Returns:
            EmailSequenceEnrollment object
            
        Raises:
            ValueError: If sequence not found, no steps, or contact already enrolled
        """
        # Check for existing active enrollment
        existing = EmailSequenceEnrollment.query.filter_by(
            workspace_id=workspace_id,
            sequence_id=sequence_id,
            contact_id=contact_id,
            status='active'
        ).first()
        if existing:
            raise ValueError('Contact is already enrolled and active in this sequence')
        
        # Get sequence with steps
        sequence = EmailSequence.query.filter_by(
            id=sequence_id,
            workspace_id=workspace_id,
            is_active=True
        ).first()
        if not sequence:
            raise ValueError('Email sequence not found or inactive')

        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        if not contact:
            raise ValueError('Contact not found')
        if not contact.email:
            raise ValueError('Contact does not have an email address')
        
        # Get first step
        steps = sorted(sequence.steps, key=lambda s: s.step_order)
        if not steps:
            raise ValueError('Email sequence has no steps')
        
        first_step = steps[0]
        next_send_at = datetime.utcnow() + timedelta(hours=first_step.delay_hours)
        
        enrollment = EmailSequenceEnrollment(
            workspace_id=workspace_id,
            sequence_id=sequence_id,
            contact_id=contact_id,
            enrolled_by=enrolled_by,
            status='active',
            current_step_index=0,
            next_send_at=next_send_at,
        )
        
        try:
            db.session.add(enrollment)
            db.session.commit()
            logger.info(
                'Contact enrolled in sequence. enrollment_id=%s contact=%s sequence=%s next_send_at=%s',
                enrollment.id, contact_id, sequence_id, next_send_at
            )
            return enrollment
        except Exception as exc:
            db.session.rollback()
            logger.error(
                'Failed to enroll contact. contact=%s sequence=%s error=%s',
                contact_id, sequence_id, str(exc)
            )
            raise

    @staticmethod
    def process_enrollment_queue():
        """
        Called by APScheduler every 15 minutes.
        - Fetches active enrollments where next_send_at <= now
        - Sends step email via queue_outbound_email()
        - Increments current_step_index, updates next_send_at
        - Sets status='completed' if last step
        
        Returns:
            dict with 'processed' count and 'errors' list
        """
        now = datetime.utcnow()
        processed = 0
        errors = []
        
        # Fetch enrollments ready to send
        enrollments = EmailSequenceEnrollment.query.filter(
            EmailSequenceEnrollment.status == 'active',
            EmailSequenceEnrollment.next_send_at <= now
        ).all()
        
        for enrollment in enrollments:
            try:
                # Get sequence and steps
                sequence = enrollment.sequence
                if not sequence or not sequence.is_active:
                    enrollment.status = 'stopped'
                    enrollment.stopped_reason = 'sequence_inactive'
                    db.session.commit()
                    continue
                
                steps = sorted(sequence.steps, key=lambda s: s.step_order)
                if not steps or enrollment.current_step_index >= len(steps):
                    enrollment.status = 'completed'
                    enrollment.completed_at = datetime.utcnow()
                    db.session.commit()
                    continue
                
                current_step = steps[enrollment.current_step_index]
                
                # Get contact email
                contact = enrollment.contact
                if not contact or not contact.email:
                    enrollment.status = 'stopped'
                    enrollment.stopped_reason = 'no_contact_email'
                    db.session.commit()
                    continue
                
                # Prepare email content
                if current_step.template_id:
                    template = EmailTemplate.query.get(current_step.template_id)
                    if template:
                        subject = EmailHubService.render_template_text(
                            template.subject_template,
                            {'contact': contact}
                        )
                        body = EmailHubService.render_template_text(
                            template.body_template,
                            {'contact': contact}
                        )
                    else:
                        subject = current_step.subject_override or ' '
                        body = current_step.body_override or ''
                else:
                    subject = current_step.subject_override or ' '
                    body = current_step.body_override or ''
                
                # Queue the email
                EmailHubService.queue_outbound_email(
                    workspace_id=enrollment.workspace_id,
                    user_id=enrollment.enrolled_by,
                    to_email=contact.email,
                    subject=subject.strip(),
                    body_text=body,
                    body_html=None,
                    contact_id=contact.id,
                )
                
                # Move to next step
                enrollment.current_step_index += 1
                
                if enrollment.current_step_index >= len(steps):
                    # Completed all steps
                    enrollment.status = 'completed'
                    enrollment.completed_at = datetime.utcnow()
                    enrollment.next_send_at = None
                else:
                    # Schedule next step
                    next_step = steps[enrollment.current_step_index]
                    enrollment.next_send_at = datetime.utcnow() + timedelta(hours=next_step.delay_hours)
                
                db.session.commit()
                processed += 1
                
                logger.info(
                    'Processed enrollment step. enrollment_id=%s step=%s contact=%s',
                    enrollment.id, enrollment.current_step_index - 1, contact.id
                )
                
            except Exception as exc:
                db.session.rollback()
                errors.append({'enrollment_id': enrollment.id, 'error': str(exc)})
                logger.error(
                    'Failed to process enrollment. enrollment_id=%s error=%s',
                    enrollment.id, str(exc)
                )
        
        return {'processed': processed, 'errors': errors}

    @staticmethod
    def unenroll_contact(enrollment_id, reason, workspace_id=None):
        """
        Sets status='stopped', stopped_reason=reason.
        
        Args:
            enrollment_id: EmailSequenceEnrollment ID
            reason: One of 'reply_detected' | 'manual' | 'bounced'
            
        Returns:
            EmailSequenceEnrollment object
            
        Raises:
            ValueError: If enrollment not found or invalid reason
        """
        valid_reasons = ('reply_detected', 'manual', 'bounced')
        if reason not in valid_reasons:
            raise ValueError(f'Invalid reason. Must be one of: {", ".join(valid_reasons)}')
        
        enrollment = EmailSequenceEnrollment.query.get(enrollment_id)
        if not enrollment:
            raise ValueError('Enrollment not found')

        if workspace_id and int(enrollment.workspace_id) != int(workspace_id):
            raise ValueError('Enrollment not found')
        
        if enrollment.status == 'stopped':
            # Already unenrolled, return as-is
            return enrollment
        
        try:
            enrollment.status = 'stopped'
            enrollment.stopped_reason = reason
            enrollment.next_send_at = None
            db.session.commit()
            
            logger.info(
                'Contact unenrolled from sequence. enrollment_id=%s reason=%s',
                enrollment_id, reason
            )
            return enrollment
        except Exception as exc:
            db.session.rollback()
            logger.error(
                'Failed to unenroll contact. enrollment_id=%s error=%s',
                enrollment_id, str(exc)
            )
            raise

    @staticmethod
    def process_reply(workspace_id, from_email, in_reply_to_message_id):
        """
        Called by gmail_sync_service when reply detected.
        - Finds OutboundEmail matching message_id
        - Finds active enrollments for that contact
        - Calls unenroll_contact(..., reason='reply_detected')
        
        Args:
            workspace_id: Workspace ID
            from_email: Email address that sent the reply
            in_reply_to_message_id: Message-ID header from the original outbound email
            
        Returns:
            dict with 'unenrolled' list of enrollment IDs
        """
        # Find outbound email by provider_message_id
        outbound = OutboundEmail.query.filter_by(
            workspace_id=workspace_id,
            provider_message_id=in_reply_to_message_id
        ).first()
        
        if not outbound:
            logger.warning(
                'process_reply: OutboundEmail not found. workspace=%s message_id=%s',
                workspace_id, in_reply_to_message_id
            )
            return {'unenrolled': []}
        
        contact_id = outbound.contact_id
        if not contact_id:
            logger.warning(
                'process_reply: OutboundEmail has no contact_id. outbound_id=%s',
                outbound.id
            )
            return {'unenrolled': []}
        
        # Find active enrollments for this contact in this workspace
        enrollments = EmailSequenceEnrollment.query.filter_by(
            workspace_id=workspace_id,
            contact_id=contact_id,
            status='active'
        ).all()
        
        unenrolled_ids = []
        for enrollment in enrollments:
            try:
                EmailHubService.unenroll_contact(
                    enrollment.id,
                    reason='reply_detected',
                    workspace_id=workspace_id,
                )
                unenrolled_ids.append(enrollment.id)
            except Exception as exc:
                logger.error(
                    'Failed to unenroll on reply. enrollment_id=%s error=%s',
                    enrollment.id, str(exc)
                )
        
        logger.info(
            'process_reply: Found %s active enrollments for contact=%s, unenrolled=%s',
            len(enrollments), contact_id, unenrolled_ids
        )
        
        return {'unenrolled': unenrolled_ids}
