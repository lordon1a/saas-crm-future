"""
Assignment Routes
Handles entity assignment operations for team members
"""
from flask import Blueprint, request, jsonify, session
from functools import wraps
import logging
from models import db, User
from services.assignment_service import AssignmentService
from realtime import socketio

logger = logging.getLogger(__name__)

bp = Blueprint('assignments', __name__, url_prefix='/api/assignments')


def login_required(f):
    """Decorator to require authentication for endpoints"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id') or not session.get('workspace_id'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


def check_assignment_permission(user_role, entity_type):
    """
    Check if user has permission to assign entities
    
    Requirements: 6.5, 6.6, 6.7
    - owner and admin: can assign any entity
    - member: can assign entities they own or are assigned to
    - viewer: cannot assign
    """
    if user_role in ['owner', 'admin']:
        return True
    elif user_role == 'member':
        # Member can assign, but service layer will validate ownership
        return True
    elif user_role == 'viewer':
        return False
    return False


# ============================================================================
# PUT /api/assignments/<entity_type>/<id> - Assign entity to team member
# ============================================================================

@bp.route('/<entity_type>/<int:entity_id>', methods=['PUT'])
@login_required
def assign_entity(entity_type, entity_id):
    """
    Assign a CRM entity to a team member
    
    Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 18.1, 18.2, 18.3, 18.4, 18.5, 18.6, 18.7
    
    Request body:
    {
        "assignee_id": 123  // User ID to assign to, or null to unassign
    }
    """
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        
        # Check permission
        if not check_assignment_permission(user_role, entity_type):
            return jsonify({'error': 'Forbidden: Viewers cannot assign entities'}), 403
        
        # Get request data
        data = request.get_json()
        if data is None:
            return jsonify({'error': 'Request body is required'}), 400
        
        assignee_id = data.get('assignee_id')
        
        # Handle unassignment
        if assignee_id is None:
            result = AssignmentService.unassign_entity(
                workspace_id=workspace_id,
                entity_type=entity_type,
                entity_id=entity_id,
                unassigned_by_id=user_id
            )
            
            # Get user name for notification
            assigned_by = User.query.get(user_id)
            
            # Emit Socket.IO notification
            if socketio and entity_type == 'conversation':
                try:
                    socketio.emit('assignment_updated', {
                        'conversation_id': entity_id,
                        'assignee_id': None,
                        'assignee_name': None,
                        'assigned_by_id': user_id,
                        'assigned_by_name': assigned_by.name if assigned_by else None,
                        'entity_type': entity_type
                    }, room=f'workspace_{workspace_id}')
                    logger.info(f"Emitted assignment_updated (unassign) for conversation {entity_id}")
                except Exception as e:
                    logger.error(f"Failed to emit Socket.IO notification: {str(e)}")
            
            return jsonify({
                'status': 'ok',
                'message': f'{entity_type.capitalize()} unassigned successfully',
                'entity_id': entity_id,
                'assigned_to': None
            }), 200
        
        # Validate assignee_id
        if not isinstance(assignee_id, int):
            return jsonify({'error': 'assignee_id must be an integer or null'}), 400
        
        # Assign entity
        result = AssignmentService.assign_entity(
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            assignee_id=assignee_id,
            assigned_by_id=user_id
        )
        
        # Get user names for notification
        assigned_by = User.query.get(user_id)
        assignee = User.query.get(assignee_id)
        
        # Emit Socket.IO notification
        if socketio and entity_type == 'conversation':
            try:
                socketio.emit('assignment_updated', {
                    'conversation_id': entity_id,
                    'assignee_id': assignee_id,
                    'assignee_name': assignee.name if assignee else None,
                    'assigned_by_id': user_id,
                    'assigned_by_name': assigned_by.name if assigned_by else None,
                    'entity_type': entity_type
                }, room=f'workspace_{workspace_id}')
                logger.info(f"Emitted assignment_updated for conversation {entity_id}")
            except Exception as e:
                logger.error(f"Failed to emit Socket.IO notification: {str(e)}")
        
        return jsonify({
            'status': 'ok',
            'message': f'{entity_type.capitalize()} assigned successfully',
            'entity_id': entity_id,
            'assigned_to': assignee_id
        }), 200
        
    except ValueError as e:
        logger.warning(f"Assignment validation failed: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to assign entity: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to assign entity'}), 500


# ============================================================================
# GET /api/assignments/members - Get assignable team members
# ============================================================================

@bp.route('/members', methods=['GET'])
@login_required
def get_assignable_members():
    """
    Get list of active team members who can be assigned to entities
    
    Requirements: 6.3, 18.1, 18.2, 18.3
    
    Returns:
    {
        "members": [
            {
                "id": 1,
                "name": "John Doe",
                "email": "john@example.com",
                "role": "admin"
            },
            ...
        ]
    }
    """
    try:
        workspace_id = session.get('workspace_id')
        
        # Get assignable members
        members = AssignmentService.get_assignable_members(workspace_id)
        
        return jsonify({
            'status': 'ok',
            'members': members
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get assignable members: {str(e)}")
        return jsonify({'error': 'Failed to retrieve team members'}), 500
