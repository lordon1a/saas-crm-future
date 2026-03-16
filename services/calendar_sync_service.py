"""
Google Calendar Sync Service - Fetches and syncs calendar events
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from models import db
from models_crm import CalendarSync, GoogleIntegration, Contact, Company, Activity
from services.google_service import GoogleService

logger = logging.getLogger(__name__)


class CalendarSyncService:
    """Service for syncing Google Calendar events to CRM"""
    
    @staticmethod
    def _build_calendar_service(google_integration: GoogleIntegration):
        """Build Calendar API service with stored credentials"""
        tokens = GoogleService.get_decrypted_tokens(google_integration)
        
        credentials = Credentials(
            token=tokens['access_token'],
            refresh_token=tokens['refresh_token'],
            token_uri='https://oauth2.googleapis.com/token',
            client_id=None,
            client_secret=None,
            scopes=json.loads(google_integration.scopes or '[]')
        )
        
        return build('calendar', 'v3', credentials=credentials)
    
    @staticmethod
    def sync_recent_events(workspace_id: int, user_id: int, days_back: int = 7, days_forward: int = 30) -> dict:
        """
        Sync calendar events from Google Calendar.
        
        Args:
            workspace_id: Workspace ID
            user_id: User ID
            days_back: How many days in the past to sync
            days_forward: How many days in the future to sync
            
        Returns:
            dict with sync statistics
        """
        integration = GoogleIntegration.query.filter_by(
            workspace_id=workspace_id,
            user_id=user_id,
            is_active=True
        ).first()
        
        if not integration:
            return {'error': 'No active Google integration found'}
        
        try:
            service = CalendarSyncService._build_calendar_service(integration)
            
            # Get primary calendar events
            time_min = (datetime.utcnow() - timedelta(days=days_back)).isoformat() + 'Z'
            time_max = (datetime.utcnow() + timedelta(days=days_forward)).isoformat() + 'Z'
            
            events_result = service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                maxResults=100,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            synced_count = 0
            skipped_count = 0
            error_count = 0
            
            for event in events:
                try:
                    # Check if already synced
                    existing = CalendarSync.query.filter_by(
                        google_event_id=event['id'],
                        calendar_id='primary'
                    ).first()
                    
                    if existing:
                        # Update existing event
                        if CalendarSyncService._update_event(existing, event):
                            synced_count += 1
                        else:
                            skipped_count += 1
                        continue
                    
                    # Save new event
                    if CalendarSyncService._save_event(workspace_id, integration.id, 'primary', event):
                        synced_count += 1
                    else:
                        error_count += 1
                        
                except Exception as e:
                    logger.error(f'Error syncing event {event.get("id")}: {e}')
                    error_count += 1
            
            return {
                'success': True,
                'synced': synced_count,
                'skipped': skipped_count,
                'errors': error_count,
                'total': len(events)
            }
            
        except Exception as e:
            logger.exception(f'Calendar sync failed: {e}')
            return {'error': str(e)}
    
    @staticmethod
    def _save_event(workspace_id: int, integration_id: int, calendar_id: str, event: dict) -> bool:
        """Parse and save calendar event to database"""
        try:
            # Extract event data
            summary = event.get('summary', 'No Title')
            description = event.get('description', '')
            location = event.get('location', '')
            
            # Parse start/end times
            start_time = CalendarSyncService._parse_datetime(event.get('start', {}))
            end_time = CalendarSyncService._parse_datetime(event.get('end', {}))
            
            if not start_time or not end_time:
                logger.warning(f'Event {event.get("id")} has no valid start/end time')
                return False
            
            # Extract attendees
            attendees = event.get('attendees', [])
            attendee_emails = [a['email'] for a in attendees if 'email' in a]
            
            organizer = event.get('organizer', {})
            organizer_email = organizer.get('email', '')
            
            # Match to contact
            contact = CalendarSyncService._match_contact(workspace_id, attendee_emails)
            company_id = contact.company_id if contact else None
            
            # Create calendar sync record
            calendar_sync = CalendarSync(
                workspace_id=workspace_id,
                google_integration_id=integration_id,
                google_event_id=event['id'],
                calendar_id=calendar_id,
                summary=summary[:500],
                description=description[:2000] if description else None,
                location=location[:500] if location else None,
                start_time=start_time,
                end_time=end_time,
                attendee_emails=json.dumps(attendee_emails),
                organizer_email=organizer_email,
                contact_id=contact.id if contact else None,
                company_id=company_id,
                event_status=event.get('status', 'confirmed'),
                is_recurring=bool(event.get('recurringEventId')),
                recurring_event_id=event.get('recurringEventId')
            )
            
            db.session.add(calendar_sync)
            db.session.flush()
            
            # Create activity record
            if contact:
                activity = Activity(
                    workspace_id=workspace_id,
                    activity_type='meeting',
                    contact_id=contact.id,
                    company_id=company_id,
                    subject=f'Meeting: {summary[:200]}',
                    description=description[:500] if description else None,
                    activity_date=start_time,
                    metadata=json.dumps({
                        'location': location,
                        'attendees': attendee_emails,
                        'google_event_id': event['id'],
                        'duration_minutes': int((end_time - start_time).total_seconds() / 60)
                    })
                )
                db.session.add(activity)
                db.session.flush()
                
                calendar_sync.activity_id = activity.id
            
            db.session.commit()
            return True
            
        except Exception as e:
            logger.error(f'Error saving calendar event: {e}')
            db.session.rollback()
            return False
    
    @staticmethod
    def _update_event(calendar_sync: CalendarSync, event: dict) -> bool:
        """Update existing calendar event"""
        try:
            # Check if event was cancelled
            if event.get('status') == 'cancelled':
                calendar_sync.event_status = 'cancelled'
                db.session.commit()
                return True
            
            # Update basic fields
            calendar_sync.summary = event.get('summary', 'No Title')[:500]
            calendar_sync.description = event.get('description', '')[:2000] or None
            calendar_sync.location = event.get('location', '')[:500] or None
            calendar_sync.event_status = event.get('status', 'confirmed')
            calendar_sync.synced_at = datetime.utcnow()
            
            # Update times
            start_time = CalendarSyncService._parse_datetime(event.get('start', {}))
            end_time = CalendarSyncService._parse_datetime(event.get('end', {}))
            
            if start_time:
                calendar_sync.start_time = start_time
            if end_time:
                calendar_sync.end_time = end_time
            
            db.session.commit()
            return True
            
        except Exception as e:
            logger.error(f'Error updating calendar event: {e}')
            db.session.rollback()
            return False
    
    @staticmethod
    def _parse_datetime(time_dict: dict) -> Optional[datetime]:
        """Parse Google Calendar datetime"""
        if not time_dict:
            return None
        
        # Try dateTime first (for specific times)
        if 'dateTime' in time_dict:
            try:
                dt_str = time_dict['dateTime']
                # Remove timezone info for simplicity
                if '+' in dt_str:
                    dt_str = dt_str.split('+')[0]
                elif 'Z' in dt_str:
                    dt_str = dt_str.replace('Z', '')
                
                return datetime.fromisoformat(dt_str)
            except Exception as e:
                logger.error(f'Error parsing dateTime: {e}')
        
        # Try date (for all-day events)
        if 'date' in time_dict:
            try:
                return datetime.strptime(time_dict['date'], '%Y-%m-%d')
            except Exception as e:
                logger.error(f'Error parsing date: {e}')
        
        return None
    
    @staticmethod
    def _match_contact(workspace_id: int, attendee_emails: list) -> Optional[Contact]:
        """Match calendar event to existing contact by attendee email"""
        for email in attendee_emails:
            contact = Contact.query.filter_by(
                workspace_id=workspace_id,
                email=email.lower()
            ).first()
            
            if contact:
                return contact
        
        return None
