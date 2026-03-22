from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class DocTemplate(db.Model):
    __tablename__ = 'doc_templates'

    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(200), nullable=False)
    description  = db.Column(db.Text)
    file_path    = db.Column(db.String(500), nullable=False)   # disk / S3 path
    file_type    = db.Column(db.String(10), nullable=False)    # docx | pptx | html
    object_type  = db.Column(db.String(100))                   # e.g. "Lead", "Contact"
    field_map    = db.Column(db.JSON)                          # {placeholder: crm_field}
    is_active    = db.Column(db.Boolean, default=True)
    version      = db.Column(db.Integer, default=1)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    documents    = db.relationship('GeneratedDocument', backref='template', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'file_type': self.file_type,
            'object_type': self.object_type,
            'field_map': self.field_map,
            'version': self.version,
            'created_at': self.created_at.isoformat(),
        }


class GeneratedDocument(db.Model):
    __tablename__ = 'generated_documents'

    id           = db.Column(db.Integer, primary_key=True)
    template_id  = db.Column(db.Integer, db.ForeignKey('doc_templates.id'), nullable=False)
    record_id    = db.Column(db.Integer, nullable=False)       # CRM record ID
    record_type  = db.Column(db.String(100))                   # e.g. "Lead"
    output_path  = db.Column(db.String(500))                   # generated file path
    output_type  = db.Column(db.String(10))                    # pdf | docx | pptx
    status       = db.Column(db.String(20), default='pending') # pending|processing|done|error
    error_msg    = db.Column(db.Text)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            'id': self.id,
            'template_id': self.template_id,
            'record_id': self.record_id,
            'record_type': self.record_type,
            'output_type': self.output_type,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'download_url': f'/docgen/download/{self.id}' if self.status == 'done' else None,
        }
