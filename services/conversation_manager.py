from models import db, Conversation
from datetime import datetime

class ConversationManager:
    @staticmethod
    def get_or_create_conversation(workspace_id, customer_id):
        """Get open conversation for customer or create new one in a workspace"""
        conversation = Conversation.query.filter_by(
            workspace_id=workspace_id,
            customer_id=customer_id,
            status='open'
        ).first()
        
        if conversation:
            return conversation
        
        # Create new conversation
        conversation = Conversation(
            workspace_id=workspace_id,
            customer_id=customer_id,
            status='open',
            last_message_at=datetime.utcnow()
        )
        db.session.add(conversation)
        db.session.commit()
        
        return conversation
    
    @staticmethod
    def get_conversations(workspace_id, status=None, limit=50):
        """Get conversations sorted by last_message_at for a specific workspace"""
        query = Conversation.query.filter_by(workspace_id=workspace_id)
        
        if status:
            query = query.filter_by(status=status)
        
        conversations = query.order_by(Conversation.last_message_at.desc()).limit(limit).all()
        return conversations
    
    @staticmethod
    def update_conversation_tag(workspace_id, conversation_id, tag):
        """Update conversation tag verifying workspace ownership"""
        conversation = Conversation.query.filter_by(id=conversation_id, workspace_id=workspace_id).first()
        if not conversation:
            raise ValueError(f"Conversation with id {conversation_id} not found in this workspace")
        
        # Validate tag
        valid_tags = ['yeni_siparis', 'kargo_sorunu', 'odeme_bekliyor', '', 'kargolandi']
        if tag and tag not in valid_tags:
            raise ValueError(f"Invalid tag: {tag}. Must be one of {valid_tags}")
        
        conversation.tags = tag if tag else None
        db.session.commit()
        
        return conversation
    
    @staticmethod
    def update_last_message_time(conversation_id, timestamp=None):
        """Update conversation's last_message_at"""
        conversation = Conversation.query.get(conversation_id)
        if conversation:
            conversation.last_message_at = timestamp or datetime.utcnow()
            db.session.commit()
    
    @staticmethod
    def close_conversation(workspace_id, conversation_id):
        """Close a conversation verifying workspace ownership"""
        conversation = Conversation.query.filter_by(id=conversation_id, workspace_id=workspace_id).first()
        if not conversation:
            raise ValueError(f"Conversation with id {conversation_id} not found in this workspace")
        
        conversation.status = 'resolved'
        db.session.commit()
        
        return conversation
