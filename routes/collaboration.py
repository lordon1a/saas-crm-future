from functools import wraps

from flask import Blueprint, jsonify, request, session

from services.collaboration_service import CollaborationService


bp = Blueprint('collaboration', __name__, url_prefix='/api/collaboration')


def _login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get('user_id') or not session.get('workspace_id'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)

    return wrapped


@bp.route('/notifications', methods=['GET'])
@_login_required
def list_notifications():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    limit = request.args.get('limit', default=30, type=int)
    return jsonify({
        'items': CollaborationService.list_notifications(workspace_id, user_id, limit=limit),
        'unread_count': CollaborationService.unread_count(workspace_id, user_id),
    }), 200


@bp.route('/notifications/unread-count', methods=['GET'])
@_login_required
def get_unread_count():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    return jsonify({'unread_count': CollaborationService.unread_count(workspace_id, user_id)}), 200


@bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@_login_required
def mark_notification_read(notification_id):
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    if not CollaborationService.mark_notification_read(workspace_id, user_id, notification_id):
        return jsonify({'error': 'Notification not found'}), 404
    return jsonify({'status': 'ok'}), 200


@bp.route('/notifications/read-all', methods=['POST'])
@_login_required
def mark_all_notifications_read():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    CollaborationService.mark_all_notifications_read(workspace_id, user_id)
    return jsonify({'status': 'ok'}), 200


@bp.route('/follows', methods=['GET'])
@_login_required
def list_follows():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    return jsonify({'items': CollaborationService.list_follows(workspace_id, user_id)}), 200


@bp.route('/follows', methods=['POST'])
@_login_required
def follow_entity():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json(silent=True) or {}
    entity_type = data.get('entity_type')
    entity_id = data.get('entity_id')

    if not entity_type or not entity_id:
        return jsonify({'error': 'entity_type and entity_id are required'}), 400

    try:
        row = CollaborationService.follow_entity(workspace_id, user_id, entity_type, int(entity_id))
        return jsonify({'id': row.id}), 201
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        return jsonify({'error': 'Follow operation failed'}), 500


@bp.route('/follows', methods=['DELETE'])
@_login_required
def unfollow_entity():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json(silent=True) or {}
    entity_type = data.get('entity_type')
    entity_id = data.get('entity_id')

    if not entity_type or not entity_id:
        return jsonify({'error': 'entity_type and entity_id are required'}), 400

    removed = CollaborationService.unfollow_entity(workspace_id, user_id, entity_type, int(entity_id))
    if not removed:
        return jsonify({'error': 'Follow not found'}), 404
    return jsonify({'status': 'ok'}), 200


@bp.route('/follows/status', methods=['GET'])
@_login_required
def follow_status():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    entity_type = request.args.get('entity_type', '').strip().lower()
    entity_id = request.args.get('entity_id', type=int)
    if not entity_type or not entity_id:
        return jsonify({'error': 'entity_type and entity_id are required'}), 400

    return jsonify({
        'is_following': CollaborationService.is_following(workspace_id, user_id, entity_type, entity_id),
    }), 200


@bp.route('/activity-feed', methods=['GET'])
@_login_required
def activity_feed():
    workspace_id = session.get('workspace_id')
    limit = request.args.get('limit', default=50, type=int)
    return jsonify({'items': CollaborationService.list_activity_feed(workspace_id, limit=limit)}), 200
