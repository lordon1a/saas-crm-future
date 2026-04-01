"""
Meeting Links API Routes
Public booking endpoints and authenticated management endpoints.
"""
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, current_app, session
from functools import wraps
from datetime import datetime, timedelta
import json

from services.meeting_link_service import (
    create_meeting_link, list_meeting_links, get_meeting_link_by_id,
    get_meeting_link_by_slug, update_meeting_link, delete_meeting_link,
    get_available_slots, create_booking, cancel_booking, list_bookings,
    get_booking_by_token
)
from models import User
from models_crm import MeetingBooking

meeting_links_bp = Blueprint('meeting_links', __name__)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        user = User.query.get(user_id)
        if not user:
            session.clear()
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    return User.query.get(user_id)


def get_workspace_id():
    """Get workspace ID from current user."""
    current_user = get_current_user()
    if current_user and hasattr(current_user, 'workspace_id'):
        return current_user.workspace_id
    return None


# =============================================================================
# PUBLIC ROUTES (No auth required)
# =============================================================================

@meeting_links_bp.route('/book/<slug>')
def public_booking_page(slug):
    """Public booking page - render HTML form."""
    meeting_link = get_meeting_link_by_slug(slug)
    if not meeting_link:
        return "Meeting link not found or inactive.", 404
    
    # Get date range for next 30 days
    date_from = datetime.utcnow()
    date_to = date_from + timedelta(days=30)
    
    # Get available slots
    slots = get_available_slots(meeting_link.id, date_from, date_to)
    
    # Group slots by date
    slots_by_date = {}
    for slot in slots:
        date_str = slot['date']
        if date_str not in slots_by_date:
            slots_by_date[date_str] = []
        slots_by_date[date_str].append({
            'time': slot['time'],
            'end_time': slot['end_time']
        })
    
    return render_template(
        'public/booking.html',
        meeting_link=meeting_link,
        slots_by_date=slots_by_date,
        prefill_email=request.args.get('email', ''),
        prefill_name=request.args.get('name', '')
    )


@meeting_links_bp.route('/api/v1/public/book/<slug>/slots')
def public_get_slots(slug):
    """Get available slots for a meeting link (public)."""
    meeting_link = get_meeting_link_by_slug(slug)
    if not meeting_link:
        return jsonify({'error': 'Meeting link not found'}), 404
    
    # Parse date range
    date_from_str = request.args.get('date_from')
    date_to_str = request.args.get('date_to')
    
    if date_from_str:
        date_from = datetime.fromisoformat(date_from_str)
    else:
        date_from = datetime.utcnow()
    
    if date_to_str:
        date_to = datetime.fromisoformat(date_to_str)
    else:
        date_to = date_from + timedelta(days=30)
    
    slots = get_available_slots(meeting_link.id, date_from, date_to)
    
    # Convert datetime to string for JSON
    for slot in slots:
        slot['datetime'] = slot['datetime'].isoformat()
    
    return jsonify({
        'meeting_link': meeting_link.to_dict(),
        'slots': slots
    })


@meeting_links_bp.route('/api/v1/public/book/<slug>', methods=['POST'])
def public_create_booking(slug):
    """Create a booking (public - no auth required)."""
    meeting_link = get_meeting_link_by_slug(slug)
    if not meeting_link:
        return jsonify({'error': 'Meeting link not found'}), 404
    
    data = request.get_json() or request.form.to_dict()
    
    # Validate required fields
    required = ['booker_name', 'booker_email', 'start_time']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Parse start_time
    try:
        start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
    except ValueError:
        return jsonify({'error': 'Invalid start_time format'}), 400
    
    try:
        booking, contact = create_booking(
            meeting_link_id=meeting_link.id,
            booker_name=data['booker_name'],
            booker_email=data['booker_email'],
            start_time=start_time,
            booker_notes=data.get('booker_notes')
        )
        
        return jsonify({
            'success': True,
            'booking': booking.to_dict(),
            'contact': contact.to_dict() if contact else None,
            'message': 'Booking confirmed!'
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Booking failed: {e}")
        return jsonify({'error': 'Booking failed. Please try again.'}), 500


@meeting_links_bp.route('/api/v1/public/book/cancel/<token>', methods=['POST'])
def public_cancel_booking(token):
    """Cancel a booking using confirmation token (public)."""
    success = cancel_booking(booking_id=None, token=token)
    
    if success:
        return jsonify({'success': True, 'message': 'Booking cancelled'})
    else:
        return jsonify({'error': 'Booking not found'}), 404


# =============================================================================
# AUTHENTICATED ROUTES (CRM Internal)
# =============================================================================

@meeting_links_bp.route('/api/v1/meeting-links', methods=['GET'])
@login_required
def api_list_meeting_links():
    """List meeting links for current user's workspace."""
    workspace_id = get_workspace_id()
    if not workspace_id:
        return jsonify({'error': 'Workspace not found'}), 400
    
    user_id = request.args.get('user_id', type=int)
    links = list_meeting_links(workspace_id, user_id)
    
    return jsonify({
        'meeting_links': [link.to_dict() for link in links]
    })


@meeting_links_bp.route('/api/v1/meeting-links', methods=['POST'])
@login_required
def api_create_meeting_link():
    """Create a new meeting link."""
    workspace_id = get_workspace_id()
    if not workspace_id:
        return jsonify({'error': 'Workspace not found'}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    title = data.get('title')
    if not title:
        return jsonify({'error': 'Title is required'}), 400

    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        meeting_link = create_meeting_link(
            workspace_id=workspace_id,
            user_id=current_user.id,
            title=title,
            duration_minutes=data.get('duration_minutes', 30),
            buffer_minutes=data.get('buffer_minutes', 0),
            max_days_ahead=data.get('max_days_ahead', 60),
            availability_json=json.dumps(data['availability']) if data.get('availability') else None,
            video_provider=data.get('video_provider', 'none'),
            location=data.get('location'),
            description=data.get('description')
        )
        
        return jsonify({
            'success': True,
            'meeting_link': meeting_link.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Create meeting link failed: {e}")
        return jsonify({'error': 'Failed to create meeting link'}), 500


@meeting_links_bp.route('/api/v1/meeting-links/<int:meeting_link_id>', methods=['GET'])
@login_required
def api_get_meeting_link(meeting_link_id):
    """Get a specific meeting link."""
    meeting_link = get_meeting_link_by_id(meeting_link_id)
    if not meeting_link:
        return jsonify({'error': 'Meeting link not found'}), 404
    
    # Check workspace access
    if meeting_link.workspace_id != get_workspace_id():
        return jsonify({'error': 'Access denied'}), 403
    
    return jsonify({
        'meeting_link': meeting_link.to_dict()
    })


@meeting_links_bp.route('/api/v1/meeting-links/<int:meeting_link_id>', methods=['PATCH'])
@login_required
def api_update_meeting_link(meeting_link_id):
    """Update a meeting link."""
    meeting_link = get_meeting_link_by_id(meeting_link_id)
    if not meeting_link:
        return jsonify({'error': 'Meeting link not found'}), 404
    
    # Check workspace access
    if meeting_link.workspace_id != get_workspace_id():
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        updated = update_meeting_link(
            meeting_link_id=meeting_link_id,
            title=data.get('title'),
            duration_minutes=data.get('duration_minutes'),
            buffer_minutes=data.get('buffer_minutes'),
            max_days_ahead=data.get('max_days_ahead'),
            availability_json=json.dumps(data['availability']) if data.get('availability') else None,
            video_provider=data.get('video_provider'),
            location=data.get('location'),
            description=data.get('description'),
            is_active=data.get('is_active')
        )
        
        return jsonify({
            'success': True,
            'meeting_link': updated.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Update meeting link failed: {e}")
        return jsonify({'error': 'Failed to update meeting link'}), 500


@meeting_links_bp.route('/api/v1/meeting-links/<int:meeting_link_id>', methods=['DELETE'])
@login_required
def api_delete_meeting_link(meeting_link_id):
    """Delete a meeting link."""
    meeting_link = get_meeting_link_by_id(meeting_link_id)
    if not meeting_link:
        return jsonify({'error': 'Meeting link not found'}), 404
    
    # Check workspace access
    if meeting_link.workspace_id != get_workspace_id():
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        delete_meeting_link(meeting_link_id)
        return jsonify({'success': True, 'message': 'Meeting link deleted'})
        
    except Exception as e:
        current_app.logger.error(f"Delete meeting link failed: {e}")
        return jsonify({'error': 'Failed to delete meeting link'}), 500


@meeting_links_bp.route('/api/v1/meeting-links/<int:meeting_link_id>/bookings', methods=['GET'])
@login_required
def api_list_bookings(meeting_link_id):
    """List bookings for a meeting link."""
    meeting_link = get_meeting_link_by_id(meeting_link_id)
    if not meeting_link:
        return jsonify({'error': 'Meeting link not found'}), 404
    
    # Check workspace access
    if meeting_link.workspace_id != get_workspace_id():
        return jsonify({'error': 'Access denied'}), 403
    
    status = request.args.get('status')
    bookings = list_bookings(meeting_link_id, status)
    
    return jsonify({
        'bookings': [b.to_dict() for b in bookings]
    })


@meeting_links_bp.route('/api/v1/meeting-links/<int:meeting_link_id>/availability', methods=['GET'])
@login_required
def api_get_availability(meeting_link_id):
    """Get available slots for a meeting link."""
    meeting_link = get_meeting_link_by_id(meeting_link_id)
    if not meeting_link:
        return jsonify({'error': 'Meeting link not found'}), 404
    
    # Check workspace access
    if meeting_link.workspace_id != get_workspace_id():
        return jsonify({'error': 'Access denied'}), 403
    
    # Parse date range
    date_from_str = request.args.get('date_from')
    date_to_str = request.args.get('date_to')
    
    if date_from_str:
        date_from = datetime.fromisoformat(date_from_str)
    else:
        date_from = datetime.utcnow()
    
    if date_to_str:
        date_to = datetime.fromisoformat(date_to_str)
    else:
        date_to = date_from + timedelta(days=30)
    
    slots = get_available_slots(meeting_link_id, date_from, date_to)
    
    # Convert datetime to string for JSON
    for slot in slots:
        slot['datetime'] = slot['datetime'].isoformat()
    
    return jsonify({
        'slots': slots
    })


@meeting_links_bp.route('/api/v1/meeting-links/<int:meeting_link_id>/bookings/<int:booking_id>/cancel', methods=['POST'])
@login_required
def api_cancel_booking(meeting_link_id, booking_id):
    """Cancel a booking (authenticated)."""
    booking = MeetingBooking.query.get(booking_id)
    if not booking:
        return jsonify({'error': 'Booking not found'}), 404
    
    # Check workspace access
    if booking.workspace_id != get_workspace_id():
        return jsonify({'error': 'Access denied'}), 403
    
    success = cancel_booking(booking_id=booking_id)
    
    if success:
        return jsonify({'success': True, 'message': 'Booking cancelled'})
    else:
        return jsonify({'error': 'Failed to cancel booking'}), 500
