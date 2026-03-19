"""
Scheduled Messages Routes
API endpoints for scheduled message management
"""
from flask import Blueprint, request, jsonify, session
from functools import wraps
from services.scheduled_message_service import ScheduledMessageService
from models import db, User
from datetime import datetime

scheduled_messages_bp = Blueprint('scheduled_messages', __name__)


def login_required(f):
    """Session-based login required decorator"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        user = User.query.get(user_id)
        if not user or not user.workspace_id:
            return jsonify({'error': 'Workspace context missing'}), 401
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    """Get current user from session"""
    user_id = session.get('user_id')
    if user_id:
        return User.query.get(user_id)
    return None


# ============================================================================
# SCHEDULED MESSAGES CRUD
# ============================================================================

@scheduled_messages_bp.route('/api/v1/scheduled-messages', methods=['POST'])
@login_required
def create_scheduled_message():
    """Create a new scheduled message"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body is required'}), 400
    
    # Required fields
    required_fields = ['target_type', 'message_body', 'scheduled_at']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400
    
    # Parse scheduled_at
    try:
        scheduled_at = datetime.fromisoformat(data['scheduled_at'].replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return jsonify({'error': 'Invalid scheduled_at format. Use ISO 8601 format'}), 400
    
    # Parse recurrence_config if present
    recurrence_config = data.get('recurrence_config')
    
    try:
        message = ScheduledMessageService.create_scheduled_message(
            workspace_id=get_current_user().workspace_id,
            created_by=get_current_user().id,
            target_type=data['target_type'],
            message_body=data['message_body'],
            scheduled_at=scheduled_at,
            target_id=data.get('target_id'),
            target_segment=data.get('target_segment'),
            template_id=data.get('template_id'),
            schedule_type=data.get('schedule_type', 'once'),
            recurrence_pattern=data.get('recurrence_pattern'),
            recurrence_config=recurrence_config
        )
        
        return jsonify(ScheduledMessageService.serialize_message(message)), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@scheduled_messages_bp.route('/api/v1/scheduled-messages', methods=['GET'])
@login_required
def list_scheduled_messages():
    """List scheduled messages with filters"""
    status = request.args.get('status')
    target_type = request.args.get('target_type')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    
    pagination = ScheduledMessageService.list_scheduled_messages(
        workspace_id=get_current_user().workspace_id,
        status=status,
        target_type=target_type,
        page=page,
        per_page=per_page
    )
    
    messages = [ScheduledMessageService.serialize_message(msg) for msg in pagination.items]
    
    return jsonify({
        'messages': messages,
        'total': pagination.total,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'pages': pagination.pages
    })


@scheduled_messages_bp.route('/api/v1/scheduled-messages/<int:message_id>', methods=['GET'])
@login_required
def get_scheduled_message(message_id):
    """Get a scheduled message by ID"""
    message = ScheduledMessageService.get_scheduled_message(
        message_id,
        get_current_user().workspace_id
    )
    
    if not message:
        return jsonify({'error': 'Scheduled message not found'}), 404
    
    return jsonify(ScheduledMessageService.serialize_message(message))


@scheduled_messages_bp.route('/api/v1/scheduled-messages/<int:message_id>', methods=['PATCH'])
@login_required
def update_scheduled_message(message_id):
    """Update a scheduled message"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body is required'}), 400
    
    # Parse scheduled_at if present
    if 'scheduled_at' in data:
        try:
            data['scheduled_at'] = datetime.fromisoformat(data['scheduled_at'].replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return jsonify({'error': 'Invalid scheduled_at format'}), 400
    
    try:
        message = ScheduledMessageService.update_scheduled_message(
            message_id,
            get_current_user().workspace_id,
            **data
        )
        
        return jsonify(ScheduledMessageService.serialize_message(message))
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@scheduled_messages_bp.route('/api/v1/scheduled-messages/<int:message_id>/cancel', methods=['POST'])
@login_required
def cancel_scheduled_message(message_id):
    """Cancel a scheduled message"""
    try:
        message = ScheduledMessageService.cancel_scheduled_message(
            message_id,
            get_current_user().workspace_id
        )
        
        return jsonify(ScheduledMessageService.serialize_message(message))
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@scheduled_messages_bp.route('/api/v1/scheduled-messages/<int:message_id>', methods=['DELETE'])
@login_required
def delete_scheduled_message(message_id):
    """Delete a scheduled message"""
    try:
        ScheduledMessageService.delete_scheduled_message(
            message_id,
            get_current_user().workspace_id
        )
        
        return jsonify({'message': 'Scheduled message deleted'}), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
