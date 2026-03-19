"""
Email Tracking Service - Track email opens and link clicks
"""
import hashlib
import logging
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode, quote

from models import db
from models_crm import EmailTracking, EmailTrackingClick

logger = logging.getLogger(__name__)


class EmailTrackingService:
    """Service for tracking email opens and clicks"""
    
    @staticmethod
    def create_tracking(workspace_id: int, recipient_email: str, subject: str, 
                       contact_id: Optional[int] = None, email_sync_id: Optional[int] = None) -> EmailTracking:
        """
        Create a new email tracking record.
        
        Args:
            workspace_id: Workspace ID
            recipient_email: Recipient email address
            subject: Email subject
            contact_id: Optional contact ID
            email_sync_id: Optional email sync ID
            
        Returns:
            EmailTracking instance
        """
        # Generate unique tracking ID
        tracking_id = EmailTrackingService._generate_tracking_id(workspace_id, recipient_email)
        
        tracking = EmailTracking(
            workspace_id=workspace_id,
            tracking_id=tracking_id,
            email_sync_id=email_sync_id,
            contact_id=contact_id,
            recipient_email=recipient_email.lower(),
            subject=subject[:500] if subject else None
        )
        
        db.session.add(tracking)
        db.session.commit()
        
        return tracking
    
    @staticmethod
    def _generate_tracking_id(workspace_id: int, recipient_email: str) -> str:
        """Generate unique tracking ID"""
        import secrets
        timestamp = str(datetime.utcnow().timestamp())
        data = f'{workspace_id}:{recipient_email}:{timestamp}:{secrets.token_hex(8)}'
        return hashlib.sha256(data.encode()).hexdigest()[:32]
    
    @staticmethod
    def add_tracking_pixel(html_body: str, tracking_id: str, base_url: str) -> str:
        """
        Add invisible tracking pixel to HTML email body.
        
        Args:
            html_body: Original HTML email body
            tracking_id: Tracking ID
            base_url: Base URL for tracking endpoint (e.g., https://crm.example.com)
            
        Returns:
            Modified HTML with tracking pixel
        """
        pixel_url = f'{base_url}/track/open/{tracking_id}'
        pixel_html = f'<img src="{pixel_url}" width="1" height="1" style="display:none;" alt="" />'
        
        # Try to insert before closing </body> tag
        if '</body>' in html_body.lower():
            return re.sub(r'</body>', f'{pixel_html}</body>', html_body, flags=re.IGNORECASE)
        
        # Otherwise append to end
        return html_body + pixel_html
    
    @staticmethod
    def rewrite_links(html_body: str, tracking_id: str, base_url: str) -> str:
        """
        Rewrite all links in HTML to track clicks.
        
        Args:
            html_body: Original HTML email body
            tracking_id: Tracking ID
            base_url: Base URL for tracking endpoint
            
        Returns:
            Modified HTML with rewritten links
        """
        def replace_link(match):
            original_url = match.group(1)
            
            # Skip tracking pixel and mailto links
            if '/track/open/' in original_url or original_url.startswith('mailto:'):
                return match.group(0)
            
            # Create tracking URL
            tracking_url = f'{base_url}/track/click/{tracking_id}?url={quote(original_url)}'
            return f'href="{tracking_url}"'
        
        # Replace all href attributes
        return re.sub(r'href="([^"]+)"', replace_link, html_body)
    
    @staticmethod
    def record_open(tracking_id: str, user_agent: Optional[str] = None, 
                   ip_address: Optional[str] = None) -> bool:
        """
        Record email open event.
        
        Args:
            tracking_id: Tracking ID
            user_agent: User agent string
            ip_address: IP address
            
        Returns:
            True if recorded successfully
        """
        tracking = EmailTracking.query.filter_by(tracking_id=tracking_id).first()
        
        if not tracking:
            logger.warning(f'Tracking ID not found: {tracking_id}')
            return False
        
        try:
            now = datetime.utcnow()
            
            # Update tracking record
            if not tracking.opened_at:
                tracking.opened_at = now
            
            tracking.open_count += 1
            tracking.last_opened_at = now
            
            if user_agent:
                tracking.user_agent = user_agent[:500]
            if ip_address:
                tracking.ip_address = ip_address[:45]
            
            db.session.commit()
            return True
            
        except Exception as e:
            logger.error(f'Error recording email open: {e}')
            db.session.rollback()
            return False
    
    @staticmethod
    def record_click(tracking_id: str, original_url: str, user_agent: Optional[str] = None,
                    ip_address: Optional[str] = None) -> bool:
        """
        Record link click event.
        
        Args:
            tracking_id: Tracking ID
            original_url: Original URL that was clicked
            user_agent: User agent string
            ip_address: IP address
            
        Returns:
            True if recorded successfully
        """
        tracking = EmailTracking.query.filter_by(tracking_id=tracking_id).first()
        
        if not tracking:
            logger.warning(f'Tracking ID not found: {tracking_id}')
            return False
        
        try:
            now = datetime.utcnow()
            
            # Update tracking record
            tracking.click_count += 1
            tracking.last_clicked_at = now
            
            # Create click record
            click = EmailTrackingClick(
                email_tracking_id=tracking.id,
                original_url=original_url[:2000],
                user_agent=user_agent[:500] if user_agent else None,
                ip_address=ip_address[:45] if ip_address else None
            )
            
            db.session.add(click)
            db.session.commit()
            return True
            
        except Exception as e:
            logger.error(f'Error recording link click: {e}')
            db.session.rollback()
            return False
    
    @staticmethod
    def get_tracking_stats(tracking_id: str) -> Optional[dict]:
        """
        Get tracking statistics for an email.
        
        Args:
            tracking_id: Tracking ID
            
        Returns:
            dict with tracking stats or None
        """
        tracking = EmailTracking.query.filter_by(tracking_id=tracking_id).first()
        
        if not tracking:
            return None
        
        clicks = EmailTrackingClick.query.filter_by(
            email_tracking_id=tracking.id
        ).order_by(EmailTrackingClick.clicked_at.desc()).all()
        
        return {
            'tracking_id': tracking.tracking_id,
            'recipient_email': tracking.recipient_email,
            'subject': tracking.subject,
            'sent_at': tracking.sent_at.isoformat() if tracking.sent_at else None,
            'opened': tracking.opened_at is not None,
            'opened_at': tracking.opened_at.isoformat() if tracking.opened_at else None,
            'open_count': tracking.open_count,
            'last_opened_at': tracking.last_opened_at.isoformat() if tracking.last_opened_at else None,
            'click_count': tracking.click_count,
            'last_clicked_at': tracking.last_clicked_at.isoformat() if tracking.last_clicked_at else None,
            'clicks': [
                {
                    'url': click.original_url,
                    'clicked_at': click.clicked_at.isoformat(),
                    'user_agent': click.user_agent,
                    'ip_address': click.ip_address
                }
                for click in clicks
            ]
        }
