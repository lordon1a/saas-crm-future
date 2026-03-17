# Implementation Plan: Enterprise CRM Features

## Overview

This implementation plan transforms the WhatsApp CRM into an enterprise-grade platform by adding 13 major feature areas. The plan follows an incremental approach, building core data models first, then business logic, then integrations, and finally security and compliance features. Each major feature includes property-based tests to validate correctness properties from the design document.

The implementation leverages the existing Flask/SQLAlchemy architecture and maintains multi-tenant isolation throughout.

## Tasks

### Phase 1: Core Data Models & Database Schema

- [x] 1. Create database models for pipeline and deal management
  - Create `Pipeline`, `DealStage`, and `Deal` models in new file `models_crm.py`
  - Include all fields from design: name, value, expected_close_date, status, win_loss_reason
  - Add workspace_id foreign keys for multi-tenant isolation
  - Create database migration script
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x]* 1.1 Write property tests for deal management
  - **Property 1: Deal creation stores all required fields**
  - **Property 2: New deals start at first pipeline stage**
  - **Property 3: Deals can transition through all valid stages**
  - **Property 4: Closing deals requires win/loss reason**
  - **Validates: Requirements 1.1, 1.2, 1.3, 1.4**

- [x] 2. Create database models for companies and contacts
  - Create `Company`, `Contact`, `CustomField`, `CustomFieldValue` models
  - Link Contact to existing Customer model for WhatsApp integration
  - Support company hierarchies with parent_company_id
  - Add custom field support for all entity types
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x]* 2.1 Write property tests for contact and company management
  - **Property 8: Company creation stores all fields**
  - **Property 9: Contact creation stores all fields**
  - **Property 10: Company-contact associations**
  - **Property 11: Company hierarchy integrity**
  - **Property 12: Custom field type support**
  - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**

- [x] 3. Create database models for tasks and projects
  - Create `Task`, `TaskDependency`, `Milestone`, `TaskComment`, `TaskAttachment` models
  - Support customer-facing vs internal-only tasks
  - Add task status workflow and priority levels
  - Link tasks to companies, deals, and milestones
  - _Requirements: 3.1, 3.2, 3.4, 3.5, 3.9_

- [x]* 3.1 Write property tests for task management
  - **Property 17: Task creation stores all fields**
  - **Property 18: Customer-facing task visibility**
  - **Property 19: Task dependency enforcement**
  - **Property 20: Milestone task grouping**
  - **Property 23: Task status validation**
  - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.9**

- [x] 4. Create database models for activity timeline
  - Create unified `Activity` model for all interaction types
  - Support activity types: email, whatsapp, call, meeting, note, task, system
  - Link activities to contacts, companies, and deals
  - Add metadata field for type-specific data (JSON)
  - _Requirements: 12.1, 12.2, 12.5_

- [x]* 4.1 Write property tests for activity timeline
  - **Property 60: Timeline chronological ordering**
  - **Property 61: Timeline activity type completeness**
  - **Property 65: Activity user attribution**
  - **Validates: Requirements 12.1, 12.2, 12.7**

- [x] 5. Create database models for documents
  - Create `Document`, `DocumentVersion`, `DocumentTemplate` models
  - Support version history and customer visibility flags
  - Add category field for organization
  - Link documents to companies and deals
  - _Requirements: 9.1, 9.2, 9.3, 9.5_

- [x]* 5.1 Write property tests for document management
  - **Property 52: File size limit enforcement**
  - **Property 53: Document version history**
  - **Property 54: Document template variable substitution**
  - **Property 55: Document category filtering**
  - **Validates: Requirements 9.1, 9.2, 9.3, 9.5**

- [x] 6. Checkpoint - Database schema complete
  - Run all migrations and verify tables created
  - Test multi-tenant isolation with workspace_id filters
  - Ensure all tests pass, ask the user if questions arise

### Phase 2: Pipeline & Deal Management

- [x] 7. Implement pipeline service and business logic
  - Create `services/pipeline_service.py` with deal CRUD operations
  - Implement deal stage transitions with validation
  - Add win/loss reason requirement for closed deals
  - Implement sales forecasting calculation (weighted pipeline)
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x]* 7.1 Write property tests for pipeline calculations
  - **Property 5: Sales forecast calculation accuracy**
  - **Property 7: Multiple pipelines maintain independence**
  - **Validates: Requirements 1.5, 1.8**

- [x] 8. Create pipeline API endpoints
  - Create `routes/pipeline.py` blueprint
  - Implement POST /api/v1/deals (create deal)
  - Implement GET /api/v1/deals (list with filters)
  - Implement PATCH /api/v1/deals/{id} (update, move stage)
  - Implement GET /api/v1/deals/forecast (sales forecast)
  - Add workspace_id filtering to all queries
  - _Requirements: 1.1, 1.3, 1.5_

- [x] 9. Create pipeline UI components
  - Create `templates/pipeline.html` with Kanban board view
  - Implement drag-and-drop for stage transitions
  - Add deal detail modal with edit capabilities
  - Display forecast metrics in dashboard
  - _Requirements: 1.6_

- [x]* 9.1 Write property test for Kanban organization
  - **Property 6: Kanban board organization**
  - **Validates: Requirements 1.6**

- [x] 10. Implement activity logging for deal operations
  - Add activity creation on deal create, update, stage change
  - Store before/after values for audit trail
  - Link activities to deals and users
  - _Requirements: 1.7_

- [x]* 10.1 Write property test for activity logging
  - **Property 45: Comprehensive audit logging**
  - **Validates: Requirements 1.7, 8.1**

### Phase 3: Contact & Company Management

- [x] 11. Implement contact service and business logic
  - Create `services/contact_service.py` with company/contact CRUD
  - Implement custom field value storage and retrieval
  - Add lead scoring calculation logic
  - Implement duplicate detection by email and phone
  - _Requirements: 2.1, 2.2, 2.3, 2.6, 2.7_

- [x]* 11.1 Write property tests for contact operations
  - **Property 13: Lead score calculation consistency**
  - **Property 14: Duplicate detection by email and phone**
  - **Property 16: Contact role validation**
  - **Validates: Requirements 2.6, 2.7, 2.9**

- [x] 12. Implement CSV import/export functionality
  - Add CSV parsing with duplicate detection
  - Implement CSV export with all fields
  - Support custom fields in import/export
  - Add error handling for malformed CSV
  - _Requirements: 2.7, 2.8_

- [x]* 12.1 Write property test for CSV round trip
  - **Property 15: CSV export-import round trip**
  - **Validates: Requirements 2.8**

- [x] 13. Create contact API endpoints
  - Create `routes/contacts.py` blueprint
  - Implement POST /api/v1/companies (create company)
  - Implement GET /api/v1/companies (list with pagination)
  - Implement POST /api/v1/contacts (create contact)
  - Implement GET /api/v1/contacts (list with filters)
  - Implement POST /api/v1/contacts/import (CSV import)
  - Implement GET /api/v1/contacts/export (CSV export)
  - _Requirements: 2.1, 2.2, 2.7, 2.8_

- [x] 14. Create contact UI components
  - Create `templates/companies.html` with company list and detail views
  - Update `templates/contacts.html` with enhanced contact management
  - Add custom field editor UI
  - Add CSV import/export buttons
  - Display company hierarchy tree view
  - _Requirements: 2.1, 2.2, 2.4_

- [x] 15. Checkpoint - Contact management complete
  - Test company-contact relationships
  - Verify custom fields work for all types
  - Test CSV import/export with sample data
  - Ensure all tests pass, ask the user if questions arise

### Phase 4: Task & Project Management

- [x] 16. Implement task service and business logic
  - Create `services/task_service.py` with task CRUD operations
  - Implement task dependency validation
  - Add milestone progress calculation
  - Implement task template instantiation
  - Support customer-facing vs internal-only visibility
  - _Requirements: 3.1, 3.2, 3.4, 3.5, 3.7_

- [x]* 16.1 Write property tests for task operations
  - **Property 21: Task template instantiation**
  - **Property 22: Task comments and attachments**
  - **Property 27: Milestone completion calculation**
  - **Validates: Requirements 3.5, 3.7, 3.8, 4.4**

- [x] 17. Create task API endpoints
  - Create `routes/tasks.py` blueprint
  - Implement POST /api/v1/tasks (create task)
  - Implement GET /api/v1/tasks (list with filters)
  - Implement PATCH /api/v1/tasks/{id} (update task)
  - Implement POST /api/v1/tasks/{id}/dependencies (add dependency)
  - Implement GET /api/v1/milestones (list milestones)
  - _Requirements: 3.1, 3.4, 3.5_

- [x] 18. Create task UI components
  - Create `templates/tasks.html` with task list and Gantt chart
  - Add task creation modal with dependency selector
  - Display milestone progress bars
  - Add task comments and attachments UI
  - _Requirements: 3.1, 3.5, 3.8_

### Phase 5: Customer Portal

- [x] 19. Create customer portal authentication system
  - Create `CustomerUser` model for portal login
  - Implement JWT-based authentication for customers
  - Create `routes/portal.py` blueprint
  - Implement POST /portal/login (customer login, returns JWT)
  - Implement POST /portal/register (customer registration)
  - Add JWT token validation middleware
  - _Requirements: 4.1_

- [x]* 19.1 Write property test for authentication separation
  - **Property 24: Customer-agent authentication separation**
  - **Validates: Requirements 4.1**

- [x] 20. Implement customer portal data isolation
  - Add customer data filtering to all portal queries
  - Ensure customers only see their company's data
  - Implement customer-facing task filtering
  - Implement customer-visible document filtering
  - _Requirements: 4.2, 4.8_

- [x]* 20.1 Write property tests for data isolation
  - **Property 25: Customer data isolation**
  - **Property 26: Customer document access**
  - **Validates: Requirements 4.2, 4.3, 4.8**

- [x] 21. Create customer portal UI
  - Create `templates/portal/` directory for portal templates
  - Create `portal/login.html` with customer login form
  - Create `portal/dashboard.html` with tasks and milestones
  - Create `portal/documents.html` with document list
  - Create `portal/messages.html` with communication hub
  - _Requirements: 4.2, 4.3, 4.5_

- [x] 22. Implement white-label branding
  - Create `PortalBranding` model
  - Add branding configuration UI in settings
  - Apply custom logo, colors, and domain to portal
  - Support custom CSS overrides
  - _Requirements: 4.6_

- [x]* 22.1 Write property test for branding application
  - **Property 29: White-label branding application**
  - **Validates: Requirements 4.6**

- [x] 23. Implement customer-agent messaging
  - Add messaging endpoints to portal API
  - Link messages to assigned agents
  - Create notification system for new messages
  - _Requirements: 4.5_

- [x]* 23.1 Write property test for messaging
  - **Property 28: Customer-agent messaging**
  - **Validates: Requirements 4.5**

- [x] 24. Checkpoint - Customer portal complete
  - Test customer login and JWT authentication
  - Verify data isolation with multiple test customers
  - Test white-label branding with custom settings
  - Ensure all tests pass, ask the user if questions arise

### Phase 6: Public REST API

- [x] 25. Create API authentication system
  - Create `APIKey` and `OAuthClient` models
  - Implement API key generation and validation
  - Create `services/api_auth_service.py`
  - Add API key authentication decorator
  - Implement OAuth 2.0 authorization code flow
  - _Requirements: 5.3, 5.4_

- [x]* 25.1 Write property test for API authentication
  - **Property 30: API key authentication**
  - **Validates: Requirements 5.3**

- [x] 26. Implement API rate limiting
  - Configure Flask-Limiter for API endpoints
  - Set 1000 requests/hour limit per API key
  - Return 429 status with Retry-After header
  - Store rate limit state in Redis (or memory for dev)
  - _Requirements: 5.5_

- [x]* 26.1 Write property test for rate limiting
  - **Property 31: Rate limiting enforcement**
  - **Validates: Requirements 5.5**

- [x] 27. Create comprehensive API documentation
  - Install and configure flask-restx or flasgger
  - Add OpenAPI decorators to all API endpoints
  - Generate Swagger UI at /api/docs
  - Document all request/response schemas
  - Add authentication examples
  - _Requirements: 5.2_

- [x] 28. Implement webhook system
  - Create `WebhookSubscription` and `WebhookDelivery` models
  - Create `services/webhook_service.py`
  - Implement webhook event dispatch for: deal.created, deal.updated, task.completed, contact.created
  - Add HMAC signature generation
  - Implement retry logic with exponential backoff (3 retries)
  - _Requirements: 5.7, 5.8, 5.9_

- [x]* 28.1 Write property tests for webhooks
  - **Property 32: Webhook event dispatch**
  - **Property 33: Webhook retry logic**
  - **Property 34: Webhook signature verification**
  - **Validates: Requirements 5.7, 5.8, 5.9**

- [x] 29. Create webhook management UI
  - Add webhook configuration page in settings
  - Allow creating/editing/deleting webhook subscriptions
  - Display webhook delivery history and status
  - Add webhook testing tool
  - _Requirements: 5.7_

### Phase 7: Google Workspace Integration

- [x] 30. Implement Google OAuth authentication
  - Create `GoogleIntegration` model
  - Install google-auth and google-api-python-client libraries
  - Implement OAuth 2.0 flow for Google Workspace
  - Create `services/google_service.py`
  - Add Google OAuth callback endpoint
  - Store access and refresh tokens securely
  - _Requirements: 6.1_

- [x] 31. Implement Gmail sync
  - Create `EmailSync` model
  - Use Gmail API to fetch emails
  - Match emails to contacts by email address
  - Create activity records for synced emails
  - Implement background sync job (every 5 minutes)
  - _Requirements: 6.2_

- [x]* 31.1 Write property test for email association
  - **Property 35: Email-to-contact association**
  - **Validates: Requirements 6.2, 10.1**

- [x] 32. Implement email tracking
  - Create `EmailTracking` model
  - Add tracking pixel to outgoing emails
  - Implement link rewriting for click tracking
  - Create tracking endpoints: /track/open/{id}, /track/click/{id}
  - Record opens and clicks in database
  - _Requirements: 6.3_

- [x]* 32.1 Write property test for email tracking
  - **Property 36: Email tracking functionality**
  - **Validates: Requirements 6.3, 10.3**

- [x] 33. Implement Google Calendar sync
  - Use Google Calendar API to fetch events
  - Match events to contacts by attendee email
  - Create activity records for meetings
  - Implement background sync job
  - _Requirements: 6.4_

- [x]* 33.1 Write property test for calendar sync
  - **Property 37: Calendar event activity creation**
  - **Validates: Requirements 6.4**

- [x] 34. Implement Google Drive integration
  - Add Drive file picker UI
  - Store Drive file IDs with deals and tasks
  - Implement file preview and download
  - _Requirements: 6.6_

- [x]* 34.1 Write property test for Drive attachments
  - **Property 38: Google Drive file attachment**
  - **Validates: Requirements 6.6**

- [x] 35. Create Google integration UI
  - Add "Connect Google" button in settings
  - Display sync status and last sync time
  - Add manual sync trigger button
  - Show synced emails in unified inbox
  - _Requirements: 6.1, 6.2_

### Phase 8: Advanced Reporting & Analytics

- [x] 36. Implement report service
  - Create `Report` and `ReportSchedule` models
  - Create `services/report_service.py`
  - Implement pipeline report generation
  - Implement win/loss analysis report
  - Implement sales cycle duration report
  - Implement stage conversion rate report
  - _Requirements: 7.1, 7.3, 7.4, 7.5_

- [x]* 36.1 Write property tests for report calculations
  - **Property 39: Pipeline report aggregation**
  - **Property 40: Win/loss analysis grouping**
  - **Property 41: Sales cycle duration calculation**
  - **Property 42: Stage conversion rate calculation**
  - **Validates: Requirements 7.1, 7.3, 7.4, 7.5**

- [x] 37. Implement custom report builder
  - Create drag-and-drop report builder UI
  - Allow selecting dimensions (stage, owner, date)
  - Allow selecting metrics (count, sum, average)
  - Generate SQL queries dynamically
  - Save custom reports
  - _Requirements: 7.6_

- [x]* 37.1 Write property test for custom reports
  - **Property 43: Custom report query generation**
  - **Validates: Requirements 7.6**

- [x] 38. Implement report export
  - Install openpyxl for Excel export
  - Install reportlab for PDF export
  - Implement Excel export with formatting
  - Implement PDF export with charts
  - _Requirements: 7.7_

- [x]* 38.1 Write property test for report exports
  - **Property 44: Report export data integrity**
  - **Validates: Requirements 7.7**

- [x] 39. Create reporting UI
  - Create `templates/reports.html` with report dashboard
  - Add report type selector (pipeline, forecast, win/loss, cycle)
  - Display charts using Chart.js
  - Add export buttons (Excel, PDF)
  - Add report scheduling UI
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.7_

- [x] 40. Checkpoint - Reporting complete
  - Test all report types with sample data
  - Verify calculations match design formulas
  - Test export formats
  - Ensure all tests pass, ask the user if questions arise

### Phase 9: Security & Compliance (SOC 2)

- [x] 41. Backend/DB: Comprehensive audit logging
  - Create `AuditLog` model and persistence strategy
  - Create `services/audit_service.py`
  - Add audit logging decorator to all critical CRUD routes
  - Log user_id, action, entity_type, entity_id, IP, user_agent
  - Store before/after values for updates
  - _Requirements: 8.1_

- [x] 42. Backend/DB: Role-based access control foundation
  - Create `Role`, `Permission`, and user-role mappings
  - Define built-in roles: Admin, Manager, Agent, Read-Only
  - Create backend permission checking middleware/decorator
  - Enforce permissions on all protected endpoints
  - _Requirements: 8.2_

- [x] 43. Backend/DB: Two-factor authentication core
  - Create `TwoFactorAuth` model and backup codes table
  - Implement TOTP generation/verification service
  - Enforce 2FA checks in login flow backend
  - _Requirements: 8.3_

- [x] 44. Backend/DB: IP whitelist enforcement
  - Create `IPWhitelist` model
  - Add IP whitelist middleware for auth endpoints
  - Reject non-whitelisted login attempts with audit logs
  - _Requirements: 8.6_

- [x] 45. Backend/DB: Session security hardening
  - Configure timeout and idle expiration strategy
  - Implement session activity tracking
  - Add optional remember-me token policy
  - _Requirements: 8.7_

- [x] 46. Backend/DB: Compliance and GDPR backend services
  - Create compliance report generator service
  - Implement GDPR export/delete request processors
  - Add safe background processing for heavy exports
  - _Requirements: 8.9, 8.10_

- [x] 47. Frontend/UI: Security and compliance management screens
  - Add role management, 2FA setup, IP whitelist, compliance, and GDPR panels in existing settings pages
  - Mevcut Tailwind CSS yapisini, sidebar'i ve renk paletini koru. ASLA sifirdan bagimsiz HTML sayfalari veya ucube tasarimlar icat etme.

- [x]* 47.1 Property tests for security features
  - **Property 46: Role-based access control**
  - **Property 47: Two-factor authentication enforcement**
  - **Property 48: IP whitelist enforcement**
  - **Property 49: Session timeout enforcement**
  - **Property 50: Compliance report generation**
  - **Property 51: GDPR data export completeness**

- [x] 48. Sistem Saglik Taramasi (Health Check)
  - Yeni eklenen kodlarin, Phase 1-8 arasindaki mevcut WhatsApp, Google OAuth ve CRM rotalarini/iliskilerini (Cascade deletes) bozmadigini denetle.

### Phase 10: Document Management

- [x] 49. Backend/DB: Document service and storage engine
  - Create `services/document_service.py`
  - Implement file upload with 50MB validation
  - Implement version control on replace operations
  - Support local and S3-compatible storage adapters
  - Generate workspace-isolated file paths and metadata
  - _Requirements: 9.1, 9.2_

- [x] 50. Backend/DB: Document templates and rendering
  - Implement Jinja2-based template parser/substitution service
  - Support variables: `{company_name}`, `{contact_name}`, `{deal_value}`, `{today_date}`
  - Persist template revisions and audit metadata
  - _Requirements: 9.3_

- [x] 51. Backend/DB: Document API layer
  - Create `routes/documents.py` blueprint
  - Implement upload/list/download/version endpoints
  - Add workspace filtering, pagination, and permission checks
  - _Requirements: 9.1, 9.2, 9.5_

- [x] 52. Frontend/UI: Document library screens
  - Extend existing CRM navigation with document library, filters, preview, and version history UI
  - Mevcut Tailwind CSS yapisini, sidebar'i ve renk paletini koru. ASLA sifirdan bagimsiz HTML sayfalari veya ucube tasarimlar icat etme.

- [x]* 52.1 Property tests for document workflows
  - **Property 52: File size limit enforcement**
  - **Property 53: Document version history**
  - **Property 54: Document template variable substitution**
  - **Property 55: Document category filtering**

- [x] 52.2 Sistem Saglik Taramasi (Health Check)
  - Yeni eklenen kodlarin, Phase 1-8 arasindaki mevcut WhatsApp, Google OAuth ve CRM rotalarini/iliskilerini (Cascade deletes) bozmadigini denetle.

### Phase 11: Email Integration & Tracking

- [x] 53. Backend/DB: Email template and sequence engine
  - Create `EmailTemplate`, `EmailSequence`, and delivery state models
  - Implement variable substitution and validation
  - Add safe send queue contracts for provider integrations
  - _Requirements: 10.2_

- [x] 54. Backend/DB: Unified inbox backend aggregation
  - Combine WhatsApp and Email streams in a normalized query/service
  - Add channel filtering and stable chronology ordering
  - Include pagination and workspace/user scoping
  - _Requirements: 10.5_

- [x] 55. Backend/DB: Outbound email sending and tracking integration
  - Implement SMTP/provider abstraction (SendGrid/Mailgun-ready)
  - Create activity logs for outbound emails
  - Reuse Phase 7 tracking hooks for opens/clicks
  - _Requirements: 10.6_

- [x] 56. Frontend/UI: Email composer, templates, and unified inbox UX
  - Add composer and template editor to existing contact/company/deal flows
  - Add channel filters and timeline blending in current inbox experience
  - Mevcut Tailwind CSS yapisini, sidebar'i ve renk paletini koru. ASLA sifirdan bagimsiz HTML sayfalari veya ucube tasarimlar icat etme.

- [x]* 56.1 Property tests for email workflows
  - **Property 56: Email template variable substitution**
  - **Property 57: Unified inbox aggregation**
  - **Property 58: Email sending and logging**

- [x] 56.2 Sistem Saglik Taramasi (Health Check)
  - Yeni eklenen kodlarin, Phase 1-8 arasindaki mevcut WhatsApp, Google OAuth ve CRM rotalarini/iliskilerini (Cascade deletes) bozmadigini denetle.

### Phase 12: QuickBooks Integration

- [x] 57. Backend/DB: QuickBooks OAuth foundation
  - Create `QuickBooksIntegration` model
  - Implement OAuth 2.0 flow and secure token storage
  - Build `services/quickbooks_service.py`
  - _Requirements: 11.1_

- [x] 58. Backend/DB: Invoice and payment sync pipeline
  - Create `QuickBooksInvoice` model
  - Create invoices on deal close events
  - Poll payment statuses and sync back to deal lifecycle
  - _Requirements: 11.2, 11.3_

- [x] 59. Backend/DB: Error handling and resilience
  - Log QuickBooks API failures with correlation IDs
  - Add retry/backoff for transient errors
  - Add admin alert hooks for persistent sync failures
  - _Requirements: 11.6_

- [x] 60. Frontend/UI: QuickBooks settings and deal visibility
  - Add connect/status/manual-sync controls in existing settings/deal views
  - Mevcut Tailwind CSS yapisini, sidebar'i ve renk paletini koru. ASLA sifirdan bagimsiz HTML sayfalari veya ucube tasarimlar icat etme.

- [x]* 60.1 Property tests for QuickBooks reliability
  - **Property 59: QuickBooks sync error logging**

- [x] 60.2 Sistem Saglik Taramasi (Health Check)
  - Yeni eklenen kodlarin, Phase 1-8 arasindaki mevcut WhatsApp, Google OAuth ve CRM rotalarini/iliskilerini (Cascade deletes) bozmadigini denetle.

### Phase 13: Collaboration Tools

- [x] 61. Backend/DB: Mention and notification core
  - Create `Mention` and `Notification` models
  - Parse `@username` patterns in comments/notes
  - Trigger notification records for mentions and assignments
  - _Requirements: 13.1, 13.2, 13.6_

- [x] 62. Backend/DB: Follow and internal-note policies
  - Create `Follow` model and follow/unfollow APIs
  - Add `is_internal` note visibility controls in backend filters
  - Ensure customer portal excludes internal notes
  - _Requirements: 13.3, 13.5_

- [x] 63. Backend/DB: Activity feed aggregation service
  - Build recent activity aggregation with filters and pagination
  - Expose read-optimized endpoint contracts for dashboard usage
  - _Requirements: 13.4_

- [x] 64. Frontend/UI: Notifications and collaboration UX
  - Add notification bell, unread badges, activity feed widgets, follow controls in existing screens
  - Mevcut Tailwind CSS yapisini, sidebar'i ve renk paletini koru. ASLA sifirdan bagimsiz HTML sayfalari veya ucube tasarimlar icat etme.

- [x]* 64.1 Property tests for collaboration features
  - **Property 66: Mention notification creation**
  - **Property 67: Internal note visibility**
  - **Property 68: Activity feed recency**
  - **Property 69: Follow notification creation**
  - **Property 70: Unread notification count**

- [x] 64.2 Sistem Saglik Taramasi (Health Check)
  - Yeni eklenen kodlarin, Phase 1-8 arasindaki mevcut WhatsApp, Google OAuth ve CRM rotalarini/iliskilerini (Cascade deletes) bozmadigini denetle.

### Phase 14: Final Integration & Testing

- [x] 65. Backend/DB: Full integration verification
  - Ensure all operations create activity records consistently
  - Validate timeline coverage for all event types
  - Run migration consistency checks and relational integrity checks

- [x] 66. Backend/DB: Comprehensive test suite and coverage
  - Add unit, integration, and end-to-end tests for all post-Phase 8 features
  - Target >80% coverage for critical business modules

- [x] 67. Backend/DB: Performance and reliability hardening
  - Add required indexes and resolve N+1 queries
  - Add caching where safe and measurable
  - Execute load tests with 300 companies and 15 concurrent users

- [x] 68. Frontend/UI: Regression and UX consistency pass
  - Validate all newly added UI surfaces against existing CRM patterns and navigation
  - Mevcut Tailwind CSS yapisini, sidebar'i ve renk paletini koru. ASLA sifirdan bagimsiz HTML sayfalari veya ucube tasarimlar icat etme.

- [x] 69. Deployment and operations documentation
  - Document environment variables, migration flow, backup/restore, and monitoring

- [x] 70. Sistem Saglik Taramasi (Health Check) + Final checkpoint
  - Yeni eklenen kodlarin, Phase 1-8 arasindaki mevcut WhatsApp, Google OAuth ve CRM rotalarini/iliskilerini (Cascade deletes) bozmadigini denetle.
  - Run full test suite and integration verification before release.

## Notes

- Tasks marked with `*` are optional property-based testing tasks and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at major milestones
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation follows an incremental approach: data models -> business logic -> API -> UI -> integrations
- Multi-tenant isolation (workspace_id) must be maintained throughout all implementations
- All new features must preserve existing WhatsApp CRM behavior, Google OAuth stability, and established UI consistency
