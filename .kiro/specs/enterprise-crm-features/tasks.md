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

- [ ]* 1.1 Write property tests for deal management
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

- [ ]* 2.1 Write property tests for contact and company management
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


- [ ]* 3.1 Write property tests for task management
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

- [ ]* 4.1 Write property tests for activity timeline
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

- [ ]* 5.1 Write property tests for document management
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

- [ ]* 7.1 Write property tests for pipeline calculations
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

- [ ]* 9.1 Write property test for Kanban organization
  - **Property 6: Kanban board organization**
  - **Validates: Requirements 1.6**

- [x] 10. Implement activity logging for deal operations
  - Add activity creation on deal create, update, stage change
  - Store before/after values for audit trail
  - Link activities to deals and users
  - _Requirements: 1.7_

- [ ]* 10.1 Write property test for activity logging
  - **Property 45: Comprehensive audit logging**
  - **Validates: Requirements 1.7, 8.1**

### Phase 3: Contact & Company Management

- [x] 11. Implement contact service and business logic
  - Create `services/contact_service.py` with company/contact CRUD
  - Implement custom field value storage and retrieval
  - Add lead scoring calculation logic
  - Implement duplicate detection by email and phone
  - _Requirements: 2.1, 2.2, 2.3, 2.6, 2.7_

- [ ]* 11.1 Write property tests for contact operations
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

- [ ]* 12.1 Write property test for CSV round trip
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

- [ ]* 16.1 Write property tests for task operations
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

- [ ]* 19.1 Write property test for authentication separation
  - **Property 24: Customer-agent authentication separation**
  - **Validates: Requirements 4.1**

- [x] 20. Implement customer portal data isolation
  - Add customer data filtering to all portal queries
  - Ensure customers only see their company's data
  - Implement customer-facing task filtering
  - Implement customer-visible document filtering
  - _Requirements: 4.2, 4.8_

- [ ]* 20.1 Write property tests for data isolation
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

- [ ]* 22.1 Write property test for branding application
  - **Property 29: White-label branding application**
  - **Validates: Requirements 4.6**

- [x] 23. Implement customer-agent messaging
  - Add messaging endpoints to portal API
  - Link messages to assigned agents
  - Create notification system for new messages
  - _Requirements: 4.5_

- [ ]* 23.1 Write property test for messaging
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

- [ ] 31. Implement Gmail sync
  - Create `EmailSync` model
  - Use Gmail API to fetch emails
  - Match emails to contacts by email address
  - Create activity records for synced emails
  - Implement background sync job (every 5 minutes)
  - _Requirements: 6.2_

- [ ]* 31.1 Write property test for email association
  - **Property 35: Email-to-contact association**
  - **Validates: Requirements 6.2, 10.1**

- [ ] 32. Implement email tracking
  - Create `EmailTracking` model
  - Add tracking pixel to outgoing emails
  - Implement link rewriting for click tracking
  - Create tracking endpoints: /track/open/{id}, /track/click/{id}
  - Record opens and clicks in database
  - _Requirements: 6.3_

- [ ]* 32.1 Write property test for email tracking
  - **Property 36: Email tracking functionality**
  - **Validates: Requirements 6.3, 10.3**

- [ ] 33. Implement Google Calendar sync
  - Use Google Calendar API to fetch events
  - Match events to contacts by attendee email
  - Create activity records for meetings
  - Implement background sync job
  - _Requirements: 6.4_

- [ ]* 33.1 Write property test for calendar sync
  - **Property 37: Calendar event activity creation**
  - **Validates: Requirements 6.4**

- [ ] 34. Implement Google Drive integration
  - Add Drive file picker UI
  - Store Drive file IDs with deals and tasks
  - Implement file preview and download
  - _Requirements: 6.6_

- [ ]* 34.1 Write property test for Drive attachments
  - **Property 38: Google Drive file attachment**
  - **Validates: Requirements 6.6**

- [ ] 35. Create Google integration UI
  - Add "Connect Google" button in settings
  - Display sync status and last sync time
  - Add manual sync trigger button
  - Show synced emails in unified inbox
  - _Requirements: 6.1, 6.2_

### Phase 8: Advanced Reporting & Analytics

- [ ] 36. Implement report service
  - Create `Report` and `ReportSchedule` models
  - Create `services/report_service.py`
  - Implement pipeline report generation
  - Implement win/loss analysis report
  - Implement sales cycle duration report
  - Implement stage conversion rate report
  - _Requirements: 7.1, 7.3, 7.4, 7.5_

- [ ]* 36.1 Write property tests for report calculations
  - **Property 39: Pipeline report aggregation**
  - **Property 40: Win/loss analysis grouping**
  - **Property 41: Sales cycle duration calculation**
  - **Property 42: Stage conversion rate calculation**
  - **Validates: Requirements 7.1, 7.3, 7.4, 7.5**

- [ ] 37. Implement custom report builder
  - Create drag-and-drop report builder UI
  - Allow selecting dimensions (stage, owner, date)
  - Allow selecting metrics (count, sum, average)
  - Generate SQL queries dynamically
  - Save custom reports
  - _Requirements: 7.6_

- [ ]* 37.1 Write property test for custom reports
  - **Property 43: Custom report query generation**
  - **Validates: Requirements 7.6**

- [ ] 38. Implement report export
  - Install openpyxl for Excel export
  - Install reportlab for PDF export
  - Implement Excel export with formatting
  - Implement PDF export with charts
  - _Requirements: 7.7_

- [ ]* 38.1 Write property test for report exports
  - **Property 44: Report export data integrity**
  - **Validates: Requirements 7.7**

- [ ] 39. Create reporting UI
  - Create `templates/reports.html` with report dashboard
  - Add report type selector (pipeline, forecast, win/loss, cycle)
  - Display charts using Chart.js
  - Add export buttons (Excel, PDF)
  - Add report scheduling UI
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.7_

- [ ] 40. Checkpoint - Reporting complete
  - Test all report types with sample data
  - Verify calculations match design formulas
  - Test export formats
  - Ensure all tests pass, ask the user if questions arise

### Phase 9: Security & Compliance (SOC 2)

- [ ] 41. Implement comprehensive audit logging
  - Create `AuditLog` model
  - Create `services/audit_service.py`
  - Add audit logging decorator for all CRUD operations
  - Log user_id, action, entity_type, entity_id, IP, user_agent
  - Store before/after values for updates
  - _Requirements: 8.1_

- [ ] 42. Implement role-based access control
  - Create `Role` and `Permission` models
  - Define built-in roles: Admin, Manager, Agent, Read-Only
  - Create permission checking decorator
  - Add role management UI in settings
  - Enforce permissions on all endpoints
  - _Requirements: 8.2_

- [ ]* 42.1 Write property test for RBAC
  - **Property 46: Role-based access control**
  - **Validates: Requirements 8.2**

- [ ] 43. Implement two-factor authentication
  - Create `TwoFactorAuth` model
  - Install pyotp library for TOTP
  - Add 2FA setup flow with QR code
  - Generate and store backup codes
  - Enforce 2FA on login
  - _Requirements: 8.3_

- [ ]* 43.1 Write property test for 2FA
  - **Property 47: Two-factor authentication enforcement**
  - **Validates: Requirements 8.3**

- [ ] 44. Implement IP whitelisting
  - Create `IPWhitelist` model
  - Add IP whitelist checking middleware
  - Reject logins from non-whitelisted IPs
  - Add IP whitelist management UI
  - _Requirements: 8.6_

- [ ]* 44.1 Write property test for IP whitelisting
  - **Property 48: IP whitelist enforcement**
  - **Validates: Requirements 8.6**

- [ ] 45. Implement session management
  - Configure session timeout (30 minutes)
  - Add session activity tracking
  - Implement automatic session invalidation
  - Add "Remember me" option with longer timeout
  - _Requirements: 8.7_

- [ ]* 45.1 Write property test for session timeout
  - **Property 49: Session timeout enforcement**
  - **Validates: Requirements 8.7**

- [ ] 46. Implement compliance reporting
  - Create compliance report generator
  - Aggregate audit logs by action type and user
  - Generate access pattern reports
  - Add compliance report UI
  - _Requirements: 8.9_

- [ ]* 46.1 Write property test for compliance reports
  - **Property 50: Compliance report generation**
  - **Validates: Requirements 8.9**

- [ ] 47. Implement GDPR tools
  - Create data export functionality (all user data)
  - Implement right-to-be-forgotten (delete all user data)
  - Add GDPR request UI
  - Generate data export in JSON format
  - _Requirements: 8.10_

- [ ]* 47.1 Write property test for GDPR export
  - **Property 51: GDPR data export completeness**
  - **Validates: Requirements 8.10**

- [ ] 48. Checkpoint - Security complete
  - Test audit logging for all operations
  - Verify RBAC with different user roles
  - Test 2FA setup and login
  - Test IP whitelisting
  - Ensure all tests pass, ask the user if questions arise

### Phase 10: Document Management

- [ ] 49. Implement document service
  - Create `services/document_service.py`
  - Implement file upload with size validation (50MB limit)
  - Implement version control (create new version on replace)
  - Support local file storage and S3 (configurable)
  - Generate unique file paths per workspace
  - _Requirements: 9.1, 9.2_

- [ ]* 49.1 Write property tests for document operations
  - **Property 52: File size limit enforcement**
  - **Property 53: Document version history**
  - **Validates: Requirements 9.1, 9.2**

- [ ] 50. Implement document templates
  - Create template variable parser (Jinja2)
  - Support variables: {company_name}, {contact_name}, {deal_value}, {today_date}
  - Implement template instantiation
  - Add template management UI
  - _Requirements: 9.3_

- [ ]* 50.1 Write property test for template substitution
  - **Property 54: Document template variable substitution**
  - **Validates: Requirements 9.3**

- [ ] 51. Create document API endpoints
  - Create `routes/documents.py` blueprint
  - Implement POST /api/v1/documents (upload)
  - Implement GET /api/v1/documents (list with filters)
  - Implement GET /api/v1/documents/{id}/download
  - Implement POST /api/v1/documents/{id}/versions (new version)
  - _Requirements: 9.1, 9.2, 9.5_

- [ ] 52. Create document UI
  - Create `templates/documents.html` with document library
  - Add file upload with drag-and-drop
  - Display version history
  - Add category filtering
  - Show document preview
  - _Requirements: 9.1, 9.2, 9.5_

- [ ]* 52.1 Write property test for document filtering
  - **Property 55: Document category filtering**
  - **Validates: Requirements 9.5**

### Phase 11: Email Integration & Tracking

- [ ] 53. Implement email template system
  - Create `EmailTemplate` and `EmailSequence` models
  - Implement template variable substitution
  - Create email template editor UI
  - Support HTML and plain text templates
  - _Requirements: 10.2_

- [ ]* 53.1 Write property test for email templates
  - **Property 56: Email template variable substitution**
  - **Validates: Requirements 10.2**

- [ ] 54. Implement unified inbox
  - Combine WhatsApp messages and emails in single query
  - Sort by timestamp chronologically
  - Add channel filter (WhatsApp, Email, All)
  - Display in existing inbox UI
  - _Requirements: 10.5_

- [ ]* 54.1 Write property test for unified inbox
  - **Property 57: Unified inbox aggregation**
  - **Validates: Requirements 10.5**

- [ ] 55. Implement email sending from CRM
  - Add email composition UI in contact detail view
  - Integrate with SMTP or email service (SendGrid, Mailgun)
  - Create activity record for sent emails
  - Add email tracking (reuse from Phase 7)
  - _Requirements: 10.6_

- [ ]* 55.1 Write property test for email sending
  - **Property 58: Email sending and logging**
  - **Validates: Requirements 10.6**

### Phase 12: QuickBooks Integration

- [ ] 56. Implement QuickBooks OAuth authentication
  - Create `QuickBooksIntegration` model
  - Install intuit-oauth library
  - Implement OAuth 2.0 flow for QuickBooks
  - Create `services/quickbooks_service.py`
  - Store access and refresh tokens
  - _Requirements: 11.1_

- [ ] 57. Implement QuickBooks invoice sync
  - Create `QuickBooksInvoice` model
  - Create invoice in QuickBooks when deal closes
  - Poll QuickBooks for payment status updates
  - Update deal status when invoice is paid
  - _Requirements: 11.2, 11.3_

- [ ] 58. Implement QuickBooks error handling
  - Log all QuickBooks API errors
  - Create admin notifications for sync failures
  - Add retry logic for transient errors
  - _Requirements: 11.6_

- [ ]* 58.1 Write property test for error logging
  - **Property 59: QuickBooks sync error logging**
  - **Validates: Requirements 11.6**

- [ ] 59. Create QuickBooks integration UI
  - Add "Connect QuickBooks" button in settings
  - Display sync status
  - Show synced invoices in deal detail view
  - Add manual sync trigger
  - _Requirements: 11.1, 11.2_

### Phase 13: Collaboration Tools

- [ ] 60. Implement mention system
  - Create `Mention` model
  - Parse @username in notes and comments
  - Create mention records
  - Link mentions to activities
  - _Requirements: 13.1, 13.2_

- [ ]* 60.1 Write property test for mentions
  - **Property 66: Mention notification creation**
  - **Validates: Requirements 13.2**

- [ ] 61. Implement notification system
  - Create `Notification` model
  - Create notifications for: mentions, task assignments, deal updates
  - Add notification API endpoints
  - Mark notifications as read
  - _Requirements: 13.2, 13.6_

- [ ]* 61.1 Write property tests for notifications
  - **Property 69: Follow notification creation**
  - **Property 70: Unread notification count**
  - **Validates: Requirements 13.5, 13.6**

- [ ] 62. Implement follow system
  - Create `Follow` model
  - Allow following contacts, companies, and deals
  - Create notifications when followed entities change
  - Add follow/unfollow buttons in UI
  - _Requirements: 13.5_

- [ ] 63. Implement internal notes
  - Add is_internal flag to notes
  - Filter internal notes from customer portal queries
  - Add "Internal Note" checkbox in UI
  - _Requirements: 13.3_

- [ ]* 63.1 Write property test for internal notes
  - **Property 67: Internal note visibility**
  - **Validates: Requirements 13.3**

- [ ] 64. Create activity feed
  - Aggregate recent activities across all records
  - Sort by timestamp descending
  - Add activity feed widget to dashboard
  - Support filtering by activity type
  - _Requirements: 13.4_

- [ ]* 64.1 Write property test for activity feed
  - **Property 68: Activity feed recency**
  - **Validates: Requirements 13.4**

- [ ] 65. Create notification UI
  - Add notification bell icon in navigation
  - Display unread count badge
  - Create notification dropdown with recent notifications
  - Add "Mark all as read" button
  - _Requirements: 13.6_

### Phase 14: Final Integration & Testing

- [ ] 66. Integrate all activity logging
  - Ensure all operations create activity records
  - Verify activity timeline shows all event types
  - Test timeline filtering and pagination
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_

- [ ]* 66.1 Write remaining activity timeline property tests
  - **Property 62: Manual note creation**
  - **Property 63: Timeline file attachments**
  - **Property 64: Timeline filtering**
  - **Validates: Requirements 12.3, 12.4, 12.6**

- [ ] 67. Create comprehensive test suite
  - Write unit tests for all services
  - Write integration tests for API endpoints
  - Write end-to-end tests for critical workflows
  - Achieve >80% code coverage
  - _All Requirements_

- [ ] 68. Performance optimization
  - Add database indexes on foreign keys and frequently queried fields
  - Optimize N+1 queries with eager loading
  - Add caching for frequently accessed data
  - Test with 300 companies and 15 concurrent users
  - _All Requirements_

- [ ] 69. Create deployment documentation
  - Document environment variables
  - Document database migration process
  - Document backup and restore procedures
  - Document monitoring and alerting setup
  - _All Requirements_

- [ ] 70. Final checkpoint - System complete
  - Run full test suite
  - Verify all 70 correctness properties pass
  - Test all integrations (Google, QuickBooks)
  - Verify SOC 2 compliance features
  - Ensure all tests pass, ask the user if questions arise

## Notes

- Tasks marked with `*` are optional property-based testing tasks and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at major milestones
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation follows an incremental approach: data models → business logic → API → UI → integrations
- Multi-tenant isolation (workspace_id) must be maintained throughout all implementations
- All new features integrate with existing WhatsApp CRM functionality
