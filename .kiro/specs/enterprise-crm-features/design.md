# Design Document: Enterprise CRM Features

## Overview

This design extends the existing WhatsApp CRM platform with enterprise-grade features to compete with Salesforce, HubSpot, and Zendesk. The system maintains the existing multi-tenant Flask/SQLAlchemy architecture while adding:

- **Pipeline Management**: Sales stages, deal tracking, forecasting
- **Advanced Contact Management**: Companies, hierarchies, custom fields
- **Task & Project Management**: Dependencies, milestones, customer visibility
- **Customer Portal**: Separate authentication, white-label support
- **Public REST API**: OAuth 2.0, webhooks, comprehensive documentation
- **Integrations**: Google Workspace, QuickBooks
- **Security & Compliance**: Audit logs, RBAC, 2FA, SOC 2 readiness
- **Document Management**: Versioning, templates, e-signatures
- **Advanced Analytics**: Pipeline reports, forecasting, custom reports

The design prioritizes:
- **Scalability**: Support 300 companies, 15 concurrent users
- **Compliance**: SOC 2 audit logs, encryption, access controls
- **Usability**: Non-technical users, intuitive interfaces
- **Integration**: Public API for external portals and tools
- **Low Maintenance**: Leverage existing architecture, minimize complexity

## Architecture

### System Architecture


```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                              │
├──────────────────┬──────────────────┬──────────────────────────┤
│  Agent Web UI    │  Customer Portal │  External Apps (API)     │
│  (Flask/Jinja2)  │  (Flask/Jinja2)  │  (REST API + Webhooks)   │
└──────────────────┴──────────────────┴──────────────────────────┘
                            │
┌───────────────────────────┼───────────────────────────────────┐
│                    Application Layer                           │
├────────────────────────────────────────────────────────────────┤
│  Authentication & Authorization                                │
│  - Agent Auth (existing session-based)                         │
│  - Customer Auth (new JWT-based)                               │
│  - API Auth (API keys + OAuth 2.0)                             │
│  - RBAC (Admin, Manager, Agent, Read-Only)                     │
│  - 2FA (TOTP)                                                  │
├────────────────────────────────────────────────────────────────┤
│  Business Logic Services                                       │
│  - Pipeline Service (deals, stages, forecasting)               │
│  - Contact Service (companies, contacts, custom fields)        │
│  - Task Service (tasks, dependencies, milestones)              │
│  - Document Service (upload, versioning, templates)            │
│  - Activity Service (timeline, events)                         │
│  - Integration Service (Google, QuickBooks)                    │
│  - Webhook Service (event dispatch, retries)                   │
│  - Audit Service (logging, compliance)                         │
│  - Report Service (analytics, forecasting)                     │
├────────────────────────────────────────────────────────────────┤
│  API Layer                                                     │
│  - REST API (Flask blueprints)                                │
│  - OpenAPI/Swagger documentation                               │
│  - Rate limiting (Flask-Limiter)                               │
│  - Webhook endpoints                                           │
└────────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────┼───────────────────────────────────┐
│                      Data Layer                                │
├────────────────────────────────────────────────────────────────┤
│  SQLAlchemy ORM                                                │
│  - Multi-tenant isolation (workspace_id)                       │
│  - Existing: Workspace, User, Customer, Conversation, Message  │
│  - New: Company, Contact, Deal, Pipeline, Task, Document,      │
│         CustomField, AuditLog, APIKey, CustomerUser, etc.      │
└────────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────┼───────────────────────────────────┐
│                    Storage Layer                               │
├────────────────────────────────────────────────────────────────┤
│  SQLite (dev) / PostgreSQL (production)                        │
│  File Storage (local/S3) for documents and media               │
│  Redis (optional) for rate limiting and caching                │
└────────────────────────────────────────────────────────────────┘
```

### Multi-Tenant Isolation

All new tables include `workspace_id` foreign key to maintain tenant isolation. Queries filter by `workspace_id` from session context.

### Authentication Strategy

- **Agent Authentication**: Existing session-based (Flask sessions)
- **Customer Authentication**: New JWT-based tokens for portal access
- **API Authentication**: API keys (service-to-service) + OAuth 2.0 (user-delegated)

## Components and Interfaces

### 1. Pipeline & Deal Management

**Components:**
- `Pipeline` model: Defines stages and probabilities
- `Deal` model: Tracks opportunities through stages
- `DealStage` model: Represents individual stages
- `PipelineService`: Business logic for deal management

**Database Schema:**

```python
class Pipeline(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    stages = db.relationship('DealStage', backref='pipeline', order_by='DealStage.order')

class DealStage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pipeline_id = db.Column(db.Integer, db.ForeignKey('pipelines.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    order = db.Column(db.Integer, nullable=False)
    probability = db.Column(db.Float, default=0.0)  # 0.0 to 1.0 for forecasting

class Deal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    pipeline_id = db.Column(db.Integer, db.ForeignKey('pipelines.id'), nullable=False)
    stage_id = db.Column(db.Integer, db.ForeignKey('deal_stages.id'), nullable=False)
    value = db.Column(db.Numeric(12, 2), default=0)
    expected_close_date = db.Column(db.Date)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='open')  # open, won, lost
    win_loss_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime)
```

**API Endpoints:**
- `POST /api/v1/deals` - Create deal
- `GET /api/v1/deals` - List deals (filterable by stage, owner)
- `GET /api/v1/deals/{id}` - Get deal details
- `PATCH /api/v1/deals/{id}` - Update deal (move stage, change value)
- `DELETE /api/v1/deals/{id}` - Delete deal
- `GET /api/v1/pipelines` - List pipelines
- `GET /api/v1/deals/forecast` - Get sales forecast

**Forecasting Algorithm:**
```
weighted_value = deal.value * stage.probability
total_forecast = sum(weighted_value for all open deals)
```

### 2. Contact & Company Management

**Components:**
- `Company` model: Organization records
- `Contact` model: Individual people (replaces/extends Customer)
- `CustomField` model: User-defined fields
- `CustomFieldValue` model: Stores custom field data
- `ContactService`: Business logic for contact/company management

**Database Schema:**

```python
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    industry = db.Column(db.String(100))
    size = db.Column(db.String(50))  # 1-10, 11-50, 51-200, 201-500, 500+
    parent_company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    website = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    contacts = db.relationship('Contact', backref='company')
    deals = db.relationship('Deal', backref='company')

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    whatsapp_phone = db.Column(db.String(50))
    role = db.Column(db.String(100))  # Decision Maker, Influencer, etc.
    job_title = db.Column(db.String(100))
    lead_score = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Link to existing Customer for WhatsApp conversations
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))

class CustomField(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)  # contact, company, deal
    field_name = db.Column(db.String(100), nullable=False)
    field_type = db.Column(db.String(50), nullable=False)  # text, number, date, dropdown, checkbox
    options = db.Column(db.Text)  # JSON array for dropdown/multi-select
    is_required = db.Column(db.Boolean, default=False)

class CustomFieldValue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    custom_field_id = db.Column(db.Integer, db.ForeignKey('custom_fields.id'), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)  # ID of contact/company/deal
    value = db.Column(db.Text)  # Stored as string, parsed based on field_type
```

**API Endpoints:**
- `POST /api/v1/companies` - Create company
- `GET /api/v1/companies` - List companies
- `GET /api/v1/companies/{id}` - Get company with contacts
- `POST /api/v1/contacts` - Create contact
- `GET /api/v1/contacts` - List contacts
- `POST /api/v1/contacts/import` - CSV import
- `GET /api/v1/contacts/export` - CSV export
- `POST /api/v1/custom-fields` - Define custom field
- `GET /api/v1/custom-fields` - List custom fields

**Duplicate Detection:**
- Check email and phone on contact creation
- Return list of potential duplicates with similarity score
- User decides to merge or create new

### 3. Task & Project Management

**Components:**
- `Task` model: Work items
- `TaskDependency` model: Task relationships
- `Milestone` model: Project milestones
- `TaskService`: Business logic for task management

**Database Schema:**

```python
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    assignee_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    deal_id = db.Column(db.Integer, db.ForeignKey('deals.id'))
    milestone_id = db.Column(db.Integer, db.ForeignKey('milestones.id'))
    status = db.Column(db.String(50), default='not_started')
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, urgent
    due_date = db.Column(db.DateTime)
    is_customer_facing = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    comments = db.relationship('TaskComment', backref='task')
    attachments = db.relationship('TaskAttachment', backref='task')

class TaskDependency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    depends_on_task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)

class Milestone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    due_date = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='active')
    tasks = db.relationship('Task', backref='milestone')
```

**API Endpoints:**
- `POST /api/v1/tasks` - Create task
- `GET /api/v1/tasks` - List tasks (filter by assignee, company, status)
- `PATCH /api/v1/tasks/{id}` - Update task
- `POST /api/v1/tasks/{id}/dependencies` - Add dependency
- `GET /api/v1/milestones` - List milestones

### 4. Customer Portal

**Components:**
- `CustomerUser` model: Portal authentication
- `CustomerPortalService`: Business logic for portal
- Separate Flask blueprint for portal routes

**Database Schema:**

```python
class CustomerUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'))
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PortalBranding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, unique=True)
    logo_url = db.Column(db.String(500))
    primary_color = db.Column(db.String(7))  # Hex color
    custom_domain = db.Column(db.String(255))
```

**Portal Routes:**
- `POST /portal/login` - Customer login (returns JWT)
- `GET /portal/tasks` - List customer-facing tasks
- `GET /portal/documents` - List shared documents
- `GET /portal/messages` - Communication hub
- `POST /portal/messages` - Send message to agent

**JWT Authentication:**
- Token includes: customer_user_id, workspace_id, company_id
- 24-hour expiration
- Refresh token for extended sessions


### 5. Public REST API

**Components:**
- `APIKey` model: Service authentication
- `OAuthClient` model: OAuth 2.0 clients
- `OAuthToken` model: Access/refresh tokens
- `WebhookSubscription` model: Event subscriptions
- `APIService`: Rate limiting, authentication

**Database Schema:**

```python
class APIKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    key = db.Column(db.String(64), unique=True, nullable=False)  # SHA-256 hash
    name = db.Column(db.String(100), nullable=False)
    scopes = db.Column(db.Text)  # JSON array of permissions
    is_active = db.Column(db.Boolean, default=True)
    last_used = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class OAuthClient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    client_id = db.Column(db.String(64), unique=True, nullable=False)
    client_secret_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    redirect_uris = db.Column(db.Text)  # JSON array
    scopes = db.Column(db.Text)  # JSON array

class OAuthToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(64), db.ForeignKey('oauth_clients.client_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    access_token = db.Column(db.String(255), unique=True, nullable=False)
    refresh_token = db.Column(db.String(255), unique=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    scopes = db.Column(db.Text)

class WebhookSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    events = db.Column(db.Text)  # JSON array: ['deal.created', 'task.completed']
    secret = db.Column(db.String(64))  # For signature verification
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class WebhookDelivery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('webhook_subscriptions.id'), nullable=False)
    event_type = db.Column(db.String(100), nullable=False)
    payload = db.Column(db.Text)  # JSON
    status = db.Column(db.String(20), default='pending')  # pending, success, failed
    attempts = db.Column(db.Integer, default=0)
    last_attempt = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

**API Versioning:**
- URL-based: `/api/v1/...`
- Version in Accept header: `Accept: application/vnd.crm.v1+json`

**Rate Limiting:**
- 1000 requests/hour per API key
- Use Flask-Limiter with Redis backend
- Return `429 Too Many Requests` with `Retry-After` header

**Webhook Signature:**
```python
signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
# Send as X-Webhook-Signature header
```

**API Documentation:**
- Use Flask-RESTX or flasgger for Swagger/OpenAPI
- Auto-generate from route decorators
- Host at `/api/docs`

### 6. Google Workspace Integration

**Components:**
- `GoogleIntegration` model: OAuth tokens
- `EmailSync` model: Synced emails
- `CalendarSync` model: Synced events
- `GoogleService`: API client wrapper

**Database Schema:**

```python
class GoogleIntegration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    access_token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text)
    token_expires_at = db.Column(db.DateTime)
    scopes = db.Column(db.Text)  # JSON array
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class EmailSync(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    gmail_message_id = db.Column(db.String(255), unique=True, nullable=False)
    subject = db.Column(db.String(500))
    body = db.Column(db.Text)
    from_email = db.Column(db.String(255))
    to_email = db.Column(db.String(255))
    sent_at = db.Column(db.DateTime)
    is_opened = db.Column(db.Boolean, default=False)
    opened_at = db.Column(db.DateTime)
```

**OAuth Flow:**
1. User clicks "Connect Google"
2. Redirect to Google OAuth consent screen
3. Google redirects back with authorization code
4. Exchange code for access/refresh tokens
5. Store tokens in GoogleIntegration table

**Email Sync:**
- Use Gmail API to fetch emails
- Match emails to contacts by email address
- Create activity timeline entries
- Sync every 5 minutes (background job)

**Calendar Sync:**
- Use Google Calendar API
- Sync events with contact attendees
- Create activity timeline entries for meetings

### 7. Advanced Reporting & Analytics

**Components:**
- `Report` model: Saved reports
- `ReportSchedule` model: Scheduled report delivery
- `ReportService`: Report generation logic

**Database Schema:**

```python
class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    report_type = db.Column(db.String(50), nullable=False)  # pipeline, forecast, win_loss
    filters = db.Column(db.Text)  # JSON: date range, owner, stage
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ReportSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('reports.id'), nullable=False)
    frequency = db.Column(db.String(20), nullable=False)  # daily, weekly, monthly
    recipients = db.Column(db.Text)  # JSON array of emails
    next_run = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
```

**Report Types:**

1. **Pipeline Report:**
   - Deals by stage (count, total value)
   - Average deal size per stage
   - Stage conversion rates

2. **Forecast Report:**
   - Weighted pipeline value
   - Expected revenue by close date
   - Confidence intervals

3. **Win/Loss Analysis:**
   - Win rate by reason
   - Loss rate by reason
   - Average deal size (won vs lost)

4. **Sales Cycle Report:**
   - Average days in each stage
   - Total cycle duration
   - Bottleneck identification

**Custom Report Builder:**
- Drag-and-drop interface
- Select dimensions (stage, owner, date)
- Select metrics (count, sum, average)
- Apply filters
- Save and schedule

### 8. Security & Compliance (SOC 2)

**Components:**
- `AuditLog` model: Activity logging
- `Role` model: RBAC roles
- `Permission` model: Granular permissions
- `TwoFactorAuth` model: 2FA secrets
- `SecurityService`: Audit, encryption, access control

**Database Schema:**

```python
class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)  # login, create_deal, delete_contact
    entity_type = db.Column(db.String(50))  # deal, contact, company
    entity_id = db.Column(db.Integer)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    changes = db.Column(db.Text)  # JSON: before/after values
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    permissions = db.Column(db.Text)  # JSON array of permission names
    is_system = db.Column(db.Boolean, default=False)  # Built-in roles

class TwoFactorAuth(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    secret = db.Column(db.String(32), nullable=False)
    is_enabled = db.Column(db.Boolean, default=False)
    backup_codes = db.Column(db.Text)  # JSON array of hashed codes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class IPWhitelist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    description = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
```

**RBAC Permissions:**
- `deals.view`, `deals.create`, `deals.edit`, `deals.delete`
- `contacts.view`, `contacts.create`, `contacts.edit`, `contacts.delete`
- `tasks.view`, `tasks.create`, `tasks.edit`, `tasks.delete`
- `reports.view`, `reports.create`
- `settings.manage`, `users.manage`, `api.manage`

**Built-in Roles:**
- **Admin**: All permissions
- **Manager**: View all, edit all, no settings
- **Agent**: View assigned, edit assigned
- **Read-Only**: View only

**Audit Logging:**
- Log all CRUD operations
- Log authentication events
- Log permission changes
- Retention: 7 years (SOC 2 requirement)

**Data Encryption:**
- At rest: SQLAlchemy encryption extension or database-level encryption
- In transit: TLS 1.3 (enforce in production)
- Sensitive fields: Encrypt API keys, OAuth tokens, 2FA secrets

**2FA Implementation:**
- Use `pyotp` library for TOTP
- QR code generation for setup
- 6-digit codes, 30-second window
- 10 backup codes (one-time use)

### 9. Document Management

**Components:**
- `Document` model: File metadata
- `DocumentVersion` model: Version history
- `DocumentTemplate` model: Reusable templates
- `DocumentService`: Upload, versioning, storage

**Database Schema:**

```python
class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(50))  # proposal, contract, invoice, general
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    deal_id = db.Column(db.Integer, db.ForeignKey('deals.id'))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    is_customer_visible = db.Column(db.Boolean, default=False)
    current_version_id = db.Column(db.Integer, db.ForeignKey('document_versions.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DocumentVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)
    mime_type = db.Column(db.String(100))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DocumentTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50))
    file_path = db.Column(db.String(500), nullable=False)
    variables = db.Column(db.Text)  # JSON: {company_name}, {deal_value}
```

**File Storage:**
- Local: `uploads/{workspace_id}/documents/{document_id}/{version_number}/filename`
- Production: S3-compatible storage (boto3)
- Max file size: 50MB

**Version Control:**
- Increment version_number on upload
- Keep all versions (no deletion)
- Update current_version_id pointer

**Template Variables:**
- `{company_name}`, `{contact_name}`, `{deal_value}`, `{today_date}`
- Replace on document generation
- Use Jinja2 for complex templates

### 10. Email Integration & Tracking

**Components:**
- `EmailTemplate` model: Reusable email templates
- `EmailSequence` model: Automated follow-ups
- `EmailTracking` model: Opens and clicks
- `EmailService`: Sending, tracking, syncing

**Database Schema:**

```python
class EmailTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(500), nullable=False)
    body = db.Column(db.Text, nullable=False)
    variables = db.Column(db.Text)  # JSON array

class EmailSequence(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    steps = db.Column(db.Text)  # JSON: [{template_id, delay_days}]

class EmailTracking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email_sync_id = db.Column(db.Integer, db.ForeignKey('email_syncs.id'), nullable=False)
    tracking_pixel_id = db.Column(db.String(64), unique=True, nullable=False)
    opened_count = db.Column(db.Integer, default=0)
    first_opened_at = db.Column(db.DateTime)
    last_opened_at = db.Column(db.DateTime)
    clicked_links = db.Column(db.Text)  # JSON array of clicked URLs
```

**Email Tracking:**
- Embed 1x1 tracking pixel: `<img src="/track/open/{tracking_pixel_id}">`
- Rewrite links: `https://crm.example.com/track/click/{tracking_pixel_id}/{link_id}`
- Record opens and clicks in EmailTracking table

**Unified Inbox:**
- Combine WhatsApp messages and emails
- Sort by timestamp
- Filter by channel (WhatsApp, Email, All)

### 11. QuickBooks Integration

**Components:**
- `QuickBooksIntegration` model: OAuth tokens
- `QuickBooksInvoice` model: Synced invoices
- `QuickBooksService`: API client wrapper

**Database Schema:**

```python
class QuickBooksIntegration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, unique=True)
    realm_id = db.Column(db.String(100), nullable=False)
    access_token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text)
    token_expires_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)

class QuickBooksInvoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    deal_id = db.Column(db.Integer, db.ForeignKey('deals.id'), nullable=False)
    qb_invoice_id = db.Column(db.String(100), nullable=False)
    invoice_number = db.Column(db.String(50))
    amount = db.Column(db.Numeric(12, 2))
    status = db.Column(db.String(50))  # draft, sent, paid
    synced_at = db.Column(db.DateTime, default=datetime.utcnow)
```

**Sync Logic:**
- When deal moves to "Closed Won", create invoice in QuickBooks
- Poll QuickBooks API every hour for payment updates
- Update deal status when invoice is paid

### 12. Activity Timeline

**Components:**
- `Activity` model: Unified activity log
- `ActivityService`: Timeline generation

**Database Schema:**

```python
class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)  # email, call, meeting, note, system
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    deal_id = db.Column(db.Integer, db.ForeignKey('deals.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    subject = db.Column(db.String(500))
    body = db.Column(db.Text)
    metadata = db.Column(db.Text)  # JSON: type-specific data
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
```

**Activity Types:**
- `email`: Sent/received emails
- `whatsapp`: WhatsApp messages
- `call`: Phone calls (manual entry)
- `meeting`: Calendar events
- `note`: Manual notes
- `task`: Task created/completed
- `system`: Deal stage change, field update

**Timeline Query:**
```sql
SELECT * FROM activities 
WHERE (contact_id = ? OR company_id = ? OR deal_id = ?)
  AND workspace_id = ?
ORDER BY created_at DESC
```

### 13. Collaboration Tools

**Components:**
- `Mention` model: @mentions in notes
- `Notification` model: User notifications
- `Follow` model: Record subscriptions
- `CollaborationService`: Notifications, mentions

**Database Schema:**

```python
class Mention(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)
    mentioned_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)  # mention, task_assigned, deal_updated
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    message = db.Column(db.String(500))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)  # contact, company, deal
    entity_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

**Mention Detection:**
```python
import re
mention_pattern = r'@(\w+)'
mentions = re.findall(mention_pattern, note_content)
# Look up users by username, create Mention records
```

**Notification Triggers:**
- @mention in note
- Task assigned
- Deal stage changed (if following)
- Contact updated (if following)

## Data Models

### Entity Relationship Diagram


```
┌─────────────┐
│  Workspace  │
└──────┬──────┘
       │
       ├──────────┬──────────┬──────────┬──────────┬──────────┐
       │          │          │          │          │          │
   ┌───▼───┐  ┌──▼──┐   ┌───▼────┐ ┌──▼──────┐ ┌─▼────────┐
   │ User  │  │Deal │   │Company │ │Pipeline │ │CustomField│
   └───┬───┘  └──┬──┘   └───┬────┘ └──┬──────┘ └──────────┘
       │         │          │         │
       │         │      ┌───▼────┐    │
       │         │      │Contact │    │
       │         │      └───┬────┘    │
       │         │          │         │
       │         └──────────┴─────────┘
       │                    │
   ┌───▼───┐           ┌───▼────┐
   │ Task  │           │Activity│
   └───────┘           └────────┘
```

### Key Relationships

- **Workspace** → Users, Companies, Contacts, Deals, Pipelines (1:N)
- **Company** → Contacts, Deals (1:N)
- **Company** → Company (parent-child hierarchy)
- **Contact** → Customer (1:1, links to WhatsApp conversations)
- **Deal** → Company, Pipeline, DealStage (N:1)
- **Task** → User (assignee), Company, Deal, Milestone (N:1)
- **Activity** → Contact, Company, Deal, User (N:1)
- **CustomField** → CustomFieldValue (1:N)

### Migration Strategy

**Phase 1: Extend Existing Models**
- Add `company_id` to Customer table (optional, for backward compatibility)
- Create Contact table with `customer_id` foreign key
- Migrate existing Customer records to Contact records

**Phase 2: Add New Models**
- Create Company, Deal, Pipeline, Task, Document tables
- Create CustomField and CustomFieldValue tables
- Create Activity table (consolidate timeline)

**Phase 3: Add Integration Models**
- Create GoogleIntegration, QuickBooksIntegration tables
- Create EmailSync, EmailTracking tables
- Create WebhookSubscription, APIKey tables

**Phase 4: Add Security Models**
- Create AuditLog, Role, TwoFactorAuth tables
- Create CustomerUser, PortalBranding tables

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Pipeline & Deal Management Properties

Property 1: Deal creation stores all required fields
*For any* deal with name, value, expected close date, and company, creating the deal should result in all fields being retrievable from the database.
**Validates: Requirements 1.1**

Property 2: New deals start at first pipeline stage
*For any* newly created deal, the deal's stage should be the first stage (lowest order number) of its assigned pipeline.
**Validates: Requirements 1.2**

Property 3: Deals can transition through all valid stages
*For any* deal and any valid stage in its pipeline, moving the deal to that stage should succeed and the deal's current stage should reflect the change.
**Validates: Requirements 1.3**

Property 4: Closing deals requires win/loss reason
*For any* deal being moved to "Closed Won" or "Closed Lost" status, the operation should fail if no win/loss reason is provided.
**Validates: Requirements 1.4**

Property 5: Sales forecast calculation accuracy
*For any* set of open deals, the calculated forecast should equal the sum of (deal.value × stage.probability) for all deals.
**Validates: Requirements 1.5, 7.2**

Property 6: Kanban board organization
*For any* pipeline, the Kanban board data structure should group deals by stage with each stage containing only deals assigned to that stage.
**Validates: Requirements 1.6**

Property 7: Multiple pipelines maintain independence
*For any* two different pipelines, deals in one pipeline should have stages independent from deals in the other pipeline.
**Validates: Requirements 1.8**

### Contact & Company Management Properties

Property 8: Company creation stores all fields
*For any* company with name, industry, size, and custom field values, creating the company should result in all fields being retrievable.
**Validates: Requirements 2.1**

Property 9: Contact creation stores all fields
*For any* contact with name, email, phone, role, and custom field values, creating the contact should result in all fields being retrievable.
**Validates: Requirements 2.2**

Property 10: Company-contact associations
*For any* company, adding multiple contacts to that company should result in all contacts being retrievable when querying the company's contacts.
**Validates: Requirements 2.3**

Property 11: Company hierarchy integrity
*For any* company with a parent company, the parent-child relationship should be maintained and queryable in both directions.
**Validates: Requirements 2.4**

Property 12: Custom field type support
*For any* custom field of type text, number, date, dropdown, checkbox, or multi-select, storing and retrieving a value should preserve the value according to the field type.
**Validates: Requirements 2.5**

Property 13: Lead score calculation consistency
*For any* contact and scoring criteria, the calculated lead score should be deterministic and match the configured scoring rules.
**Validates: Requirements 2.6**

Property 14: Duplicate detection by email and phone
*For any* contact being imported, if another contact exists with the same email or phone number, the system should flag it as a potential duplicate.
**Validates: Requirements 2.7**

Property 15: CSV export-import round trip
*For any* set of contacts and companies, exporting to CSV then importing should result in equivalent records (preserving all field values).
**Validates: Requirements 2.8**

Property 16: Contact role validation
*For any* contact, the assigned role should be one of: Decision Maker, Influencer, Champion, Blocker, or End User.
**Validates: Requirements 2.9**

### Task & Project Management Properties

Property 17: Task creation stores all fields
*For any* task with title, description, assignee, due date, and priority, creating the task should result in all fields being retrievable.
**Validates: Requirements 3.1**

Property 18: Customer-facing task visibility
*For any* task marked as customer-facing, the task should appear in customer portal queries for that task's associated company.
**Validates: Requirements 3.2, 3.3, 9.4**

Property 19: Task dependency enforcement
*For any* task with dependencies, attempting to start the task should fail if any dependency task is not completed.
**Validates: Requirements 3.4**

Property 20: Milestone task grouping
*For any* milestone, all tasks associated with that milestone should be retrievable when querying the milestone's tasks.
**Validates: Requirements 3.5**

Property 21: Task template instantiation
*For any* task template, creating a task from the template should copy all template fields (title, description, priority) to the new task.
**Validates: Requirements 3.7**

Property 22: Task comments and attachments
*For any* task, adding comments and file attachments should result in them being retrievable when querying the task.
**Validates: Requirements 3.8**

Property 23: Task status validation
*For any* task, the status should be one of: Not Started, In Progress, Blocked, Completed, or Cancelled.
**Validates: Requirements 3.9**

### Customer Portal Properties

Property 24: Customer-agent authentication separation
*For any* customer credentials, attempting to authenticate as an agent should fail, and vice versa.
**Validates: Requirements 4.1**

Property 25: Customer data isolation
*For any* customer user, all queries should return only data belonging to that customer's company (tasks, documents, contacts, deals).
**Validates: Requirements 4.2, 4.8**

Property 26: Customer document access
*For any* document marked as customer-visible, customers of the associated company should be able to retrieve and download the document.
**Validates: Requirements 4.3**

Property 27: Milestone completion calculation
*For any* milestone, the completion percentage should equal (completed_tasks / total_tasks) × 100.
**Validates: Requirements 4.4**

Property 28: Customer-agent messaging
*For any* message sent by a customer, the message should be delivered to the agent assigned to that customer's company.
**Validates: Requirements 4.5**

Property 29: White-label branding application
*For any* workspace with custom branding configured, the customer portal should render using the custom logo, colors, and domain.
**Validates: Requirements 4.6**

### Public REST API Properties

Property 30: API key authentication
*For any* valid API key, requests with that key should be authenticated and authorized according to the key's scopes.
**Validates: Requirements 5.3**

Property 31: Rate limiting enforcement
*For any* API key, the 1001st request within a 1-hour window should be rejected with a 429 status code.
**Validates: Requirements 5.5**

Property 32: Webhook event dispatch
*For any* subscribed event (deal.created, deal.updated, task.completed, contact.created), the event should trigger a webhook delivery to all active subscriptions.
**Validates: Requirements 5.7**

Property 33: Webhook retry logic
*For any* failed webhook delivery, the system should retry up to 3 times with exponential backoff (1s, 2s, 4s).
**Validates: Requirements 5.8**

Property 34: Webhook signature verification
*For any* webhook delivery, the signature should be HMAC-SHA256(secret, payload) and verifiable by the recipient.
**Validates: Requirements 5.9**

### Google Workspace Integration Properties

Property 35: Email-to-contact association
*For any* synced email, the email should be associated with the contact whose email address matches the sender or recipient.
**Validates: Requirements 6.2, 10.1**

Property 36: Email tracking functionality
*For any* email sent through the CRM, the tracking pixel and rewritten links should correctly record opens and clicks.
**Validates: Requirements 6.3, 10.3**

Property 37: Calendar event activity creation
*For any* Google Calendar event with contact attendees, syncing should create an activity record linked to those contacts.
**Validates: Requirements 6.4**

Property 38: Google Drive file attachment
*For any* Google Drive file attached to a deal or task, the Drive file ID should be stored and retrievable.
**Validates: Requirements 6.6**

### Reporting & Analytics Properties

Property 39: Pipeline report aggregation
*For any* pipeline, the report should correctly aggregate deal count and total value grouped by stage.
**Validates: Requirements 7.1**

Property 40: Win/loss analysis grouping
*For any* set of closed deals, the win/loss report should correctly group deals by win/loss reason with counts and percentages.
**Validates: Requirements 7.3**

Property 41: Sales cycle duration calculation
*For any* set of closed won deals, the average sales cycle duration should equal the mean of (closed_date - created_date) across all deals.
**Validates: Requirements 7.4**

Property 42: Stage conversion rate calculation
*For any* pipeline stage, the conversion rate should equal (deals_moved_to_next_stage / deals_entered_stage) × 100.
**Validates: Requirements 7.5**

Property 43: Custom report query generation
*For any* custom report with selected dimensions and metrics, the generated query should return data correctly grouped and aggregated.
**Validates: Requirements 7.6**

Property 44: Report export data integrity
*For any* report, exporting to Excel or PDF should contain the same data as displayed in the UI.
**Validates: Requirements 7.7**

### Security & Compliance Properties

Property 45: Comprehensive audit logging
*For any* user operation (create, read, update, delete), an audit log entry should be created with user_id, action, entity_type, entity_id, and timestamp.
**Validates: Requirements 8.1, 1.7, 9.7, 10.7, 12.5**

Property 46: Role-based access control
*For any* user with a specific role, operations should be permitted or denied according to the role's permissions.
**Validates: Requirements 8.2**

Property 47: Two-factor authentication enforcement
*For any* user with 2FA enabled, login should require a valid TOTP code in addition to password.
**Validates: Requirements 8.3**

Property 48: IP whitelist enforcement
*For any* workspace with IP whitelisting enabled, login attempts from non-whitelisted IPs should be rejected.
**Validates: Requirements 8.6**

Property 49: Session timeout enforcement
*For any* user session, the session should be invalidated after 30 minutes of inactivity.
**Validates: Requirements 8.7**

Property 50: Compliance report generation
*For any* date range, the compliance report should correctly aggregate audit log entries by action type and user.
**Validates: Requirements 8.9**

Property 51: GDPR data export completeness
*For any* user data export request, the export should include all data associated with that user across all tables.
**Validates: Requirements 8.10**

### Document Management Properties

Property 52: File size limit enforcement
*For any* file upload, files larger than 50MB should be rejected with an appropriate error message.
**Validates: Requirements 9.1**

Property 53: Document version history
*For any* document, replacing the file should create a new version record while preserving all previous versions.
**Validates: Requirements 9.2**

Property 54: Document template variable substitution
*For any* document template with variables, generating a document should replace all variables with actual values.
**Validates: Requirements 9.3**

Property 55: Document category filtering
*For any* document category (Proposals, Contracts, Invoices, General), querying by category should return only documents in that category.
**Validates: Requirements 9.5**

### Email Integration Properties

Property 56: Email template variable substitution
*For any* email template with variables, rendering the template should replace all variables with contact-specific values.
**Validates: Requirements 10.2**

Property 57: Unified inbox aggregation
*For any* contact, the unified inbox should return both WhatsApp messages and emails sorted chronologically.
**Validates: Requirements 10.5**

Property 58: Email sending and logging
*For any* email sent from a contact record, the email should be delivered and an activity record should be created.
**Validates: Requirements 10.6**

### QuickBooks Integration Properties

Property 59: QuickBooks sync error logging
*For any* failed QuickBooks sync operation, an error should be logged with details and an admin notification should be created.
**Validates: Requirements 11.6**

### Activity Timeline Properties

Property 60: Timeline chronological ordering
*For any* contact, company, or deal, the activity timeline should return all activities sorted by created_at in descending order.
**Validates: Requirements 12.1**

Property 61: Timeline activity type completeness
*For any* activity timeline, the results should include all activity types: emails, WhatsApp messages, calls, meetings, tasks, notes, and system events.
**Validates: Requirements 12.2**

Property 62: Manual note creation
*For any* agent adding a note to a timeline, the note should be stored and appear in subsequent timeline queries.
**Validates: Requirements 12.3**

Property 63: Timeline file attachments
*For any* activity, attaching files should result in the files being retrievable when querying the activity.
**Validates: Requirements 12.4**

Property 64: Timeline filtering
*For any* timeline query with filters (activity type, date range), the results should include only activities matching all filters.
**Validates: Requirements 12.6**

Property 65: Activity user attribution
*For any* activity, the activity record should include the user_id of the agent who performed the action.
**Validates: Requirements 12.7**

### Collaboration Properties

Property 66: Mention notification creation
*For any* note containing @username, a notification should be created for the mentioned user.
**Validates: Requirements 13.2**

Property 67: Internal note visibility
*For any* note marked as internal-only, the note should not appear in customer portal queries.
**Validates: Requirements 13.3**

Property 68: Activity feed recency
*For any* activity feed query, the results should return recent activities across all records sorted by created_at descending.
**Validates: Requirements 13.4**

Property 69: Follow notification creation
*For any* followed entity (contact, company, deal), changes to that entity should create notifications for all following users.
**Validates: Requirements 13.5**

Property 70: Unread notification count
*For any* user, the unread notification count should equal the number of notifications where is_read = false.
**Validates: Requirements 13.6**

## Error Handling

### Error Categories

1. **Validation Errors** (400 Bad Request)
   - Missing required fields
   - Invalid field types or formats
   - Business rule violations (e.g., closing deal without reason)

2. **Authentication Errors** (401 Unauthorized)
   - Invalid credentials
   - Expired tokens
   - Missing API keys

3. **Authorization Errors** (403 Forbidden)
   - Insufficient permissions
   - RBAC violations
   - IP whitelist violations

4. **Not Found Errors** (404 Not Found)
   - Entity does not exist
   - Workspace not found

5. **Conflict Errors** (409 Conflict)
   - Duplicate records
   - Concurrent modification conflicts

6. **Rate Limit Errors** (429 Too Many Requests)
   - API rate limit exceeded
   - Include Retry-After header

7. **Integration Errors** (502 Bad Gateway)
   - Google API failures
   - QuickBooks API failures
   - Webhook delivery failures

8. **Server Errors** (500 Internal Server Error)
   - Unexpected exceptions
   - Database errors

### Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Deal value must be a positive number",
    "field": "value",
    "details": {}
  }
}
```

### Error Handling Strategy

- **Graceful Degradation**: If Google sync fails, continue with core CRM functionality
- **Retry Logic**: Exponential backoff for webhook deliveries and external API calls
- **User Feedback**: Clear, actionable error messages
- **Logging**: All errors logged with context for debugging
- **Monitoring**: Alert on critical errors (auth failures, data corruption)

## Testing Strategy

### Dual Testing Approach

The system requires both unit testing and property-based testing for comprehensive coverage:

- **Unit Tests**: Verify specific examples, edge cases, and error conditions
- **Property Tests**: Verify universal properties across all inputs
- Together they provide comprehensive coverage: unit tests catch concrete bugs, property tests verify general correctness

### Property-Based Testing

**Library Selection:**
- Python: Use `hypothesis` library for property-based testing
- Minimum 100 iterations per property test
- Each test must reference its design document property

**Test Configuration:**
```python
from hypothesis import given, settings
import hypothesis.strategies as st

@settings(max_examples=100)
@given(deal=st.builds(Deal, ...))
def test_property_5_sales_forecast_calculation(deal):
    """
    Feature: enterprise-crm-features
    Property 5: Sales forecast calculation accuracy
    """
    # Test implementation
```

**Property Test Coverage:**
- All 70 correctness properties must have corresponding property tests
- Each property test validates the universal quantification
- Tests should generate random valid inputs using Hypothesis strategies

### Unit Testing

**Focus Areas:**
- Specific examples demonstrating correct behavior
- Edge cases (empty lists, null values, boundary conditions)
- Error conditions (invalid inputs, missing data)
- Integration points between components

**Unit Test Balance:**
- Avoid writing too many unit tests - property tests handle input coverage
- Focus unit tests on:
  - Concrete examples from requirements
  - Edge cases not easily expressed as properties
  - Integration between components
  - Error handling paths

**Example Unit Tests:**
```python
def test_deal_creation_with_all_fields():
    """Test creating a deal with all required fields"""
    # Validates: Requirements 1.1 (example)

def test_deal_close_without_reason_fails():
    """Test that closing a deal without reason raises error"""
    # Validates: Requirements 1.4 (error condition)

def test_empty_pipeline_forecast():
    """Test forecast calculation with no deals"""
    # Validates: Requirements 1.5 (edge case)
```

### Integration Testing

**Critical Integration Points:**
- Google Workspace OAuth flow
- QuickBooks OAuth flow and data sync
- Webhook delivery and retry logic
- Email sending and tracking
- Customer portal authentication

### Test Data Generation

**Hypothesis Strategies:**
```python
# Generate valid companies
companies = st.builds(
    Company,
    name=st.text(min_size=1, max_size=200),
    industry=st.sampled_from(['Pharmaceutical', 'Technology', 'Healthcare']),
    size=st.sampled_from(['1-10', '11-50', '51-200', '201-500', '500+'])
)

# Generate valid deals
deals = st.builds(
    Deal,
    name=st.text(min_size=1, max_size=200),
    value=st.decimals(min_value=0, max_value=1000000, places=2),
    expected_close_date=st.dates()
)

# Generate valid contacts
contacts = st.builds(
    Contact,
    first_name=st.text(min_size=1, max_size=100),
    last_name=st.text(min_size=1, max_size=100),
    email=st.emails(),
    phone=st.from_regex(r'\+?[1-9]\d{1,14}')
)
```

### Test Environment

- **Development**: SQLite with test fixtures
- **CI/CD**: PostgreSQL with Docker
- **Test Isolation**: Each test uses a separate workspace_id
- **Cleanup**: Rollback transactions after each test

### Performance Testing

**Load Testing:**
- 15 concurrent users
- 300 companies with 3-5 contacts each
- 1000 deals across all pipelines
- Measure response times for critical operations

**Targets:**
- API response time < 200ms (p95)
- Page load time < 1s
- Database queries < 100ms

### Security Testing

- **Penetration Testing**: SQL injection, XSS, CSRF
- **Authentication Testing**: Brute force protection, session hijacking
- **Authorization Testing**: RBAC bypass attempts, data isolation
- **Compliance Testing**: Audit log completeness, encryption verification

