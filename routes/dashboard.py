"""
Dashboard API Routes

Endpoints for the daily action dashboard bell feature.
Provides prioritized action items, dismiss/complete actions, and settings management.
"""

from flask import Blueprint, jsonify, request, session
from functools import wraps
from services.action_dashboard_service import ActionDashboardService
from models import db, User

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')


def login_required(f):
    """Session-based login required decorator"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    """Get current user from session"""
    user_id = session.get('user_id')
    if user_id:
        return User.query.get(user_id)
    return None


@dashboard_bp.route('/actions', methods=['GET'])
@login_required
def get_actions():
    """
    Get prioritized action items for current user.
    
    Returns:
        JSON with actions list and count
    """
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Calculate action items
        actions = ActionDashboardService.calculate_action_items(
            workspace_id=current_user.workspace_id,
            user_id=current_user.id,
            limit=10
        )
        
        # Track widget viewed event
        ActionDashboardService.track_engagement(
            workspace_id=current_user.workspace_id,
            user_id=current_user.id,
            event_type='widget_viewed'
        )
        
        # Convert ActionItem dataclasses to dicts
        actions_data = [
            {
                'id': action.id,
                'action_type': action.action_type,
                'priority': action.priority,
                'priority_score': action.priority_score,
                'entity_type': action.entity_type,
                'entity_id': action.entity_id,
                'entity_name': action.entity_name,
                'recommended_action': action.recommended_action,
                'context': action.context,
                'last_activity_at': action.last_activity_at.isoformat() if action.last_activity_at else None
            }
            for action in actions
        ]
        
        return jsonify({
            'success': True,
            'actions': actions_data,
            'count': len(actions_data)
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Exception in get_actions: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dashboard_bp.route('/actions/<action_id>/dismiss', methods=['POST'])
@login_required
def dismiss_action(action_id):
    """
    Dismiss an action for 24 hours.
    
    Args:
        action_id: Action ID (format: "type:id")
        
    Returns:
        Success response
    """
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        success = ActionDashboardService.dismiss_action(
            workspace_id=current_user.workspace_id,
            user_id=current_user.id,
            action_id=action_id
        )
        
        if success:
            # Track engagement
            parts = action_id.split(':')
            action_type = parts[0] if len(parts) == 2 else None
            
            ActionDashboardService.track_engagement(
                workspace_id=current_user.workspace_id,
                user_id=current_user.id,
                event_type='action_dismissed',
                action_id=action_id,
                action_type=action_type
            )
            
            return jsonify({
                'success': True,
                'message': 'Action dismissed'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to dismiss action'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dashboard_bp.route('/actions/<action_id>/complete', methods=['POST'])
@login_required
def complete_action(action_id):
    """
    Complete an action (marks task as completed if task_overdue, otherwise dismisses).
    
    Args:
        action_id: Action ID (format: "type:id")
        
    Returns:
        Success response
    """
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        success = ActionDashboardService.complete_action(
            workspace_id=current_user.workspace_id,
            user_id=current_user.id,
            action_id=action_id
        )
        
        if success:
            # Track engagement
            parts = action_id.split(':')
            action_type = parts[0] if len(parts) == 2 else None
            
            ActionDashboardService.track_engagement(
                workspace_id=current_user.workspace_id,
                user_id=current_user.id,
                event_type='action_completed',
                action_id=action_id,
                action_type=action_type
            )
            
            return jsonify({
                'success': True,
                'message': 'Action completed'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to complete action'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dashboard_bp.route('/settings', methods=['GET'])
@login_required
def get_settings():
    """
    Get dashboard settings for current workspace.
    
    Returns:
        Settings as JSON
    """
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        settings = ActionDashboardService.get_or_create_settings(
            workspace_id=current_user.workspace_id
        )
        
        return jsonify({
            'success': True,
            'settings': settings.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dashboard_bp.route('/settings', methods=['PUT'])
@login_required
def update_settings():
    """
    Update dashboard settings (admin only).
    
    Returns:
        Updated settings as JSON
    """
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if user is admin
        if current_user.role not in ['admin', 'owner']:
            return jsonify({
                'success': False,
                'error': 'Admin access required'
            }), 403
        
        data = request.get_json()
        
        settings = ActionDashboardService.update_settings(
            workspace_id=current_user.workspace_id,
            data=data
        )
        
        return jsonify({
            'success': True,
            'settings': settings.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
