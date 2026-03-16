"""
Task Comment Service
Handles task comments and attachments
"""
from models import db
from models_crm import Task, TaskComment, TaskAttachment
from datetime import datetime
import os
from werkzeug.utils import secure_filename


class TaskCommentService:
    """Service for managing task comments and attachments"""
    
    @staticmethod
    def create_comment(task_id, user_id, content):
        """Create a new comment on a task"""
        # Verify task exists
        task = Task.query.get(task_id)
        if not task:
            raise ValueError('Task not found')
        
        comment = TaskComment(
            task_id=task_id,
            user_id=user_id,
            content=content
        )
        
        db.session.add(comment)
        db.session.commit()
        
        return comment
    
    @staticmethod
    def get_task_comments(task_id):
        """Get all comments for a task"""
        return TaskComment.query.filter_by(task_id=task_id).order_by(TaskComment.created_at.desc()).all()
    
    @staticmethod
    def delete_comment(comment_id, user_id):
        """Delete a comment (only by the author)"""
        comment = TaskComment.query.get(comment_id)
        if not comment:
            raise ValueError('Comment not found')
        
        if comment.user_id != user_id:
            raise PermissionError('You can only delete your own comments')
        
        db.session.delete(comment)
        db.session.commit()
        
        return True
    
    @staticmethod
    def create_attachment(task_id, user_id, file, upload_folder='uploads/tasks'):
        """Create a new attachment for a task"""
        # Verify task exists
        task = Task.query.get(task_id)
        if not task:
            raise ValueError('Task not found')
        
        # Secure filename
        filename = secure_filename(file.filename)
        
        # Create workspace-specific folder
        workspace_folder = os.path.join(upload_folder, f'workspace_{task.workspace_id}')
        os.makedirs(workspace_folder, exist_ok=True)
        
        # Add timestamp to filename to avoid conflicts
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        unique_filename = f'{timestamp}_{filename}'
        file_path = os.path.join(workspace_folder, unique_filename)
        
        # Save file
        file.save(file_path)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Create attachment record
        attachment = TaskAttachment(
            task_id=task_id,
            file_name=filename,
            file_path=file_path,
            file_size=file_size,
            uploaded_by=user_id
        )
        
        db.session.add(attachment)
        db.session.commit()
        
        return attachment
    
    @staticmethod
    def get_task_attachments(task_id):
        """Get all attachments for a task"""
        return TaskAttachment.query.filter_by(task_id=task_id).order_by(TaskAttachment.created_at.desc()).all()
    
    @staticmethod
    def delete_attachment(attachment_id, user_id):
        """Delete an attachment (only by the uploader)"""
        attachment = TaskAttachment.query.get(attachment_id)
        if not attachment:
            raise ValueError('Attachment not found')
        
        if attachment.uploaded_by != user_id:
            raise PermissionError('You can only delete your own attachments')
        
        # Delete file from disk
        if os.path.exists(attachment.file_path):
            os.remove(attachment.file_path)
        
        db.session.delete(attachment)
        db.session.commit()
        
        return True
