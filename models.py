from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Workspace(db.Model):
    __tablename__ = 'workspaces'
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Meta (WhatsApp) Integrations per tenant
    whatsapp_phone_number_id = db.Column(db.String(100), unique=True, index=True)
    whatsapp_access_token = db.Column(db.Text)
    waba_id = db.Column(db.String(100))
    telegram_bot_token = db.Column(db.Text)

    users = db.relationship('User', backref='workspace', lazy=True)
    customers = db.relationship('Customer', backref='workspace', lazy=True)
    conversations = db.relationship('Conversation', backref='workspace', lazy=True)
    quick_replies = db.relationship('QuickReply', backref='workspace', lazy=True)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='agent', nullable=False)
    messages = db.relationship('Message', backref='sender', lazy=True)

class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    phone_number = db.Column(db.String(50), nullable=False, index=True)
    profile_name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    company = db.Column(db.String(100))
    job_title = db.Column(db.String(100))
    labels = db.Column(db.String(255)) # comma separated tags
    notes = db.Column(db.Text)
    private_notes = db.Column(db.Text)
    telegram_chat_id = db.Column(db.String(100), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    conversations = db.relationship('Conversation', backref='customer', lazy=True, cascade="all, delete-orphan")
    
    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'phone_number', name='uix_workspace_phone'),
    )

class Conversation(db.Model):
    __tablename__ = 'conversations'
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default='open', nullable=False, index=True)
    tags = db.Column(db.String(255))
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    notes = db.Column(db.Text)
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    messages = db.relationship('Message', backref='conversation', lazy=True, order_by='Message.created_at', cascade="all, delete-orphan")
    conv_notes = db.relationship('Note', backref='conversation', lazy=True, cascade="all, delete-orphan")

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False, index=True)
    sender_type = db.Column(db.String(20), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    message_body = db.Column(db.Text, nullable=False)
    channel = db.Column(db.String(20), default='whatsapp', nullable=False, index=True)
    meta_message_id = db.Column(db.String(100), unique=True, index=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    # Medya: image, audio, video, document, sticker
    media_type = db.Column(db.String(20), nullable=True)
    media_url = db.Column(db.String(500), nullable=True)

class QuickReply(db.Model):
    __tablename__ = 'quick_replies'
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    title = db.Column(db.String(100), nullable=False)
    body = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))

class Note(db.Model):
    __tablename__ = 'notes'
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    is_internal = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

class MessageTemplate(db.Model):
    __tablename__ = 'message_templates'
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)          # Kullanıcı dostu ad (Sipariş Onayı)
    body = db.Column(db.Text, nullable=False)                  # Mesaj içeriği
    category = db.Column(db.String(50), default='custom')      # marketing | utility | custom
    language = db.Column(db.String(10), default='tr')          # tr, en ...
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    workspace = db.relationship('Workspace', backref=db.backref('templates', lazy=True), foreign_keys=[workspace_id])
