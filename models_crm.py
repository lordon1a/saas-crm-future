"""
Enterprise CRM Models - Pipeline & Deal Management
This module contains database models for CRM features including:
- Pipeline management
- Deal tracking
- Company and contact management
- Tasks and projects
- Activity timeline
- Documents
"""
from models import db
from datetime import datetime


# ============================================================================
# PIPELINE & DEAL MANAGEMENT
# ============================================================================

class Pipeline(db.Model):
    """
    Represents a sales pipeline with multiple stages.
    Each workspace can have multiple pipelines (e.g., Sales, Partnerships).
    """
    __tablename__ = 'pipelines'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    stages = db.relationship('DealStage', backref='pipeline', lazy=True, 
                           order_by='DealStage.order', cascade="all, delete-orphan")
    deals = db.relationship('Deal', backref='pipeline', lazy=True)
    
    def __repr__(self):
        return f'<Pipeline {self.name}>'


class DealStage(db.Model):
    """
    Represents a stage in a sales pipeline.
    Stages have an order and probability for forecasting.
    """
    __tablename__ = 'deal_stages'
    
    id = db.Column(db.Integer, primary_key=True)
    pipeline_id = db.Column(db.Integer, db.ForeignKey('pipelines.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    order = db.Column(db.Integer, nullable=False)  # 1, 2, 3... for stage ordering
    probability = db.Column(db.Integer, default=100)  # 0-100 for forecasting (changed from Float)
    rotting_days = db.Column(db.Integer, nullable=True)  # Days until deal is considered stale
    is_active = db.Column(db.Boolean, default=True, nullable=False)  # Soft delete flag
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        db.UniqueConstraint('pipeline_id', 'order', name='uix_pipeline_stage_order'),
    )
    
    def __repr__(self):
        return f'<DealStage {self.name} (order={self.order})>'


class Deal(db.Model):
    """
    Represents a sales opportunity/deal.
    Tracks value, stage, expected close date, and win/loss reasons.
    """
    __tablename__ = 'deals'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    pipeline_id = db.Column(db.Integer, db.ForeignKey('pipelines.id'), nullable=False, index=True)
    stage_id = db.Column(db.Integer, db.ForeignKey('deal_stages.id'), nullable=False, index=True)
    value = db.Column(db.Numeric(12, 2), default=0)
    expected_close_date = db.Column(db.Date)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default='open', nullable=False, index=True)  # open, won, lost
    win_loss_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = db.Column(db.DateTime)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    stage_entered_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)  # Track when deal entered current stage
    version = db.Column(db.Integer, default=0, nullable=False)  # Optimistic locking
    
    # Relationships
    stage = db.relationship('DealStage', foreign_keys=[stage_id], backref='deals')
    tasks = db.relationship('Task', backref='deal', lazy=True, cascade='all, delete-orphan', foreign_keys='Task.deal_id')
    activities = db.relationship('Activity', backref='deal', lazy=True, cascade='all, delete-orphan', foreign_keys='Activity.deal_id')
    
    def __repr__(self):
        return f'<Deal {self.name} (${self.value})>'
    
    def get_weighted_value(self):
        """Calculate weighted value for forecasting: value * stage probability"""
        if self.status == 'open' and self.stage:
            return float(self.value) * (self.stage.probability / 100.0)
        return 0.0
    
    def is_rotting(self):
        """Check if deal has been in current stage too long"""
        if not self.stage or not self.stage.rotting_days or self.status != 'open':
            return False
        
        days_in_stage = (datetime.utcnow() - self.stage_entered_at).days
        return days_in_stage >= self.stage.rotting_days
    
    def days_in_current_stage(self):
        """Get number of days deal has been in current stage"""
        if not self.stage_entered_at:
            return 0
        return (datetime.utcnow() - self.stage_entered_at).days


# ============================================================================
# COMPANY & CONTACT MANAGEMENT
# ============================================================================

class Company(db.Model):
    """
    Represents an organization/company.
    Can have multiple contacts and deals.
    Supports parent-child hierarchy for subsidiaries.
    """
    __tablename__ = 'companies'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    industry = db.Column(db.String(100))
    size = db.Column(db.String(50))  # 1-10, 11-50, 51-200, 201-500, 500+
    parent_company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    website = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    display_order = db.Column(db.Integer, default=0, nullable=False, index=True)
    
    # Relationships
    contacts = db.relationship('Contact', backref='company', lazy=True, 
                              foreign_keys='Contact.company_id')
    deals = db.relationship('Deal', backref='company', lazy=True, cascade='all, delete-orphan')
    subsidiaries = db.relationship('Company', backref=db.backref('parent_company', remote_side=[id]), 
                                  lazy=True)
    
    def __repr__(self):
        return f'<Company {self.name}>'


class Contact(db.Model):
    """
    Represents an individual person associated with a company.
    Links to existing Customer model for WhatsApp conversations.
    """
    __tablename__ = 'contacts'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True, index=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100))
    email = db.Column(db.String(255), index=True)
    phone = db.Column(db.String(50))
    whatsapp_phone = db.Column(db.String(50))
    telegram_chat_id = db.Column(db.String(100), index=True)
    role = db.Column(db.String(100))  # Decision Maker, Influencer, Champion, Blocker, End User
    job_title = db.Column(db.String(100))
    lead_score = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    display_order = db.Column(db.Integer, default=0, nullable=False, index=True)
    is_starred = db.Column(db.Boolean, default=False, nullable=False, index=True)
    
    # Link to existing Customer for WhatsApp conversations
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    
    # Relationships
    activities = db.relationship('Activity', backref='contact', lazy=True, cascade='all, delete-orphan', foreign_keys='Activity.contact_id')
    
    def __repr__(self):
        return f'<Contact {self.first_name} {self.last_name}>'
    
    @property
    def full_name(self):
        """Return full name"""
        if self.last_name:
            return f'{self.first_name} {self.last_name}'
        return self.first_name


# ============================================================================
# CUSTOMER PORTAL
# ============================================================================

class CustomerUser(db.Model):
    """
    Customer-facing auth account for portal login.
    Separate from internal agent/admin users.
    """
    __tablename__ = 'customer_users'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=True, index=True)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime)

    company = db.relationship('Company', backref=db.backref('customer_users', lazy=True))
    contact = db.relationship('Contact', backref=db.backref('customer_users', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'company_id', 'email', name='uix_customer_user_email'),
    )

    def __repr__(self):
        return f'<CustomerUser {self.email} company={self.company_id}>'


class PortalBranding(db.Model):
    """
    Workspace-level white-label branding configuration for customer portal.
    """
    __tablename__ = 'portal_brandings'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, unique=True, index=True)
    logo_url = db.Column(db.String(500))
    primary_color = db.Column(db.String(7), default='#7c3aed')
    secondary_color = db.Column(db.String(7), default='#8b5cf6')
    custom_domain = db.Column(db.String(255), index=True)
    custom_css = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<PortalBranding workspace={self.workspace_id}>'


class WorkspacePreference(db.Model):
    """
    Workspace-level UI preferences used by settings-driven feature toggles.
    """
    __tablename__ = 'workspace_preferences'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, unique=True, index=True)
    show_dashboard_insights = db.Column(db.Boolean, default=False, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<WorkspacePreference workspace={self.workspace_id} dashboard={self.show_dashboard_insights}>'


class CustomField(db.Model):
    """
    User-defined custom fields for contacts, companies, or deals.
    Supports multiple field types.
    """
    __tablename__ = 'custom_fields'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    entity_type = db.Column(db.String(50), nullable=False, index=True)  # contact, company, deal
    field_name = db.Column(db.String(100), nullable=False)
    field_type = db.Column(db.String(50), nullable=False)  # text, number, date, dropdown, checkbox, multi_select
    options = db.Column(db.Text)  # JSON array for dropdown/multi-select
    is_required = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    values = db.relationship('CustomFieldValue', backref='custom_field', lazy=True, 
                           cascade="all, delete-orphan")
    
    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'entity_type', 'field_name', 
                          name='uix_workspace_entity_field'),
    )
    
    def __repr__(self):
        return f'<CustomField {self.field_name} ({self.entity_type})>'


class CustomFieldValue(db.Model):
    """
    Stores values for custom fields.
    entity_id refers to the ID of the contact/company/deal.
    """
    __tablename__ = 'custom_field_values'
    
    id = db.Column(db.Integer, primary_key=True)
    custom_field_id = db.Column(db.Integer, db.ForeignKey('custom_fields.id'), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=False, index=True)  # ID of contact/company/deal
    value = db.Column(db.Text)  # Stored as string, parsed based on field_type
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('custom_field_id', 'entity_id', name='uix_field_entity'),
    )
    
    def __repr__(self):
        return f'<CustomFieldValue field_id={self.custom_field_id} entity_id={self.entity_id}>'



# ============================================================================
# TASK & PROJECT MANAGEMENT
# ============================================================================

class Task(db.Model):
    """
    Represents a work item assigned to agents or visible to customers.
    Supports dependencies and milestones.
    """
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    assignee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True, index=True)
    deal_id = db.Column(db.Integer, db.ForeignKey('deals.id'), nullable=True, index=True)
    milestone_id = db.Column(db.Integer, db.ForeignKey('milestones.id'), nullable=True, index=True)
    status = db.Column(db.String(50), default='not_started', nullable=False, index=True)
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, urgent
    due_date = db.Column(db.DateTime)
    is_customer_facing = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    # Relationships
    comments = db.relationship('TaskComment', backref='task', lazy=True, cascade="all, delete-orphan")
    attachments = db.relationship('TaskAttachment', backref='task', lazy=True, cascade="all, delete-orphan")
    dependencies = db.relationship('TaskDependency', 
                                  foreign_keys='TaskDependency.task_id',
                                  backref='task', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Task {self.title}>'


class TaskDependency(db.Model):
    """
    Represents a dependency between tasks.
    task_id depends on depends_on_task_id.
    """
    __tablename__ = 'task_dependencies'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False, index=True)
    depends_on_task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        db.UniqueConstraint('task_id', 'depends_on_task_id', name='uix_task_dependency'),
    )
    
    def __repr__(self):
        return f'<TaskDependency task={self.task_id} depends_on={self.depends_on_task_id}>'


class Milestone(db.Model):
    """
    Represents a project milestone that groups related tasks.
    """
    __tablename__ = 'milestones'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True, index=True)
    due_date = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    tasks = db.relationship('Task', backref='milestone', lazy=True, cascade='all, delete-orphan', foreign_keys='Task.milestone_id')
    
    def __repr__(self):
        return f'<Milestone {self.name}>'


class TaskComment(db.Model):
    """
    Comments on tasks for collaboration.
    """
    __tablename__ = 'task_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<TaskComment task_id={self.task_id}>'


class TaskAttachment(db.Model):
    """
    File attachments for tasks.
    """
    __tablename__ = 'task_attachments'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False, index=True)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<TaskAttachment {self.file_name}>'


# ============================================================================
# ACTIVITY TIMELINE
# ============================================================================

class Activity(db.Model):
    """
    Unified activity log for all interactions.
    Tracks emails, calls, meetings, notes, and system events.
    """
    __tablename__ = 'activities'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    activity_type = db.Column(db.String(50), nullable=False, index=True)  # email, call, meeting, note, system, whatsapp, task
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=True, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True, index=True)
    deal_id = db.Column(db.Integer, db.ForeignKey('deals.id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    subject = db.Column(db.String(500))
    body = db.Column(db.Text)
    extra_data = db.Column(db.Text)  # JSON: type-specific data
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<Activity {self.activity_type} at {self.created_at}>'


# ============================================================================
# COLLABORATION TOOLS
# ============================================================================

class Mention(db.Model):
    """
    Mention records parsed from notes/comments.
    """
    __tablename__ = 'mentions'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=True, index=True)
    note_id = db.Column(db.Integer, db.ForeignKey('notes.id'), nullable=True, index=True)
    mentioned_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        db.UniqueConstraint('note_id', 'mentioned_user_id', name='uix_mention_note_user'),
    )

    def __repr__(self):
        return f'<Mention note={self.note_id} user={self.mentioned_user_id}>'


class Notification(db.Model):
    """
    In-app user notifications for collaboration events.
    """
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    notification_type = db.Column(db.String(50), nullable=False, index=True)  # mention, task_assigned, entity_updated
    entity_type = db.Column(db.String(50), index=True)
    entity_id = db.Column(db.Integer, index=True)
    message = db.Column(db.String(500), nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    read_at = db.Column(db.DateTime)

    def __repr__(self):
        return f'<Notification user={self.user_id} type={self.notification_type}>'


class Follow(db.Model):
    """
    User subscriptions for entity update notifications.
    """
    __tablename__ = 'follows'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    entity_type = db.Column(db.String(50), nullable=False, index=True)  # contact, company, deal
    entity_id = db.Column(db.Integer, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'user_id', 'entity_type', 'entity_id', name='uix_follow_unique'),
    )

    def __repr__(self):
        return f'<Follow user={self.user_id} {self.entity_type}:{self.entity_id}>'


# ============================================================================
# DOCUMENT MANAGEMENT
# ============================================================================

class Document(db.Model):
    """
    File metadata for documents shared with customers or internally.
    Supports versioning.
    """
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(50))  # proposal, contract, invoice, general
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True, index=True)
    deal_id = db.Column(db.Integer, db.ForeignKey('deals.id'), nullable=True, index=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_customer_visible = db.Column(db.Boolean, default=False)
    current_version_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    versions = db.relationship('DocumentVersion', backref='document', lazy=True, 
                              order_by='DocumentVersion.version_number.desc()',
                              cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Document {self.name}>'


class DocumentVersion(db.Model):
    """
    Version history for documents.
    """
    __tablename__ = 'document_versions'
    
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False, index=True)
    version_number = db.Column(db.Integer, nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)
    mime_type = db.Column(db.String(100))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        db.UniqueConstraint('document_id', 'version_number', name='uix_document_version'),
    )
    
    def __repr__(self):
        return f'<DocumentVersion doc_id={self.document_id} v{self.version_number}>'


class DocumentTemplate(db.Model):
    """
    Reusable document templates for proposals, contracts, etc.
    """
    __tablename__ = 'document_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50))
    file_path = db.Column(db.String(500), nullable=False)
    variables = db.Column(db.Text)  # JSON: {company_name}, {deal_value}, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<DocumentTemplate {self.name}>'


# ============================================================================
# ADVANCED REPORTING & ANALYTICS
# ============================================================================

class Report(db.Model):
    """
    Saved analytics report definition.
    Supports both system report types and custom builder configurations.
    """
    __tablename__ = 'reports'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    report_type = db.Column(db.String(50), nullable=False, index=True)  # pipeline, forecast, win_loss, cycle, stage_conversion, custom
    config_json = db.Column(db.Text)  # JSON config for filters and custom builder
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    schedules = db.relationship('ReportSchedule', backref='report', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Report {self.name} type={self.report_type}>'


class ReportSchedule(db.Model):
    """
    Report delivery schedule metadata.
    """
    __tablename__ = 'report_schedules'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    report_id = db.Column(db.Integer, db.ForeignKey('reports.id'), nullable=False, index=True)
    frequency = db.Column(db.String(20), nullable=False)  # daily, weekly, monthly
    delivery_channel = db.Column(db.String(20), nullable=False, default='email')  # email
    delivery_target = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_run_at = db.Column(db.DateTime)
    next_run_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<ReportSchedule report={self.report_id} freq={self.frequency}>'


# ============================================================================
# SECURITY & COMPLIANCE (SOC 2)
# ============================================================================

class AuditLog(db.Model):
    """
    Immutable-style security audit events.
    """
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    action = db.Column(db.String(120), nullable=False, index=True)
    entity_type = db.Column(db.String(80), nullable=False, index=True)
    entity_id = db.Column(db.String(80), index=True)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    before_data = db.Column(db.Text)
    after_data = db.Column(db.Text)
    metadata_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f'<AuditLog action={self.action} entity={self.entity_type}:{self.entity_id}>'


class Role(db.Model):
    """
    Role catalog for RBAC.
    """
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False, index=True)
    description = db.Column(db.String(255))
    is_system = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'name', name='uix_role_workspace_name'),
    )

    def __repr__(self):
        return f'<Role {self.name} workspace={self.workspace_id}>'


class Permission(db.Model):
    """
    Permission catalog shared across workspaces.
    """
    __tablename__ = 'permissions'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Permission {self.key}>'


class RolePermission(db.Model):
    """
    Many-to-many mapping between roles and permissions.
    """
    __tablename__ = 'role_permissions'

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False, index=True)
    permission_id = db.Column(db.Integer, db.ForeignKey('permissions.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    role = db.relationship('Role', backref=db.backref('role_permissions', lazy=True, cascade='all, delete-orphan'))
    permission = db.relationship('Permission', backref=db.backref('role_permissions', lazy=True, cascade='all, delete-orphan'))

    __table_args__ = (
        db.UniqueConstraint('role_id', 'permission_id', name='uix_role_permission'),
    )

    def __repr__(self):
        return f'<RolePermission role={self.role_id} permission={self.permission_id}>'


class UserRole(db.Model):
    """
    User to role assignment table.
    """
    __tablename__ = 'user_roles'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    role = db.relationship('Role', backref=db.backref('user_roles', lazy=True, cascade='all, delete-orphan'))

    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'user_id', 'role_id', name='uix_workspace_user_role'),
    )

    def __repr__(self):
        return f'<UserRole user={self.user_id} role={self.role_id}>'


class TwoFactorAuth(db.Model):
    """
    User-level 2FA configuration.
    """
    __tablename__ = 'two_factor_auth'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)
    secret_key = db.Column(db.String(64), nullable=False)
    backup_codes_json = db.Column(db.Text)
    is_enabled = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<TwoFactorAuth user={self.user_id} enabled={self.is_enabled}>'


class IPWhitelist(db.Model):
    """
    Workspace-level login IP whitelist.
    """
    __tablename__ = 'ip_whitelists'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    ip_address = db.Column(db.String(64), nullable=False, index=True)
    label = db.Column(db.String(120))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'ip_address', name='uix_workspace_ip_whitelist'),
    )

    def __repr__(self):
        return f'<IPWhitelist workspace={self.workspace_id} ip={self.ip_address}>'


class SessionActivity(db.Model):
    """
    Session metadata for activity tracking and timeout management.
    """
    __tablename__ = 'session_activities'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    session_token = db.Column(db.String(128), nullable=False, unique=True, index=True)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    last_seen_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<SessionActivity user={self.user_id} active={self.is_active}>'


class GDPRRequest(db.Model):
    """
    Tracks GDPR data export and delete requests.
    """
    __tablename__ = 'gdpr_requests'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    requested_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    request_type = db.Column(db.String(20), nullable=False, index=True)  # export, delete
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)  # pending, completed, failed
    target_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    result_json = db.Column(db.Text)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime)

    def __repr__(self):
        return f'<GDPRRequest type={self.request_type} status={self.status}>'


# ============================================================================
# WEBHOOK SUBSCRIPTIONS & DELIVERIES
# ============================================================================

class WebhookSubscription(db.Model):
    """
    Outgoing webhook subscription configuration for workspace events.
    """
    __tablename__ = 'webhook_subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    target_url = db.Column(db.String(1000), nullable=False)
    event_types = db.Column(db.String(500), nullable=False)  # comma separated values
    secret = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    deliveries = db.relationship(
        'WebhookDelivery',
        backref='subscription',
        lazy=True,
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<WebhookSubscription {self.name} workspace={self.workspace_id}>'


class WebhookDelivery(db.Model):
    """
    Delivery attempt history for outgoing webhooks.
    """
    __tablename__ = 'webhook_deliveries'

    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('webhook_subscriptions.id'), nullable=False, index=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    event_type = db.Column(db.String(100), nullable=False, index=True)
    status = db.Column(db.String(30), nullable=False, default='pending', index=True)  # pending, success, failed
    payload = db.Column(db.Text, nullable=False)
    signature = db.Column(db.String(255))
    attempt_count = db.Column(db.Integer, default=0, nullable=False)
    max_attempts = db.Column(db.Integer, default=3, nullable=False)
    response_status_code = db.Column(db.Integer)
    response_body = db.Column(db.Text)
    next_retry_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<WebhookDelivery sub={self.subscription_id} event={self.event_type} status={self.status}>'


# ============================================================================
# PUBLIC API AUTHENTICATION
# ============================================================================

class APIKey(db.Model):
    """
    Service-to-service API key credentials for public REST API access.
    Stores only hashed key values; plaintext key is shown once at creation.
    """
    __tablename__ = 'api_keys'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    key_prefix = db.Column(db.String(24), nullable=False, index=True)
    key_hash = db.Column(db.String(128), nullable=False, unique=True, index=True)
    scopes = db.Column(db.String(500), default='read')  # comma separated scopes
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_used_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<APIKey {self.name} workspace={self.workspace_id}>'


class OAuthClient(db.Model):
    """
    OAuth2 client application configuration for authorization code flow.
    """
    __tablename__ = 'oauth_clients'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    client_id = db.Column(db.String(80), nullable=False, unique=True, index=True)
    client_secret_hash = db.Column(db.String(128), nullable=False)
    redirect_uris = db.Column(db.Text, nullable=False)  # JSON array string
    scopes = db.Column(db.String(500), default='read')  # comma separated scopes
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<OAuthClient {self.name} workspace={self.workspace_id}>'


class OAuthAuthorizationCode(db.Model):
    """
    Short-lived authorization code used in OAuth 2.0 authorization code flow.
    """
    __tablename__ = 'oauth_authorization_codes'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey('oauth_clients.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    code_hash = db.Column(db.String(128), nullable=False, unique=True, index=True)
    redirect_uri = db.Column(db.String(500), nullable=False)
    scopes = db.Column(db.String(500), default='read')
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    client = db.relationship('OAuthClient', backref=db.backref('auth_codes', lazy=True))

    def __repr__(self):
        return f'<OAuthAuthorizationCode client={self.client_id} workspace={self.workspace_id}>'


class OAuthAccessToken(db.Model):
    """
    Bearer access token issued by OAuth 2.0 token endpoint.
    """
    __tablename__ = 'oauth_access_tokens'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey('oauth_clients.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    token_hash = db.Column(db.String(128), nullable=False, unique=True, index=True)
    scopes = db.Column(db.String(500), default='read')
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    client = db.relationship('OAuthClient', backref=db.backref('access_tokens', lazy=True))

    def __repr__(self):
        return f'<OAuthAccessToken client={self.client_id} workspace={self.workspace_id}>'


# ============================================================================
# GOOGLE WORKSPACE INTEGRATION
# ============================================================================

class GoogleIntegration(db.Model):
    """
    Google Workspace OAuth credentials per workspace and user.
    Token fields are stored encrypted at rest by service layer.
    """
    __tablename__ = 'google_integrations'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    google_email = db.Column(db.String(255), index=True)
    access_token = db.Column(db.Text, nullable=False)  # encrypted token payload
    refresh_token = db.Column(db.Text)  # encrypted token payload
    token_expires_at = db.Column(db.DateTime, index=True)
    scopes = db.Column(db.Text)  # JSON array string
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'user_id', name='uix_google_integration_workspace_user'),
    )

    def __repr__(self):
        return f'<GoogleIntegration workspace={self.workspace_id} user={self.user_id} active={self.is_active}>'


# ============================================================================
# QUICKBOOKS INTEGRATION
# ============================================================================

class QuickBooksIntegration(db.Model):
    """
    QuickBooks OAuth credentials per workspace and user.
    Token fields are stored encrypted at rest by service layer.
    """
    __tablename__ = 'quickbooks_integrations'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    realm_id = db.Column(db.String(100), index=True)
    company_name = db.Column(db.String(255))
    access_token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text)
    token_expires_at = db.Column(db.DateTime, index=True)
    refresh_expires_at = db.Column(db.DateTime, index=True)
    scopes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    last_sync_at = db.Column(db.DateTime)
    last_error = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'user_id', name='uix_quickbooks_integration_workspace_user'),
    )

    def __repr__(self):
        return f'<QuickBooksIntegration workspace={self.workspace_id} user={self.user_id} active={self.is_active}>'


class QuickBooksInvoice(db.Model):
    """
    QuickBooks invoice sync ledger linked to CRM deals.
    """
    __tablename__ = 'quickbooks_invoices'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    integration_id = db.Column(db.Integer, db.ForeignKey('quickbooks_integrations.id'), nullable=True, index=True)
    deal_id = db.Column(db.Integer, db.ForeignKey('deals.id'), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    quickbooks_invoice_id = db.Column(db.String(100), index=True)
    doc_number = db.Column(db.String(100), index=True)
    sync_status = db.Column(db.String(20), default='pending', nullable=False, index=True)  # pending, synced, failed
    payment_status = db.Column(db.String(20), default='unpaid', nullable=False, index=True)  # unpaid, partial, paid
    amount = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    currency = db.Column(db.String(10), default='USD')
    due_date = db.Column(db.Date)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    paid_at = db.Column(db.DateTime)
    last_synced_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    retry_count = db.Column(db.Integer, default=0, nullable=False)
    next_retry_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    integration = db.relationship('QuickBooksIntegration', backref=db.backref('invoices', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'deal_id', name='uix_quickbooks_invoice_workspace_deal'),
    )

    def __repr__(self):
        return f'<QuickBooksInvoice deal={self.deal_id} status={self.sync_status} payment={self.payment_status}>'


class QuickBooksSyncError(db.Model):
    """
    Error log for QuickBooks sync failures with retry metadata.
    """
    __tablename__ = 'quickbooks_sync_errors'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    integration_id = db.Column(db.Integer, db.ForeignKey('quickbooks_integrations.id'), nullable=True, index=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('quickbooks_invoices.id'), nullable=True, index=True)
    correlation_id = db.Column(db.String(64), nullable=False, index=True)
    operation = db.Column(db.String(50), nullable=False, index=True)
    error_message = db.Column(db.Text, nullable=False)
    http_status = db.Column(db.Integer)
    retry_count = db.Column(db.Integer, default=0, nullable=False)
    will_retry = db.Column(db.Boolean, default=False, nullable=False)
    next_retry_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    resolved_at = db.Column(db.DateTime)

    integration = db.relationship('QuickBooksIntegration', backref=db.backref('sync_errors', lazy=True))
    invoice = db.relationship('QuickBooksInvoice', backref=db.backref('sync_errors', lazy=True))

    def __repr__(self):
        return f'<QuickBooksSyncError op={self.operation} correlation={self.correlation_id}>'


# ============================================================================
# GOOGLE WORKSPACE INTEGRATION - EMAIL & CALENDAR SYNC
# ============================================================================

class EmailSync(db.Model):
    """
    Tracks synced emails from Gmail API.
    Links emails to contacts and creates activity records.
    """
    __tablename__ = 'email_syncs'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    google_integration_id = db.Column(db.Integer, db.ForeignKey('google_integrations.id'), nullable=False, index=True)
    gmail_message_id = db.Column(db.String(255), nullable=False, unique=True, index=True)
    thread_id = db.Column(db.String(255), index=True)
    subject = db.Column(db.String(500))
    from_email = db.Column(db.String(255), index=True)
    to_emails = db.Column(db.Text)  # JSON array
    cc_emails = db.Column(db.Text)  # JSON array
    body_snippet = db.Column(db.Text)
    body_html = db.Column(db.Text)
    body_text = db.Column(db.Text)
    received_at = db.Column(db.DateTime, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=True, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True, index=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=True, index=True)
    is_sent = db.Column(db.Boolean, default=False)  # True if sent by user, False if received
    has_attachments = db.Column(db.Boolean, default=False)
    labels = db.Column(db.Text)  # JSON array of Gmail labels
    synced_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<EmailSync {self.gmail_message_id} from={self.from_email}>'


class EmailTracking(db.Model):
    """
    Tracks email opens and link clicks for outgoing emails.
    Used for email engagement analytics.
    """
    __tablename__ = 'email_tracking'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    tracking_id = db.Column(db.String(64), nullable=False, unique=True, index=True)
    email_sync_id = db.Column(db.Integer, db.ForeignKey('email_syncs.id'), nullable=True, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=True, index=True)
    recipient_email = db.Column(db.String(255), nullable=False, index=True)
    subject = db.Column(db.String(500))
    sent_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    opened_at = db.Column(db.DateTime, index=True)
    open_count = db.Column(db.Integer, default=0)
    last_opened_at = db.Column(db.DateTime)
    click_count = db.Column(db.Integer, default=0)
    last_clicked_at = db.Column(db.DateTime)
    user_agent = db.Column(db.String(500))
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<EmailTracking {self.tracking_id} to={self.recipient_email}>'


class EmailTrackingClick(db.Model):
    """
    Records individual link clicks within tracked emails.
    """
    __tablename__ = 'email_tracking_clicks'
    
    id = db.Column(db.Integer, primary_key=True)
    email_tracking_id = db.Column(db.Integer, db.ForeignKey('email_tracking.id'), nullable=False, index=True)
    original_url = db.Column(db.Text, nullable=False)
    clicked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    user_agent = db.Column(db.String(500))
    ip_address = db.Column(db.String(45))
    
    def __repr__(self):
        return f'<EmailTrackingClick tracking={self.email_tracking_id} at={self.clicked_at}>'


class EmailTemplate(db.Model):
    """
    Workspace-scoped email templates with merge variables.
    """
    __tablename__ = 'email_templates'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    subject_template = db.Column(db.String(500), nullable=False)
    body_template = db.Column(db.Text, nullable=False)
    variables_json = db.Column(db.Text)  # JSON array of variable names
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'name', name='uix_email_template_workspace_name'),
    )

    def __repr__(self):
        return f'<EmailTemplate {self.name} workspace={self.workspace_id}>'


class EmailSequence(db.Model):
    """
    Ordered set of delayed email steps.
    """
    __tablename__ = 'email_sequences'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    steps = db.relationship('EmailSequenceStep', backref='sequence', lazy=True, cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'name', name='uix_email_sequence_workspace_name'),
    )

    def __repr__(self):
        return f'<EmailSequence {self.name} workspace={self.workspace_id}>'


class EmailSequenceStep(db.Model):
    """
    Individual step in an email sequence.
    """
    __tablename__ = 'email_sequence_steps'

    id = db.Column(db.Integer, primary_key=True)
    sequence_id = db.Column(db.Integer, db.ForeignKey('email_sequences.id'), nullable=False, index=True)
    step_order = db.Column(db.Integer, nullable=False)
    delay_hours = db.Column(db.Integer, default=0, nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('email_templates.id'), nullable=True, index=True)
    subject_override = db.Column(db.String(500))
    body_override = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('sequence_id', 'step_order', name='uix_email_sequence_step_order'),
    )

    def __repr__(self):
        return f'<EmailSequenceStep sequence={self.sequence_id} order={self.step_order}>'


class EmailSendQueue(db.Model):
    """
    Durable queue contract for outbound email delivery workers.
    """
    __tablename__ = 'email_send_queue'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    outbound_email_id = db.Column(db.Integer, db.ForeignKey('outbound_emails.id'), nullable=False, index=True)
    provider = db.Column(db.String(50), nullable=False, default='smtp')
    status = db.Column(db.String(20), nullable=False, default='queued', index=True)  # queued, processing, sent, failed
    payload_json = db.Column(db.Text, nullable=False)
    attempt_count = db.Column(db.Integer, default=0, nullable=False)
    next_attempt_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    last_error = db.Column(db.Text)
    processed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<EmailSendQueue outbound={self.outbound_email_id} status={self.status}>'


class OutboundEmail(db.Model):
    """
    Outbound email delivery ledger with provider and tracking metadata.
    """
    __tablename__ = 'outbound_emails'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=True, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True, index=True)
    deal_id = db.Column(db.Integer, db.ForeignKey('deals.id'), nullable=True, index=True)
    to_email = db.Column(db.String(255), nullable=False, index=True)
    subject = db.Column(db.String(500), nullable=False)
    body_text = db.Column(db.Text)
    body_html = db.Column(db.Text)
    provider = db.Column(db.String(50), nullable=False, default='smtp')
    provider_message_id = db.Column(db.String(255), index=True)
    status = db.Column(db.String(20), nullable=False, default='queued', index=True)  # queued, sent, failed
    tracking_id = db.Column(db.String(64), index=True)
    sent_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    queue_items = db.relationship('EmailSendQueue', backref='outbound_email', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<OutboundEmail to={self.to_email} status={self.status}>'


class CalendarSync(db.Model):
    """
    Tracks synced calendar events from Google Calendar API.
    Links events to contacts and creates activity records.
    """
    __tablename__ = 'calendar_syncs'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    google_integration_id = db.Column(db.Integer, db.ForeignKey('google_integrations.id'), nullable=False, index=True)
    google_event_id = db.Column(db.String(255), nullable=False, index=True)
    calendar_id = db.Column(db.String(255), nullable=False, index=True)
    summary = db.Column(db.String(500))
    description = db.Column(db.Text)
    location = db.Column(db.String(500))
    start_time = db.Column(db.DateTime, nullable=False, index=True)
    end_time = db.Column(db.DateTime, nullable=False)
    attendee_emails = db.Column(db.Text)  # JSON array
    organizer_email = db.Column(db.String(255), index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=True, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True, index=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=True, index=True)
    event_status = db.Column(db.String(50))  # confirmed, tentative, cancelled
    is_recurring = db.Column(db.Boolean, default=False)
    recurring_event_id = db.Column(db.String(255), index=True)
    synced_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        db.UniqueConstraint('google_event_id', 'calendar_id', name='uix_google_event_calendar'),
    )
    
    def __repr__(self):
        return f'<CalendarSync {self.google_event_id} summary={self.summary}>'


# ============================================================================
# GOOGLE DRIVE INTEGRATION
# ============================================================================

class DriveAttachment(db.Model):
    """
    Represents a Google Drive file attached to a deal or task.
    Stores Drive file ID and metadata for quick access.
    """
    __tablename__ = 'drive_attachments'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    
    # Google Drive file info
    drive_file_id = db.Column(db.String(200), nullable=False, index=True)
    file_name = db.Column(db.String(500), nullable=False)
    mime_type = db.Column(db.String(100))
    file_size = db.Column(db.BigInteger)  # bytes
    thumbnail_url = db.Column(db.String(1000))
    web_view_link = db.Column(db.String(1000))
    
    # Attachment context (what is this file attached to?)
    entity_type = db.Column(db.String(50), nullable=False, index=True)  # 'deal', 'task', 'contact', 'company'
    entity_id = db.Column(db.Integer, nullable=False, index=True)
    
    # Metadata
    attached_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    attached_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    notes = db.Column(db.Text)
    
    def __repr__(self):
        return f'<DriveAttachment {self.file_name} -> {self.entity_type}:{self.entity_id}>'
