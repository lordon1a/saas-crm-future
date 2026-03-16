import os
from services.customer_manager import CustomerManager
from services.conversation_manager import ConversationManager
from services.message_manager import MessageManager
from services.media_service import get_media_url_from_meta, download_and_save_media
from datetime import datetime

# Medya tipi etiketleri
MEDIA_TYPE_LABELS = {
    'image': '[🖼️ Görsel mesaj]',
    'audio': '[🎵 Ses mesajı]',
    'video': '[🎥 Video mesajı]',
    'document': '[📄 Dosya/Belge]',
    'sticker': '[😊 Sticker]',
    'location': '[📍 Konum]',
    'contacts': '[👤 Rehber paylaşımı]',
    'reaction': None,  # Reactions'ı yoksay
    'unsupported': '[⚠️ Desteklenmeyen mesaj tipi]',
}

class WebhookHandler:
    @staticmethod
    def verify_webhook(verify_token, challenge):
        """Verify webhook token"""
        expected_token = os.getenv('WEBHOOK_VERIFY_TOKEN')
        
        if verify_token == expected_token:
            return challenge, 200
        else:
            return 'Forbidden', 403
    
    @staticmethod
    def extract_message_data(payload):
        """Extract message data from Meta webhook payload"""
        try:
            entry = payload.get('entry', [])[0]
            changes = entry.get('changes', [])[0]
            value = changes.get('value', {})
            
            # Meta ID Extraction for Multi-Tenant Workspace Resolution
            metadata = value.get('metadata', {})
            whatsapp_phone_number_id = metadata.get('phone_number_id')
            
            contacts = value.get('contacts', [])
            messages = value.get('messages', [])
            
            if not messages:
                return None
            
            message = messages[0]
            contact = contacts[0] if contacts else {}
            
            phone_number = message.get('from')
            profile_name = contact.get('profile', {}).get('name', phone_number)
            meta_message_id = message.get('id')
            timestamp = message.get('timestamp')
            message_type = message.get('type', 'text')
            
            # Metin mesajı
            if message_type == 'text':
                message_body = message.get('text', {}).get('body', '')
                media_id = None
            # Reaction — yoksay
            elif message_type == 'reaction':
                return None
            # Medya mesajları
            else:
                label = MEDIA_TYPE_LABELS.get(message_type, f'[📎 {message_type} mesajı]')
                if label is None:
                    return None
                media_data = message.get(message_type, {})
                caption = media_data.get('caption', '')
                message_body = f"{label}{': ' + caption if caption else ''}"
                media_id = media_data.get('id')
            
            return {
                'whatsapp_phone_number_id': whatsapp_phone_number_id,
                'phone_number': phone_number,
                'profile_name': profile_name,
                'message_body': message_body,
                'meta_message_id': meta_message_id,
                'timestamp': timestamp,
                'message_type': message_type,
                'media_id': media_id
            }
        
        except (KeyError, IndexError) as e:
            raise ValueError(f"Invalid payload structure: {e}")
    
    @staticmethod
    def process_incoming_message(payload):
        """Process incoming message from webhook"""
        message_data = WebhookHandler.extract_message_data(payload)
        
        if not message_data:
            return {'status': 'ignored', 'reason': 'No processable message in payload'}
        
        has_media = message_data.get('media_id') and message_data.get('message_type') in ('image', 'audio', 'video', 'document', 'sticker')
        if not message_data.get('message_body') and not has_media:
            return {'status': 'ignored', 'reason': 'Empty message body and no media'}
            
        whatsapp_phone_number_id = message_data.get('whatsapp_phone_number_id')
        if not whatsapp_phone_number_id:
            return {'status': 'error', 'reason': 'Missing whatsapp_phone_number_id in metadata'}
            
        # Tenant Isolation: Find the Company (Workspace) that owns this WhatsApp Number
        from models import Workspace, db, Message
        workspace = Workspace.query.filter_by(whatsapp_phone_number_id=whatsapp_phone_number_id).first()
        
        if not workspace:
            return {'status': 'error', 'reason': f'No workspace found for number ID {whatsapp_phone_number_id}'}
        
        # Get or create customer (isolated by workspace_id)
        customer = CustomerManager.get_or_create_customer(
            workspace_id=workspace.id,
            phone_number=message_data['phone_number'],
            profile_name=message_data['profile_name']
        )
        
        # Get or create open conversation (isolated by workspace_id)
        conversation = ConversationManager.get_or_create_conversation(
            workspace_id=workspace.id,
            customer_id=customer.id
        )
        
        # Duplicate kontrolü — aynı meta_message_id varsa kaydetme
        from models import db, Message
        existing = Message.query.filter_by(
            meta_message_id=message_data['meta_message_id']
        ).first() if message_data.get('meta_message_id') else None
        
        if existing:
            return {
                'status': 'duplicate',
                'message_id': existing.id,
                'conversation_id': conversation.id,
                'customer_id': customer.id
            }
        
        # Medya varsa indir ve yerel path kaydet
        media_type = None
        media_url = None
        message_type = message_data.get('message_type', 'text')
        if message_type in ('image', 'audio', 'video', 'document', 'sticker') and message_data.get('media_id'):
            access_token = workspace.whatsapp_access_token
            if access_token:
                media_url_meta = get_media_url_from_meta(message_data['media_id'], access_token)
                if media_url_meta:
                    media_url = download_and_save_media(
                        media_url_meta, access_token, workspace.id, message_type
                    )
                    if media_url:
                        media_type = message_type
        
        message = MessageManager.save_incoming_message(
            conversation_id=conversation.id,
            message_body=message_data['message_body'],
            meta_message_id=message_data['meta_message_id'],
            media_type=media_type,
            media_url=media_url
        )
        
        # Update conversation last_message_at
        ConversationManager.update_last_message_time(conversation.id)
        
        # Otomatik yanıt kontrolü
        try:
            from services.automation_engine import AutoReplyEngine
            AutoReplyEngine.check_and_reply(message, conversation)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning('Auto-reply check failed: %s', e)
        
        # Otomatik atama (eğer atanmamışsa)
        if not conversation.assigned_to:
            try:
                from services.automation_engine import AssignmentEngine
                AssignmentEngine.auto_assign_conversation(conversation)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning('Auto-assignment failed: %s', e)
        
        # SSE Notification Push (yeni mesaj geldiğinde frontend'e bildir)
        try:
            from routes.api import push_notification
            push_notification(workspace.id, 'new_message', {
                'conversation_id': conversation.id,
                'customer_id': customer.id,
                'message_id': message.id,
                'preview': message_data['message_body'][:100]
            })
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning('SSE push failed: %s', e)
        
        return {
            'status': 'success',
            'workspace_id': workspace.id,
            'message_id': message.id,
            'conversation_id': conversation.id,
            'customer_id': customer.id
        }
