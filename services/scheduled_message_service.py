"""
Scheduled Message Service
Zamanlanmış mesaj yönetimi
"""
from models import db
from models_automation import ScheduledMessage
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class ScheduledMessageService:
    """Service for managing scheduled messages"""
    
    @staticmethod
    def create_scheduled_message(workspace_id, created_by, target_type, message_body, 
                                 scheduled_at, target_id=None, target_segment=None,
                                 template_id=None, schedule_type='once', 
                                 recurrence_pattern=None, recurrence_config=None):
        """Create a new scheduled message"""
        
        if not message_body or not message_body.strip():
            raise ValueError('Message body is required')
        
        if not scheduled_at:
            raise ValueError('Scheduled time is required')
        
        # Validate target
        if target_type not in ['conversation', 'customer', 'segment', 'broadcast']:
            raise ValueError('Invalid target type')
        
        if target_type in ['conversation', 'customer'] and not target_id:
            raise ValueError(f'target_id is required for {target_type}')
        
        if target_type == 'segment' and not target_segment:
            raise ValueError('target_segment is required for segment type')
        
        # Validate schedule type
        if schedule_type not in ['once', 'recurring']:
            raise ValueError('Invalid schedule type')
        
        if schedule_type == 'recurring' and not recurrence_pattern:
            raise ValueError('recurrence_pattern is required for recurring messages')
        
        # Create scheduled message
        scheduled_message = ScheduledMessage(
            workspace_id=workspace_id,
            target_type=target_type,
            target_id=target_id,
            target_segment=target_segment,
            message_body=message_body,
            template_id=template_id,
            schedule_type=schedule_type,
            scheduled_at=scheduled_at,
            recurrence_pattern=recurrence_pattern,
            recurrence_config=json.dumps(recurrence_config) if recurrence_config else None,
            status='pending',
            created_by=created_by
        )
        
        try:
            db.session.add(scheduled_message)
            db.session.commit()
            return scheduled_message
        except Exception as e:
            db.session.rollback()
            logger.error(f'Failed to create scheduled message: {e}')
            raise
    
    @staticmethod
    def list_scheduled_messages(workspace_id, status=None, target_type=None, 
                               page=1, per_page=50):
        """List scheduled messages with filters"""
        query = ScheduledMessage.query.filter_by(workspace_id=workspace_id)
        
        if status:
            query = query.filter_by(status=status)
        
        if target_type:
            query = query.filter_by(target_type=target_type)
        
        query = query.order_by(ScheduledMessage.scheduled_at.desc())
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return pagination
    
    @staticmethod
    def get_scheduled_message(message_id, workspace_id):
        """Get a scheduled message by ID"""
        return ScheduledMessage.query.filter_by(
            id=message_id,
            workspace_id=workspace_id
        ).first()
    
    @staticmethod
    def update_scheduled_message(message_id, workspace_id, **kwargs):
        """Update a scheduled message"""
        message = ScheduledMessageService.get_scheduled_message(message_id, workspace_id)
        
        if not message:
            raise ValueError('Scheduled message not found')
        
        # Can only update pending messages
        if message.status != 'pending':
            raise ValueError('Can only update pending messages')
        
        # Update allowed fields
        allowed_fields = [
            'message_body', 'scheduled_at', 'target_type', 'target_id',
            'target_segment', 'template_id', 'schedule_type',
            'recurrence_pattern', 'recurrence_config'
        ]
        
        for field in allowed_fields:
            if field in kwargs:
                value = kwargs[field]
                if field == 'recurrence_config' and value:
                    value = json.dumps(value)
                setattr(message, field, value)
        
        try:
            db.session.commit()
            return message
        except Exception as e:
            db.session.rollback()
            logger.error(f'Failed to update scheduled message: {e}')
            raise
    
    @staticmethod
    def cancel_scheduled_message(message_id, workspace_id):
        """Cancel a scheduled message"""
        message = ScheduledMessageService.get_scheduled_message(message_id, workspace_id)
        
        if not message:
            raise ValueError('Scheduled message not found')
        
        if message.status != 'pending':
            raise ValueError('Can only cancel pending messages')
        
        try:
            message.status = 'cancelled'
            db.session.commit()
            return message
        except Exception as e:
            db.session.rollback()
            logger.error(f'Failed to cancel scheduled message: {e}')
            raise
    
    @staticmethod
    def delete_scheduled_message(message_id, workspace_id):
        """Delete a scheduled message"""
        message = ScheduledMessageService.get_scheduled_message(message_id, workspace_id)
        
        if not message:
            raise ValueError('Scheduled message not found')
        
        try:
            db.session.delete(message)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f'Failed to delete scheduled message: {e}')
            raise
    
    @staticmethod
    def get_pending_messages(limit=100):
        """Get pending messages that are due to be sent"""
        now = datetime.utcnow()
        
        return ScheduledMessage.query.filter(
            ScheduledMessage.status == 'pending',
            ScheduledMessage.scheduled_at <= now
        ).limit(limit).all()
    
    @staticmethod
    def mark_as_sent(message_id):
        """Mark a message as sent"""
        message = ScheduledMessage.query.get(message_id)
        
        if not message:
            return False
        
        try:
            message.status = 'sent'
            message.sent_at = datetime.utcnow()
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f'Failed to mark message as sent: {e}')
            return False
    
    @staticmethod
    def mark_as_failed(message_id, error_message):
        """Mark a message as failed"""
        message = ScheduledMessage.query.get(message_id)
        
        if not message:
            return False
        
        try:
            message.status = 'failed'
            message.error_message = error_message
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f'Failed to mark message as failed: {e}')
            return False
    
    @staticmethod
    def serialize_message(message):
        """Serialize a scheduled message to dict"""
        if not message:
            return None
        
        recurrence_config = None
        if message.recurrence_config:
            try:
                recurrence_config = json.loads(message.recurrence_config)
            except json.JSONDecodeError:
                recurrence_config = None
        
        return {
            'id': message.id,
            'workspace_id': message.workspace_id,
            'target_type': message.target_type,
            'target_id': message.target_id,
            'target_segment': message.target_segment,
            'message_body': message.message_body,
            'template_id': message.template_id,
            'schedule_type': message.schedule_type,
            'scheduled_at': message.scheduled_at.isoformat() if message.scheduled_at else None,
            'recurrence_pattern': message.recurrence_pattern,
            'recurrence_config': recurrence_config,
            'status': message.status,
            'sent_at': message.sent_at.isoformat() if message.sent_at else None,
            'error_message': message.error_message,
            'created_by': message.created_by,
            'created_at': message.created_at.isoformat() if message.created_at else None
        }
