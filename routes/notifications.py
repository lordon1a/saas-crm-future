"""
Notification Routes
API endpoints for task notifications and notification preferences
"""
from flask import Blueprint, request, jsonify, session
from functools import wraps
from services.notification_service import NotificationService
from models import db, User
import logging

logger = logging.getLogger(__name__)
notifications_bp = Blueprint('notifications', __name__)


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
# NOTIFICATION ENDPOINTS
# ============================================================================

@notifications_bp.route('/api/v1/notifications', methods=['GET'])
@login_required
def get_notifications():
    """
    Get user notifications with pagination and filters
    
    Query params:
        - page: Page number (default 1)
        - per_page: Items per page (default 50, max 100)
        - unread_only: Filter unread notifications (true/false)
    """
    current_user = get_current_user()
    
    # Parse query parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    unread_only = request.args.get('unread_only', '').lower() == 'true'
    
    # Limit per_page to max 100
    if per_page > 100:
        per_page = 100
    
    try:
        # Calculate offset for pagination
        limit = per_page
        
        # Get notifications
        notifications = NotificationService.get_user_notifications(
            workspace_id=current_user.workspace_id,
            user_id=current_user.id,
            unread_only=unread_only,
            limit=limit
        )
        
        # Get unread count
        unread_count = NotificationService.get_unread_count(
            workspace_id=current_user.workspace_id,
            user_id=current_user.id
        )
        
        return jsonify({
            'notifications': [{
                'id': n.id,
                'task_id': n.task_id,
                'message': n.message,
                'notification_type': n.notification_type,
                'is_read': n.is_read,
                'created_at': n.created_at.isoformat(),
                'read_at': n.read_at.isoformat() if n.read_at else None
            } for n in notifications],
            'unread_count': unread_count,
            'page': page,
            'per_page': per_page
        })
        
    except Exception as e:
        logger.error(f"Error fetching notifications: {str(e)}")
        return jsonify({'error': 'Bildirimler getirilirken hata oluştu'}), 500


@notifications_bp.route('/api/v1/notifications/<int:notification_id>/read', methods=['PATCH'])
@login_required
def mark_notification_read(notification_id):
    """
    Mark a notification as read
    
    Path params:
        - notification_id: Notification ID
    """
    current_user = get_current_user()
    
    try:
        success = NotificationService.mark_as_read(
            notification_id=notification_id,
            user_id=current_user.id
        )
        
        if not success:
            return jsonify({'error': 'Bildirim bulunamadı'}), 404
        
        return jsonify({
            'message': 'Bildirim okundu olarak işaretlendi',
            'notification_id': notification_id
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error marking notification as read: {str(e)}")
        return jsonify({'error': 'Bildirim güncellenirken hata oluştu'}), 500


@notifications_bp.route('/api/v1/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """
    Mark all notifications as read for the current user
    """
    current_user = get_current_user()
    
    try:
        count = NotificationService.mark_all_as_read(
            workspace_id=current_user.workspace_id,
            user_id=current_user.id
        )
        
        return jsonify({
            'message': 'Tüm bildirimler okundu olarak işaretlendi',
            'count': count
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error marking all notifications as read: {str(e)}")
        return jsonify({'error': 'Bildirimler güncellenirken hata oluştu'}), 500


# ============================================================================
# NOTIFICATION PREFERENCES
# ============================================================================

@notifications_bp.route('/api/v1/notifications/preferences', methods=['GET'])
@login_required
def get_notification_preferences():
    """
    Get notification preferences for the current user
    """
    current_user = get_current_user()
    
    try:
        preferences = NotificationService.get_or_create_preferences(
            workspace_id=current_user.workspace_id,
            user_id=current_user.id
        )
        
        return jsonify({
            'task_reminder_enabled': preferences.task_reminder_enabled,
            'task_overdue_enabled': preferences.task_overdue_enabled,
            'task_assigned_enabled': preferences.task_assigned_enabled,
            'task_updated_enabled': preferences.task_updated_enabled,
            'reminder_minutes_before': preferences.reminder_minutes_before,
            'updated_at': preferences.updated_at.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error fetching notification preferences: {str(e)}")
        return jsonify({'error': 'Bildirim tercihleri getirilirken hata oluştu'}), 500


@notifications_bp.route('/api/v1/notifications/preferences', methods=['PUT'])
@login_required
def update_notification_preferences():
    """
    Update notification preferences for the current user
    
    Request body:
    {
        "task_reminder_enabled": true,
        "task_overdue_enabled": true,
        "task_assigned_enabled": true,
        "task_updated_enabled": false,
        "reminder_minutes_before": 15
    }
    """
    current_user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Veri sağlanmadı'}), 400
    
    # Validate reminder_minutes_before if provided
    if 'reminder_minutes_before' in data:
        valid_values = [0, 5, 10, 15, 30, 60, 120, 1440]
        if data['reminder_minutes_before'] not in valid_values:
            return jsonify({
                'error': f'Geçersiz hatırlatma süresi. Geçerli değerler: {valid_values}'
            }), 400
    
    try:
        preferences = NotificationService.update_preferences(
            workspace_id=current_user.workspace_id,
            user_id=current_user.id,
            data=data
        )
        
        return jsonify({
            'message': 'Bildirim tercihleri güncellendi',
            'task_reminder_enabled': preferences.task_reminder_enabled,
            'task_overdue_enabled': preferences.task_overdue_enabled,
            'task_assigned_enabled': preferences.task_assigned_enabled,
            'task_updated_enabled': preferences.task_updated_enabled,
            'reminder_minutes_before': preferences.reminder_minutes_before,
            'updated_at': preferences.updated_at.isoformat()
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating notification preferences: {str(e)}")
        return jsonify({'error': 'Bildirim tercihleri güncellenirken hata oluştu'}), 500
