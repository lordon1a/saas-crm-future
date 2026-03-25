"""
Gmail Sync Service - Fetches and syncs emails from Gmail API
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from models import db
from models_crm import EmailSync, GoogleIntegration, Contact, Company, Activity
from services.google_service import GoogleService

logger = logging.getLogger(__name__)


class GmailSyncService:
    """Service for syncing Gmail emails to CRM"""
    
    @staticmethod
    def _build_gmail_service(google_integration: GoogleIntegration):
        """Build Gmail API service with stored credentials"""
        tokens = GoogleService.get_decrypted_tokens(google_integration)
        
        credentials = Credentials(
            token=tokens['access_token'],
            refresh_token=tokens['refresh_token'],
            token_uri='https://oauth2.googleapis.com/token',
            client_id=None,  # Not needed for API calls
            client_secret=None,
            scopes=json.loads(google_integration.scopes or '[]')
        )
        
        return build('gmail', 'v1', credentials=credentials)
    
    @staticmethod
    def sync_recent_emails(workspace_id: int, user_id: int, max_results: int = 50) -> dict:
        """
        Sync recent emails from Gmail for a user.
        
        Args:
            workspace_id: Workspace ID
            user_id: User ID
            max_results: Maximum number of emails to fetch
            
        Returns:
            dict with sync statistics
        """
        # Get active Google integration
        integration = GoogleIntegration.query.filter_by(
            workspace_id=workspace_id,
            user_id=user_id,
            is_active=True
        ).first()
        
        if not integration:
            return {'error': 'No active Google integration found'}
        
        try:
            service = GmailSyncService._build_gmail_service(integration)
            
            # Get messages from last 7 days
            query = f'after:{int((datetime.utcnow() - timedelta(days=7)).timestamp())}'
            
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            synced_count = 0
            skipped_count = 0
            error_count = 0
            
            for msg in messages:
                try:
                    # Check if already synced
                    existing = EmailSync.query.filter_by(
                        gmail_message_id=msg['id']
                    ).first()
                    
                    if existing:
                        skipped_count += 1
                        continue
                    
                    # Fetch full message
                    full_msg = service.users().messages().get(
                        userId='me',
                        id=msg['id'],
                        format='full'
                    ).execute()
                    
                    # Parse and save email
                    if GmailSyncService._save_email(workspace_id, integration.id, full_msg):
                        synced_count += 1
                    else:
                        error_count += 1
                        
                except Exception as e:
                    logger.error(f'Error syncing email {msg["id"]}: {e}')
                    error_count += 1
            
            return {
                'success': True,
                'synced': synced_count,
                'skipped': skipped_count,
                'errors': error_count,
                'total': len(messages)
            }
            
        except Exception as e:
            logger.exception(f'Gmail sync failed: {e}')
            return {'error': str(e)}
    
    @staticmethod
    def _save_email(workspace_id: int, integration_id: int, message: dict) -> bool:
        """Parse and save email to database"""
        try:
            headers = {h['name']: h['value'] for h in message['payload'].get('headers', [])}
            
            # Extract email data
            subject = headers.get('Subject', '')
            from_email = GmailSyncService._extract_email(headers.get('From', ''))
            to_emails = GmailSyncService._extract_emails(headers.get('To', ''))
            cc_emails = GmailSyncService._extract_emails(headers.get('Cc', ''))
            
            # Get email body
            body_text, body_html = GmailSyncService._extract_body(message['payload'])
            
            # Parse date
            date_str = headers.get('Date', '')
            received_at = GmailSyncService._parse_date(date_str)
            
            # Match to contact
            contact = GmailSyncService._match_contact(workspace_id, from_email, to_emails)
            company_id = contact.company_id if contact else None
            
            # Create email sync record
            email_sync = EmailSync(
                workspace_id=workspace_id,
                google_integration_id=integration_id,
                gmail_message_id=message['id'],
                thread_id=message.get('threadId'),
                subject=subject[:500] if subject else None,
                from_email=from_email,
                to_emails=json.dumps(to_emails),
                cc_emails=json.dumps(cc_emails),
                body_snippet=message.get('snippet', '')[:1000],
                body_html=body_html,
                body_text=body_text,
                received_at=received_at,
                contact_id=contact.id if contact else None,
                company_id=company_id,
                is_sent=False,  # Assume received for now
                has_attachments=GmailSyncService._has_attachments(message['payload']),
                labels=json.dumps(message.get('labelIds', []))
            )
            
            db.session.add(email_sync)
            db.session.flush()
            
            # Create activity record
            if contact:
                activity = Activity(
                    workspace_id=workspace_id,
                    activity_type='email',
                    contact_id=contact.id,
                    company_id=company_id,
                    subject=f'Email: {subject[:200]}',
                    description=message.get('snippet', '')[:500],
                    activity_date=received_at or datetime.utcnow(),
                    metadata=json.dumps({
                        'from': from_email,
                        'to': to_emails,
                        'gmail_message_id': message['id']
                    })
                )
                db.session.add(activity)
                db.session.flush()
                
                email_sync.activity_id = activity.id
            
            db.session.commit()
            
            # Auto-enrichment: E-postadan contact bilgisi çıkar (arka planda)
            if contact:
                try:
                    from threading import Thread
                    from services.enrichment import enrich_contact
                    email_body = body_text or body_html or message.get('snippet', '')
                    Thread(
                        target=enrich_contact,
                        args=(contact.id, workspace_id, email_body[:1000], 'email'),
                        daemon=True
                    ).start()
                except Exception as e:
                    logger.warning(f'Auto-enrichment failed: {e}')
            
            return True
            
        except Exception as e:
            logger.error(f'Error saving email: {e}')
            db.session.rollback()
            return False
    
    @staticmethod
    def _extract_email(email_str: str) -> str:
        """Extract email address from 'Name <email@example.com>' format"""
        if not email_str:
            return ''
        
        if '<' in email_str and '>' in email_str:
            start = email_str.index('<') + 1
            end = email_str.index('>')
            return email_str[start:end].strip().lower()
        
        return email_str.strip().lower()
    
    @staticmethod
    def _extract_emails(emails_str: str) -> list:
        """Extract multiple email addresses"""
        if not emails_str:
            return []
        
        emails = []
        for part in emails_str.split(','):
            email = GmailSyncService._extract_email(part.strip())
            if email:
                emails.append(email)
        
        return emails
    
    @staticmethod
    def _extract_body(payload: dict) -> tuple:
        """Extract text and HTML body from email payload"""
        body_text = ''
        body_html = ''
        
        if 'body' in payload and payload['body'].get('data'):
            import base64
            body_text = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
        
        if 'parts' in payload:
            for part in payload['parts']:
                mime_type = part.get('mimeType', '')
                
                if mime_type == 'text/plain' and part.get('body', {}).get('data'):
                    import base64
                    body_text = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                
                elif mime_type == 'text/html' and part.get('body', {}).get('data'):
                    import base64
                    body_html = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
        
        return body_text[:10000], body_html[:50000]  # Limit sizes
    
    @staticmethod
    def _has_attachments(payload: dict) -> bool:
        """Check if email has attachments"""
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('filename'):
                    return True
        return False
    
    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        """Parse email date header"""
        if not date_str:
            return None
        
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str).replace(tzinfo=None)
        except Exception:
            return None
    
    @staticmethod
    def _match_contact(workspace_id: int, from_email: str, to_emails: list) -> Optional[Contact]:
        """Match email to existing contact by email address"""
        # Try from_email first
        if from_email:
            contact = Contact.query.filter_by(
                workspace_id=workspace_id,
                email=from_email
            ).first()
            
            if contact:
                return contact
        
        # Try to_emails
        for email in to_emails:
            contact = Contact.query.filter_by(
                workspace_id=workspace_id,
                email=email
            ).first()
            
            if contact:
                return contact
        
        return None
