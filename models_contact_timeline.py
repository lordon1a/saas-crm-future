"""
Contact & Company Timeline Models - Enterprise Grade
Handles notes and activity logs for contact/company detail pages
"""
from models import db
from datetime import datetime


class ContactNote(db.Model):
    """
    Notes attached to contacts (not conversations).
    Used in contact detail page timeline.
    """
    __tablename__ = 'contact_notes'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='contact_notes', lazy='joined')
    
    def __repr__(self):
        return f'<ContactNote id={self.id} contact_id={self.contact_id}>'
    
    def to_dict(self):
        """Convert to dictionary for API response"""
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'content': self.content,
            'user_id': self.user_id,
            'user_name': self.user.name if self.user else 'Unknown',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'type': 'note'
        }


class ContactActivityLog(db.Model):
    """
    System-generated activity logs for contacts.
    Tracks actions like: contact_created, contact_updated, deal_created, etc.
    """
    __tablename__ = 'contact_activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False, index=True)
    action_type = db.Column(db.String(50), nullable=False, index=True)  # contact_created, contact_updated, deal_created, email_sent, call_made
    description = db.Column(db.Text, nullable=False)
    metadata_json = db.Column(db.Text)  # JSON: additional data like deal_id, amount, etc.
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    user = db.relationship('User', backref='contact_activity_logs', lazy='joined')
    
    def __repr__(self):
        return f'<ContactActivityLog id={self.id} action={self.action_type}>'
    
    def to_dict(self):
        """Convert to dictionary for API response"""
        import json
        metadata = {}
        if self.metadata_json:
            try:
                metadata = json.loads(self.metadata_json)
            except:
                pass
        
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'action_type': self.action_type,
            'description': self.description,
            'metadata': metadata,
            'user_id': self.user_id,
            'user_name': self.user.name if self.user else 'System',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'type': 'activity'
        }


class CompanyNote(db.Model):
    """
    Notes attached to companies.
    Used in company detail page timeline.
    """
    __tablename__ = 'company_notes'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='company_notes', lazy='joined')

    def __repr__(self):
        return f'<CompanyNote id={self.id} company_id={self.company_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'company_id': self.company_id,
            'content': self.content,
            'user_id': self.user_id,
            'user_name': self.user.name if self.user else 'Unknown',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'type': 'note'
        }
