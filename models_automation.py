"""
Automation & Workflow Models
Otomasyon ve iş akışı yönetimi için veritabanı modelleri
"""
from models import db
from datetime import datetime

class AutomationRule(db.Model):
    """
    Otomasyon kuralları
    Örnek: Yeni müşteri geldiğinde hoş geldin mesajı gönder
    """
    __tablename__ = 'automation_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    
    # Kural bilgileri
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Trigger (Ne zaman çalışsın?)
    trigger_type = db.Column(db.String(50), nullable=False)  # new_conversation, keyword, tag_added, time_based, inactivity
    trigger_config = db.Column(db.Text)  # JSON: keyword, tag, time, etc.
    
    # Conditions (Hangi koşullarda?)
    conditions = db.Column(db.Text)  # JSON: customer_tag, conversation_tag, time_range, etc.
    
    # Actions (Ne yapsın?)
    actions = db.Column(db.Text, nullable=False)  # JSON: send_message, assign_agent, add_tag, create_ticket, etc.
    
    # İstatistikler
    execution_count = db.Column(db.Integer, default=0)
    last_executed_at = db.Column(db.DateTime)
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    workspace = db.relationship('Workspace', backref=db.backref('automation_rules', lazy=True))
    executions = db.relationship('AutomationExecution', backref='rule', lazy=True, cascade='all, delete-orphan')


class AutomationExecution(db.Model):
    """
    Otomasyon çalıştırma geçmişi
    Her kural çalıştığında log tutulur
    """
    __tablename__ = 'automation_executions'
    
    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey('automation_rules.id'), nullable=False, index=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), index=True)
    
    # Çalıştırma bilgileri
    status = db.Column(db.String(20), nullable=False)  # success, failed, skipped
    error_message = db.Column(db.Text)
    execution_data = db.Column(db.Text)  # JSON: hangi aksiyonlar yapıldı
    
    executed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)


class ScheduledMessage(db.Model):
    """
    Zamanlanmış mesajlar
    Belirli bir tarih/saatte veya tekrarlayan şekilde mesaj gönderimi
    """
    __tablename__ = 'scheduled_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    
    # Hedef
    target_type = db.Column(db.String(20), nullable=False)  # conversation, customer, segment, broadcast
    target_id = db.Column(db.Integer)  # conversation_id veya customer_id
    target_segment = db.Column(db.String(100))  # segment için: tag, label, etc.
    
    # Mesaj içeriği
    message_body = db.Column(db.Text, nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('message_templates.id'))
    
    # Zamanlama
    schedule_type = db.Column(db.String(20), nullable=False)  # once, recurring
    scheduled_at = db.Column(db.DateTime, nullable=False, index=True)
    
    # Recurring için
    recurrence_pattern = db.Column(db.String(50))  # daily, weekly, monthly
    recurrence_config = db.Column(db.Text)  # JSON: days, time, etc.
    
    # Durum
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, sent, failed, cancelled
    sent_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    workspace = db.relationship('Workspace', backref=db.backref('scheduled_messages', lazy=True))
    template = db.relationship('MessageTemplate', backref=db.backref('scheduled_messages', lazy=True))


class AutoReply(db.Model):
    """
    Otomatik yanıtlar (Keyword-based)
    Belirli anahtar kelimelere otomatik yanıt verir
    """
    __tablename__ = 'auto_replies'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    
    # Kural bilgileri
    name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Trigger
    keywords = db.Column(db.Text, nullable=False)  # Comma-separated keywords
    match_type = db.Column(db.String(20), default='contains')  # contains, exact, starts_with, ends_with
    case_sensitive = db.Column(db.Boolean, default=False)
    
    # Yanıt
    reply_message = db.Column(db.Text, nullable=False)
    reply_delay = db.Column(db.Integer, default=0)  # Saniye cinsinden gecikme (daha doğal görünmesi için)
    
    # Koşullar
    conditions = db.Column(db.Text)  # JSON: time_range, customer_tag, etc.
    
    # İstatistikler
    trigger_count = db.Column(db.Integer, default=0)
    last_triggered_at = db.Column(db.DateTime)
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    workspace = db.relationship('Workspace', backref=db.backref('auto_replies', lazy=True))


class AssignmentRule(db.Model):
    """
    Otomatik atama kuralları
    Yeni konuşmaları otomatik olarak temsilcilere atar
    """
    __tablename__ = 'assignment_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    
    # Kural bilgileri
    name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    priority = db.Column(db.Integer, default=0)  # Yüksek priority önce çalışır
    
    # Koşullar
    conditions = db.Column(db.Text)  # JSON: customer_tag, conversation_tag, keyword, time_range, etc.
    
    # Atama stratejisi
    assignment_type = db.Column(db.String(20), nullable=False)  # round_robin, load_based, specific_agent, team
    assignment_config = db.Column(db.Text)  # JSON: agent_ids, team_id, etc.
    
    # İstatistikler
    assignment_count = db.Column(db.Integer, default=0)
    last_assigned_at = db.Column(db.DateTime)
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    workspace = db.relationship('Workspace', backref=db.backref('assignment_rules', lazy=True))


class WorkflowTemplate(db.Model):
    """
    Workflow şablonları
    Hazır workflow'lar (örnek: Yeni müşteri onboarding, Sipariş takibi, etc.)
    """
    __tablename__ = 'workflow_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Şablon bilgileri
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))  # onboarding, sales, support, marketing
    icon = db.Column(db.String(50))
    
    # Workflow yapısı
    workflow_config = db.Column(db.Text, nullable=False)  # JSON: nodes, edges, actions
    
    # Meta
    is_system = db.Column(db.Boolean, default=False)  # Sistem şablonu mu?
    usage_count = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
