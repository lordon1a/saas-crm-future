from functools import wraps

from flask import Blueprint, jsonify, request, session

from services.system_health_service import SystemHealthService


bp = Blueprint('system_health', __name__, url_prefix='/api/settings/system-health')


def _login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get('user_id') or not session.get('workspace_id'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)

    return wrapped


@bp.route('/report', methods=['GET'])
@_login_required
def health_report():
    workspace_id = session.get('workspace_id')
    days = request.args.get('days', default=30, type=int)
    days = max(1, min(days, 365))
    return jsonify(SystemHealthService.generate_report(workspace_id, days=days)), 200
