import logging

from flask import Blueprint, jsonify, request

from models import Workspace
from routes.api import push_notification
from realtime import emit_chat_message_event, socketio
from services.telegram_service import TelegramService

logger = logging.getLogger(__name__)

telegram_bp = Blueprint('telegram', __name__, url_prefix='/api/v1')


@telegram_bp.route('/webhooks/telegram', methods=['POST'])
def telegram_webhook():
    payload = request.get_json(silent=True) or {}
    workspace_id = request.args.get('workspace_id', type=int)
    if not workspace_id:
        return jsonify({'status': 'ignored', 'reason': 'workspace_id is required'}), 200

    workspace = Workspace.query.filter_by(id=workspace_id).first()
    if not workspace or not workspace.telegram_bot_token:
        return jsonify({'status': 'ignored', 'reason': 'workspace/token not configured'}), 200

    secret_header = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
    expected_secret = f'tg_ws_{workspace_id}'
    if secret_header and secret_header != expected_secret:
        return jsonify({'status': 'forbidden'}), 403

    service = TelegramService(workspace.telegram_bot_token)
    result = service.handle_incoming_message(payload, workspace_id=workspace_id)

    if result.get('success') and result.get('conversation_id'):
        try:
            if not result.get('emitted_realtime'):
                emit_chat_message_event(result.get('message_id'), workspace_id=workspace_id)

            socketio.emit(
                'telegram_webhook_processed',
                {
                    'workspace_id': workspace_id,
                    'conversation_id': result.get('conversation_id'),
                    'contact_id': result.get('customer_id'),
                    'message_id': result.get('message_id'),
                },
                room=f'ws_{workspace_id}',
            )

            push_notification(
                workspace_id,
                'new_message',
                {
                    'conversation_id': result.get('conversation_id'),
                    'message_id': result.get('message_id'),
                    'customer_id': result.get('customer_id'),
                },
            )
        except Exception as exc:
            logger.warning('Telegram realtime push failed: %s', exc)

    return jsonify(result), 200
