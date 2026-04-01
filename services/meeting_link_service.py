"""
Meeting Link Service
Manages self-booking meeting links and reservations.
"""
import json
import secrets
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging


logger = logging.getLogger(__name__)


def generate_slug(title: str, user_id: int) -> str:
    """Generate a unique slug from title."""
    # Create base slug from title
    base_slug = title.lower().replace(' ', '-').replace('_', '-')
    # Remove non-alphanumeric characters
    base_slug = ''.join(c for c in base_slug if c.isalnum() or c == '-')
    base_slug = base_slug[:80]  # Max 80 chars
    
    # Make unique by appending short random string
    suffix = secrets.token_hex(2)
    slug = f"{base_slug}-{suffix}"
    
    # Ensure slug is unique
    from app import db
    from models_crm import MeetingLink
    counter = 0
    while MeetingLink.query.filter_by(slug=slug).first():
        counter += 1
        suffix = secrets.token_hex(2)
        slug = f"{base_slug}-{suffix}-{counter}"
    
    return slug


def create_meeting_link(
    workspace_id: int,
    user_id: int,
    title: str,
    duration_minutes: int = 30,
    buffer_minutes: int = 0,
    max_days_ahead: int = 60,
    availability_json: str = None,
    video_provider: str = 'none',
    location: str = None,
    description: str = None
):
    """Create a new meeting link."""
    from app import db
    from models_crm import MeetingLink
    
    slug = generate_slug(title, user_id)
    
    meeting_link = MeetingLink(
        workspace_id=workspace_id,
        user_id=user_id,
        slug=slug,
        title=title,
        duration_minutes=duration_minutes,
        buffer_minutes=buffer_minutes,
        max_days_ahead=max_days_ahead,
        availability_json=availability_json or get_default_availability(),
        video_provider=video_provider or 'none',
        location=location,
        description=description
    )
    
    db.session.add(meeting_link)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    
    return meeting_link


def list_meeting_links(workspace_id: int, user_id: int = None) -> List:
    """List meeting links for a workspace, optionally filtered by user."""
    from models_crm import MeetingLink
    
    query = MeetingLink.query.filter_by(workspace_id=workspace_id)
    if user_id:
        query = query.filter_by(user_id=user_id)
    return query.order_by(MeetingLink.created_at.desc()).all()


def get_meeting_link_by_id(meeting_link_id: int):
    """Get a meeting link by ID."""
    from models_crm import MeetingLink
    return MeetingLink.query.get(meeting_link_id)


def get_meeting_link_by_slug(slug: str):
    """Get a meeting link by slug."""
    from models_crm import MeetingLink
    return MeetingLink.query.filter_by(slug=slug, is_active=True).first()


def update_meeting_link(
    meeting_link_id: int,
    title: str = None,
    duration_minutes: int = None,
    buffer_minutes: int = None,
    max_days_ahead: int = None,
    availability_json: str = None,
    video_provider: str = None,
    location: str = None,
    description: str = None,
    is_active: bool = None
):
    """Update a meeting link."""
    from app import db
    from models_crm import MeetingLink
    
    meeting_link = MeetingLink.query.get(meeting_link_id)
    if not meeting_link:
        return None
    
    if title is not None:
        meeting_link.title = title
    if duration_minutes is not None:
        meeting_link.duration_minutes = duration_minutes
    if buffer_minutes is not None:
        meeting_link.buffer_minutes = buffer_minutes
    if max_days_ahead is not None:
        meeting_link.max_days_ahead = max_days_ahead
    if availability_json is not None:
        meeting_link.availability_json = availability_json
    if video_provider is not None:
        meeting_link.video_provider = video_provider
    if location is not None:
        meeting_link.location = location
    if description is not None:
        meeting_link.description = description
    if is_active is not None:
        meeting_link.is_active = is_active
    
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return meeting_link


def delete_meeting_link(meeting_link_id: int) -> bool:
    """Delete a meeting link."""
    from app import db
    from models_crm import MeetingLink
    
    meeting_link = MeetingLink.query.get(meeting_link_id)
    if not meeting_link:
        return False
    
    db.session.delete(meeting_link)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return True


def get_default_availability() -> str:
    """Get default weekly availability (9 AM - 5 PM weekdays)."""
    availability = {}
    for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']:
        availability[day] = [{"start": "09:00", "end": "17:00"}]
    return json.dumps(availability)


def get_available_slots(meeting_link_id: int, date_from: datetime, date_to: datetime) -> List[Dict[str, Any]]:
    """
    Get available time slots for a meeting link within date range.
    Returns list of {date, time, datetime} objects.
    """
    from models_crm import MeetingLink, MeetingBooking
    
    meeting_link = MeetingLink.query.get(meeting_link_id)
    if not meeting_link or not meeting_link.is_active:
        return []
    
    availability = json.loads(meeting_link.availability_json or '{}')
    slots = []
    
    current_date = date_from.date()
    end_date = date_to.date()
    
    # Don't exceed max_days_ahead
    max_date = datetime.utcnow().date() + timedelta(days=meeting_link.max_days_ahead)
    if end_date > max_date:
        end_date = max_date
    
    while current_date <= end_date:
        # Get day of week in lowercase
        dow = current_date.strftime('%A').lower()
        
        if dow in availability:
            for time_range in availability[dow]:
                # Generate slots for this day
                day_slots = generate_day_slots(
                    current_date,
                    time_range['start'],
                    time_range['end'],
                    meeting_link.duration_minutes,
                    meeting_link.buffer_minutes
                )
                slots.extend(day_slots)
        
        current_date += timedelta(days=1)
    
    # Filter out slots that are in the past
    now = datetime.utcnow()
    slots = [s for s in slots if s['datetime'] > now]
    
    # Filter out already booked slots
    booked_times = get_booked_times(meeting_link_id, date_from, date_to)
    slots = [s for s in slots if not is_slot_booked(s['datetime'], meeting_link.duration_minutes, booked_times)]
    
    return slots


def generate_day_slots(date: datetime, start_time: str, end_time: str, duration: int, buffer: int) -> List[Dict[str, Any]]:
    """Generate time slots for a single day."""
    slots = []
    
    # Parse start and end times
    start_hour, start_min = map(int, start_time.split(':'))
    end_hour, end_min = map(int, end_time.split(':'))
    
    slot_start = date.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
    day_end = date.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)
    
    while slot_start + timedelta(minutes=duration) <= day_end:
        slot_end = slot_start + timedelta(minutes=duration)
        
        slots.append({
            'date': date.strftime('%Y-%m-%d'),
            'time': slot_start.strftime('%H:%M'),
            'datetime': slot_start,
            'end_time': slot_end.strftime('%H:%M')
        })
        
        # Move to next slot (duration + buffer)
        slot_start = slot_end + timedelta(minutes=buffer)
    
    return slots


def get_booked_times(meeting_link_id: int, date_from: datetime, date_to: datetime) -> List[tuple]:
    """Get list of (start_time, end_time) tuples for existing bookings."""
    from models_crm import MeetingBooking
    
    bookings = MeetingBooking.query.filter(
        MeetingBooking.meeting_link_id == meeting_link_id,
        MeetingBooking.status.in_(['confirmed', 'pending']),
        MeetingBooking.start_time >= date_from,
        MeetingBooking.end_time <= date_to
    ).all()
    
    return [(b.start_time, b.end_time) for b in bookings]


def is_slot_booked(slot_time: datetime, duration: int, booked_times: List[tuple]) -> bool:
    """Check if a time slot overlaps with any booked time."""
    slot_end = slot_time + timedelta(minutes=duration)
    
    for booked_start, booked_end in booked_times:
        # Check for overlap
        if slot_time < booked_end and slot_end > booked_start:
            return True
    
    return False


def create_booking(
    meeting_link_id: int,
    booker_name: str,
    booker_email: str,
    start_time: datetime,
    booker_notes: str = None
):
    """
    Create a new booking for a meeting link.
    Returns (booking, matched_contact).
    """
    from app import db
    from models_crm import MeetingLink, MeetingBooking, Contact, Activity
    
    meeting_link = MeetingLink.query.get(meeting_link_id)
    if not meeting_link or not meeting_link.is_active:
        raise ValueError("Meeting link not found or inactive")
    
    # Check if slot is still available
    booked_times = get_booked_times(meeting_link_id, start_time - timedelta(days=1), start_time + timedelta(days=1))
    if is_slot_booked(start_time, meeting_link.duration_minutes, booked_times):
        raise ValueError("This time slot is no longer available")
    
    # Generate confirmation token
    confirmation_token = secrets.token_urlsafe(32)
    
    # Create booking
    booking = MeetingBooking(
        meeting_link_id=meeting_link_id,
        workspace_id=meeting_link.workspace_id,
        booker_name=booker_name,
        booker_email=booker_email,
        booker_notes=booker_notes,
        start_time=start_time,
        end_time=start_time + timedelta(minutes=meeting_link.duration_minutes),
        status='confirmed',
        confirmation_token=confirmation_token
    )
    
    # Try to match or create contact
    contact = match_or_create_contact(meeting_link.workspace_id, booker_name, booker_email)
    if contact:
        booking.contact_id = contact.id
    
    try:
        db.session.add(booking)
        db.session.flush()

        # Best-effort external integrations (Google Calendar / Zoom URL)
        try:
            booking.google_calendar_event_id = _create_google_calendar_event_for_booking(meeting_link, booking)
        except Exception as exc:
            logger.warning('Google Calendar event creation failed for booking %s: %s', booking.id, exc)

        try:
            booking.zoom_meeting_url = _resolve_zoom_url_for_booking(meeting_link, booking)
        except Exception as exc:
            logger.warning('Zoom URL resolution failed for booking %s: %s', booking.id, exc)
        
        # Create activity
        activity = Activity(
            workspace_id=meeting_link.workspace_id,
            contact_id=contact.id if contact else None,
            activity_type='meeting_scheduled',
            description=f'Meeting scheduled: {meeting_link.title}',
            notes=f"Booker: {booker_name} ({booker_email})\nTime: {start_time.strftime('%Y-%m-%d %H:%M')}\nLocation: {meeting_link.location or 'TBD'}",
            user_id=meeting_link.user_id
        )
        db.session.add(activity)

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    
    # Send confirmation email (async)
    send_booking_confirmation(booking, meeting_link)
    
    return booking, contact


def _create_google_calendar_event_for_booking(meeting_link, booking) -> Optional[str]:
    """
    Create a Google Calendar event for booking owner if integration is active.
    Returns Google event id or None.
    """
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from models_crm import GoogleIntegration
    from services.google_service import GoogleService

    integration = GoogleIntegration.query.filter_by(
        workspace_id=meeting_link.workspace_id,
        user_id=meeting_link.user_id,
        is_active=True,
    ).first()

    if not integration:
        return None

    tokens = GoogleService.get_decrypted_tokens(integration)
    creds = Credentials(
        token=tokens['access_token'],
        refresh_token=tokens.get('refresh_token'),
        token_uri='https://oauth2.googleapis.com/token',
        client_id=None,
        client_secret=None,
        scopes=json.loads(integration.scopes or '[]'),
    )

    service = build('calendar', 'v3', credentials=creds)
    event_body = {
        'summary': meeting_link.title,
        'description': booking.booker_notes or meeting_link.description or '',
        'start': {'dateTime': booking.start_time.isoformat(), 'timeZone': 'UTC'},
        'end': {'dateTime': booking.end_time.isoformat(), 'timeZone': 'UTC'},
        'attendees': [{'email': booking.booker_email}],
    }
    if meeting_link.location:
        event_body['location'] = meeting_link.location

    created = service.events().insert(calendarId='primary', body=event_body, sendUpdates='all').execute()
    return created.get('id')


def _resolve_zoom_url_for_booking(meeting_link, booking) -> Optional[str]:
    """
    Resolve a Zoom URL for booking when meeting location is a Zoom link.
    """
    if getattr(meeting_link, 'video_provider', 'none') == 'zoom':
        from services.zoom_service import ZoomService
        zoom_payload = ZoomService.create_meeting(
            workspace_id=meeting_link.workspace_id,
            user_id=meeting_link.user_id,
            topic=meeting_link.title,
            start_time=booking.start_time,
            duration_minutes=meeting_link.duration_minutes,
        )
        return zoom_payload.get('zoom_join_url')

    location = (meeting_link.location or '').strip()
    if 'zoom.us/' in location:
        return location
    return None


def match_or_create_contact(workspace_id: int, name: str, email: str):
    """Match existing contact by email or create new one."""
    from app import db
    from models_crm import Contact
    
    contact = Contact.query.filter_by(
        workspace_id=workspace_id,
        email=email.lower()
    ).first()
    
    if contact:
        return contact
    
    # Create new contact
    try:
        contact = Contact(
            workspace_id=workspace_id,
            name=name,
            email=email.lower(),
            created_by=None  # System created
        )
        db.session.add(contact)
        db.session.commit()
        return contact
    except Exception:
        db.session.rollback()
        return None


def cancel_booking(booking_id: int = None, token: str = None) -> bool:
    """Cancel a booking using booking ID or confirmation token."""
    from app import db
    from models_crm import MeetingBooking, Activity
    
    if booking_id:
        booking = MeetingBooking.query.get(booking_id)
    elif token:
        booking = MeetingBooking.query.filter_by(confirmation_token=token).first()
    else:
        return False
    
    if not booking:
        return False
    
    if booking.status == 'cancelled':
        return True  # Already cancelled
    
    booking.status = 'cancelled'
    
    # Update activity if exists
    activity = Activity.query.filter_by(
        workspace_id=booking.workspace_id,
        activity_type='meeting_scheduled'
    ).filter(
        Activity.notes.like(f'%{booking.booker_email}%')
    ).first()
    
    if activity:
        activity.description = f'Meeting cancelled: {booking.meeting_link.title if booking.meeting_link else "Unknown"}'

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    
    # Send cancellation email
    send_booking_cancellation(booking)
    
    return True


def list_bookings(meeting_link_id: int, status: str = None) -> List:
    """List bookings for a meeting link."""
    from models_crm import MeetingBooking
    
    query = MeetingBooking.query.filter_by(meeting_link_id=meeting_link_id)
    if status:
        query = query.filter_by(status=status)
    return query.order_by(MeetingBooking.start_time.desc()).all()


def get_booking_by_token(token: str):
    """Get booking by confirmation token."""
    from models_crm import MeetingBooking
    return MeetingBooking.query.filter_by(confirmation_token=token).first()


def send_booking_confirmation(booking, meeting_link):
    """Send confirmation email to booker."""
    from flask import current_app
    from services.email_hub_service import EmailHubService
    
    try:
        subject = f"Meeting Confirmed: {meeting_link.title}"
        
        # Build email body
        body = f"""
Hello {booking.booker_name},

Your meeting has been confirmed!

Meeting Details:
- Title: {meeting_link.title}
- Date & Time: {booking.start_time.strftime('%A, %B %d, %Y at %I:%M %p')}
- Duration: {meeting_link.duration_minutes} minutes
- Location: {meeting_link.location or 'Virtual meeting'}

Cancel or Reschedule:
Use this link to cancel: {booking.meeting_link.booking_url if booking.meeting_link else '/book'}

Best regards,
{meeting_link.owner.name if meeting_link.owner else 'The Team'}
        """.strip()
        
        # Queue email
        EmailHubService.queue_outbound_email(
            workspace_id=booking.workspace_id,
            user_id=meeting_link.user_id,
            to_email=booking.booker_email,
            subject=subject,
            body_text=body,
            body_html=None,
            contact_id=booking.contact_id
        )
    except Exception as e:
        current_app.logger.error(f"Failed to send booking confirmation: {e}")


def send_booking_cancellation(booking):
    """Send cancellation email to booker."""
    from flask import current_app
    from services.email_hub_service import EmailHubService
    
    try:
        if not booking.meeting_link:
            return

        subject = f"Meeting Cancelled: {booking.meeting_link.title if booking.meeting_link else 'Meeting'}"
        
        body = f"""
Hello {booking.booker_name},

Your meeting has been cancelled.

Original Meeting:
- Title: {booking.meeting_link.title if booking.meeting_link else 'Meeting'}
- Date & Time: {booking.start_time.strftime('%A, %B %d, %Y at %I:%M %p')}

You can book a new time slot here: {booking.meeting_link.booking_url if booking.meeting_link else '/book'}

Best regards,
The Team
        """.strip()
        
        EmailHubService.queue_outbound_email(
            workspace_id=booking.workspace_id,
            user_id=booking.meeting_link.user_id,
            to_email=booking.booker_email,
            subject=subject,
            body_text=body,
            body_html=None,
            contact_id=booking.contact_id
        )
    except Exception as e:
        current_app.logger.error(f"Failed to send cancellation email: {e}")
