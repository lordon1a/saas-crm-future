from models import db, QuickReply

class QuickReplyManager:
    @staticmethod
    def get_all_quick_replies(workspace_id):
        """Get all quick replies for a specific workspace"""
        return QuickReply.query.filter_by(workspace_id=workspace_id).all()
    
    @staticmethod
    def create_quick_reply(workspace_id, title, body, category=None):
        """Create a new quick reply within a workspace"""
        quick_reply = QuickReply(workspace_id=workspace_id, title=title, body=body, category=category)
        db.session.add(quick_reply)
        db.session.commit()
        return quick_reply
    
    @staticmethod
    def get_quick_reply_by_id(workspace_id, reply_id):
        """Get quick reply by ID and verify workspace ownership"""
        return QuickReply.query.filter_by(id=reply_id, workspace_id=workspace_id).first()
