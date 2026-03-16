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
    probability = db.Column(db.Float, default=0.0)  # 0.0 to 1.0 for forecasting
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
    
    # Relationships
    stage = db.relationship('DealStage', foreign_keys=[stage_id], backref='deals')
    
    def __repr__(self):
        return f'<Deal {self.name} (${self.value})>'
    
    def get_weighted_value(self):
        """Calculate weighted value for forecasting: value * stage probability"""
        if self.status == 'open' and self.stage:
            return float(self.value) * self.stage.probability
        return 0.0


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
    
    # Relationships
    contacts = db.relationship('Contact', backref='company', lazy=True, 
                              foreign_keys='Contact.company_id')
    deals = db.relationship('Deal', backref='company', lazy=True)
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
    role = db.Column(db.String(100))  # Decision Maker, Influencer, Champion, Blocker, End User
    job_title = db.Column(db.String(100))
    lead_score = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Link to existing Customer for WhatsApp conversations
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    
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
    tasks = db.relationship('Task', backref='milestone', lazy=True)
    
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
    
    def __repr__(self):
        return f'<Activity {self.activity_type} at {self.created_at}>'


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
