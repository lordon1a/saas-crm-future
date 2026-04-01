"""Webchat routes for public widget and internal CRM inbox."""
from flask import Blueprint, request, jsonify, session
from functools import wraps

from models import User
from services.webchat_service import (
    init_public_session,
    add_public_message,
    poll_messages,
    list_open_sessions,
    get_session_messages,
    agent_reply,
    close_session,
    get_or_create_config,
    update_config,
)

webchat_bp = Blueprint('webchat', __name__)


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


def _workspace_id():
    return session.get('workspace_id')


@webchat_bp.route('/api/v1/public/chat/init', methods=['GET'])
def public_chat_init():
    workspace_id = request.args.get('workspace_id', type=int)
    if not workspace_id:
        return jsonify({'error': 'workspace_id is required'}), 400

    visitor_id = request.cookies.get('visitor_id') or request.args.get('visitor_id')
    source_url = request.args.get('source_url')
    name = request.args.get('name')
    email = request.args.get('email')

    try:
        chat_session = init_public_session(
            workspace_id=workspace_id,
            visitor_id=visitor_id,
            source_url=source_url,
            name=name,
            email=email,
        )
        return jsonify({'session': chat_session.to_dict()})
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400


@webchat_bp.route('/api/v1/public/chat/<int:session_id>/message', methods=['POST'])
def public_chat_message(session_id):
    data = request.get_json() or {}
    try:
        msg = add_public_message(session_id, data.get('content'))
        return jsonify({'message': msg.to_dict()})
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400


@webchat_bp.route('/api/v1/public/chat/<int:session_id>/poll', methods=['GET'])
def public_chat_poll(session_id):
    since_id = request.args.get('since_id', 0, type=int)
    messages = poll_messages(session_id, since_id)
    return jsonify({'messages': [m.to_dict() for m in messages]})


@webchat_bp.route('/api/v1/webchat/sessions', methods=['GET'])
@login_required
def api_webchat_sessions():
    workspace_id = _workspace_id()
    sessions = list_open_sessions(workspace_id)
    return jsonify({'sessions': [s.to_dict() for s in sessions]})


@webchat_bp.route('/api/v1/webchat/sessions/<int:session_id>/messages', methods=['GET'])
@login_required
def api_webchat_session_messages(session_id):
    workspace_id = _workspace_id()
    chat_session, messages = get_session_messages(workspace_id, session_id)
    if not chat_session:
        return jsonify({'error': 'Session not found'}), 404

    return jsonify({
        'session': chat_session.to_dict(),
        'messages': [m.to_dict() for m in messages],
    })


@webchat_bp.route('/api/v1/webchat/sessions/<int:session_id>/reply', methods=['POST'])
@login_required
def api_webchat_reply(session_id):
    data = request.get_json() or {}
    try:
        msg = agent_reply(
            workspace_id=_workspace_id(),
            session_id=session_id,
            agent_id=session.get('user_id'),
            content=data.get('content'),
        )
        return jsonify({'message': msg.to_dict()})
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400


@webchat_bp.route('/api/v1/webchat/sessions/<int:session_id>/close', methods=['POST'])
@login_required
def api_webchat_close(session_id):
    try:
        closed = close_session(_workspace_id(), session_id)
        return jsonify({'session': closed.to_dict()})
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 404


@webchat_bp.route('/api/v1/webchat/config', methods=['GET'])
@login_required
def api_webchat_config():
    cfg = get_or_create_config(_workspace_id())
    return jsonify({'config': cfg.to_dict()})


@webchat_bp.route('/api/v1/webchat/config', methods=['PATCH'])
@login_required
def api_update_webchat_config():
    data = request.get_json() or {}
    cfg = update_config(_workspace_id(), data)
    return jsonify({'config': cfg.to_dict()})
