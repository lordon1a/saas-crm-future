import logging
from datetime import datetime

import requests

from models import Conversation, Customer, Message, Workspace, db
from models_crm import Activity, Contact
from services.conversation_manager import ConversationManager
from services.message_manager import MessageManager

logger = logging.getLogger(__name__)


class TelegramService:
    def __init__(self, bot_token):
        self.bot_token = (bot_token or '').strip()
        self.base_url = f'https://api.telegram.org/bot{self.bot_token}' if self.bot_token else None

    def send_message(self, chat_id, text):
        if not self.base_url:
            return {'success': False, 'error': 'Telegram bot token not configured'}

        url = f'{self.base_url}/sendMessage'
        payload = {
            'chat_id': str(chat_id),
            'text': text,
        }
        try:
            response = requests.post(url, json=payload, timeout=12)
            data = response.json() if response.content else {}
            if not response.ok or not data.get('ok'):
                return {'success': False, 'error': (data.get('description') if isinstance(data, dict) else None) or response.text}
            message_id = ((data.get('result') or {}).get('message_id'))
            return {'success': True, 'message_id': f'tg-{message_id}' if message_id is not None else None}
        except Exception as exc:
            logger.exception('Telegram send_message failed: %s', exc)
            return {'success': False, 'error': str(exc)}

    def set_webhook(self, url, secret_token=None):
        if not self.base_url:
            return {'success': False, 'error': 'Telegram bot token not configured'}

        endpoint = f'{self.base_url}/setWebhook'
        payload = {'url': url}
        if secret_token:
            payload['secret_token'] = secret_token

        try:
            response = requests.post(endpoint, json=payload, timeout=12)
            data = response.json() if response.content else {}
            if not response.ok or not data.get('ok'):
                return {'success': False, 'error': (data.get('description') if isinstance(data, dict) else None) or response.text}
            return {'success': True, 'result': data.get('result')}
        except Exception as exc:
            logger.exception('Telegram set_webhook failed: %s', exc)
            return {'success': False, 'error': str(exc)}

    def handle_incoming_message(self, payload, workspace_id):
        try:
            message_data = payload.get('message') or payload.get('edited_message')
            if not message_data:
                return {'success': True, 'status': 'ignored', 'reason': 'No message payload'}

            chat = message_data.get('chat') or {}
            chat_id = str(chat.get('id') or '').strip()
            if not chat_id:
                return {'success': False, 'status': 'error', 'error': 'chat_id missing'}

            text = (message_data.get('text') or '').strip()
            if not text:
                text = (message_data.get('caption') or '').strip() or '[Telegram mesajı]'

            update_id = payload.get('update_id')
            telegram_message_id = message_data.get('message_id')
            dedupe_id = f'tg-{update_id}' if update_id is not None else (f'tg-msg-{telegram_message_id}' if telegram_message_id is not None else None)

            existing = Message.query.filter_by(meta_message_id=dedupe_id).first() if dedupe_id else None
            if existing:
                return {
                    'success': True,
                    'status': 'duplicate',
                    'conversation_id': existing.conversation_id,
                    'message_id': existing.id,
                }

            workspace = Workspace.query.filter_by(id=workspace_id).first()
            if not workspace:
                return {'success': False, 'status': 'error', 'error': 'Workspace not found'}

            customer = Customer.query.filter_by(workspace_id=workspace_id, telegram_chat_id=chat_id).first()
            if not customer:
                contact = Contact.query.filter_by(workspace_id=workspace_id, telegram_chat_id=chat_id).first()
                if contact and contact.customer_id:
                    customer = Customer.query.filter_by(id=contact.customer_id, workspace_id=workspace_id).first()

            from_user = message_data.get('from') or {}
            profile_name = (chat.get('first_name') or from_user.get('first_name') or from_user.get('username') or f'Telegram {chat_id}').strip()

            if not customer:
                customer = Customer(
                    workspace_id=workspace_id,
                    phone_number=f'tg:{chat_id}',
                    profile_name=profile_name,
                    telegram_chat_id=chat_id,
                )
                db.session.add(customer)
                db.session.flush()
            elif not customer.telegram_chat_id:
                customer.telegram_chat_id = chat_id

            conversation = ConversationManager.get_or_create_conversation(workspace_id=workspace_id, customer_id=customer.id)

            message = MessageManager.save_incoming_message(
                conversation_id=conversation.id,
                message_body=text,
                meta_message_id=dedupe_id,
                channel='telegram',
            )
            ConversationManager.update_last_message_time(conversation.id, timestamp=datetime.utcnow())

            contact = Contact.query.filter_by(workspace_id=workspace_id, customer_id=customer.id).first()
            if not contact:
                contact = Contact(
                    workspace_id=workspace_id,
                    customer_id=customer.id,
                    first_name=profile_name,
                    phone=customer.phone_number,
                    telegram_chat_id=chat_id,
                )
                db.session.add(contact)
            elif not contact.telegram_chat_id:
                contact.telegram_chat_id = chat_id

            activity = Activity(
                workspace_id=workspace_id,
                activity_type='telegram',
                contact_id=contact.id if contact else None,
                user_id=None,
                subject='Telegram mesajı',
                body=text[:2000],
            )
            db.session.add(activity)
            db.session.commit()

            return {
                'success': True,
                'status': 'processed',
                'conversation_id': conversation.id,
                'customer_id': customer.id,
                'message_id': message.id,
            }
        except Exception as exc:
            db.session.rollback()
            logger.exception('Telegram incoming message process failed: %s', exc)
            return {'success': False, 'status': 'error', 'error': str(exc)}
