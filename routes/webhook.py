from flask import Blueprint, request, jsonify
import os
import logging
import hmac
import hashlib
from models import db, Customer, Conversation, Message
from realtime import emit_chat_message_event
from services.webhook_handler import WebhookHandler
from datetime import datetime

logger = logging.getLogger(__name__)
bp = Blueprint('webhook', __name__)

@bp.route('/webhook', methods=['GET'])
def verify_webhook():
    """Verify webhook for Meta WhatsApp API"""
    verify_token = os.getenv('WEBHOOK_VERIFY_TOKEN')
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if not verify_token:
        logger.error('WEBHOOK_VERIFY_TOKEN is not configured')
        return 'Forbidden', 403

    if mode == 'subscribe' and token and challenge and token == verify_token:
        return challenge, 200
    return 'Forbidden', 403

@bp.route('/webhook', methods=['POST'])
def handle_webhook():
    """Handle incoming webhook from Meta WhatsApp API"""
    app_secret = os.getenv('WHATSAPP_APP_SECRET')
    if app_secret:
        signature = request.headers.get('X-Hub-Signature-256', '')
        raw_body = request.get_data(cache=True) or b''
        expected = 'sha256=' + hmac.new(
            app_secret.encode('utf-8'),
            raw_body,
            hashlib.sha256
        ).hexdigest()
        if not signature or not hmac.compare_digest(signature, expected):
            logger.warning('Webhook signature verification failed')
            return jsonify({'status': 'forbidden'}), 403

    data = request.get_json()
    
    if not data or 'entry' not in data:
        return jsonify({'status': 'ignored'}), 200
    
    try:
        result = WebhookHandler.process_incoming_message(data)
        if result.get('status') == 'success' and result.get('workspace_id'):
            workspace_id = result.get('workspace_id')
            
            # Mark onboarding step as complete (first message = channel connected)
            from services.onboarding_service import OnboardingService
            OnboardingService.complete_step(workspace_id, 'channel_connected')
            
            try:
                emit_chat_message_event(result.get('message_id'), workspace_id=workspace_id)
            except Exception as emit_exc:
                logger.warning('Socket emit failed in webhook: %s', emit_exc)

            from routes.api import push_notification
            push_notification(
                result['workspace_id'],
                'new_message',
                {'conversation_id': result.get('conversation_id'), 'message_id': result.get('message_id')}
            )
        return jsonify(result), 200
    except Exception as e:
        logger.exception('Webhook işleme hatası: %s', e)
        return jsonify({'status': 'error', 'message': str(e)}), 200
