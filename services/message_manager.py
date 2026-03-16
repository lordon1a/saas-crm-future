from models import db, Message
from datetime import datetime

class MessageManager:
    @staticmethod
    def save_incoming_message(conversation_id, message_body, meta_message_id, media_type=None, media_url=None):
        """Save incoming message from customer (optional media)."""
        message = Message(
            conversation_id=conversation_id,
            sender_type='customer',
            sender_id=None,
            message_body=message_body,
            meta_message_id=meta_message_id,
            media_type=media_type,
            media_url=media_url
        )
        db.session.add(message)
        db.session.commit()
        return message

    @staticmethod
    def save_outgoing_message(conversation_id, message_body, sender_id, meta_message_id, media_type=None, media_url=None):
        """Save outgoing message from agent (optional media)."""
        message = Message(
            conversation_id=conversation_id,
            sender_type='agent',
            sender_id=sender_id,
            message_body=message_body,
            meta_message_id=meta_message_id,
            media_type=media_type,
            media_url=media_url
        )
        db.session.add(message)
        db.session.commit()
        return message
    
    @staticmethod
    def get_conversation_messages(conversation_id):
        """Get all messages for a conversation sorted by created_at"""
        messages = Message.query.filter_by(
            conversation_id=conversation_id
        ).order_by(Message.created_at.asc()).all()
        
        return messages
