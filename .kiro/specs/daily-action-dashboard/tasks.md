# Implementation Plan: Daily Action Dashboard

## Overview

This plan implements a prioritized action list as a topbar bell button (similar to notifications) that surfaces high-value tasks for sales representatives. The bell icon appears in the topbar on all pages with a badge showing the action count. Clicking opens a dropdown with the top 10 prioritized actions. The implementation follows the service layer pattern, uses existing Flask/SQLAlchemy stack, maintains multi-tenant isolation, and follows the same UX pattern as notification-bell.js for consistency. All tasks build incrementally with checkpoints to validate functionality.

## Tasks

- [x] 1. Create database models and migration
  - [x] 1.1 Add new models to models_crm.py
    - Create DismissedAction model with workspace_id, user_id, action_id, dismissed_at, expires_at
    - Create DashboardSettings model with workspace_id and threshold configuration fields
    - Create WidgetEngagement model for analytics tracking
    - Add to_dict() methods to all new models
    - _Requirements: 6.1, 6.2, 7.1, 7.2, 8.1_
  
  - [x] 1.2 Create migration script
    - Create migrations/add_action_dashboard_tables.py
    - Include CREATE TABLE statements for dismissed_actions, dashboard_settings, widget_engagements
    - Add indexes: idx_dismissed_workspace_user, idx_dismissed_expires, idx_engagement_workspace_user, idx_engagement_event_type, idx_engagement_created
    - Add indexes on existing tables: idx_contact_lead_score_activity, idx_deal_close_date, idx_deal_stage_entered, idx_task_due_date
    - _Requirements: 9.4, 6.1_
  
  - [x] 1.3 Update app.py run_migrations() function
    - Add add_action_dashboard_tables migration to the run_migrations() function
    - Ensure migration runs on Render startup
    - _Requirements: 9.4_
  
  - [x] 1.4 Run migration locally
    - Execute flask db migrate -m "Add action dashboard tables and indexes"
    - Execute flask db upgrade
    - Verify tables created in database
    - _Requirements: 9.4_

- [x] 2. Implement service layer
  - [x] 2.1 Create services/action_dashboard_service.py
    - Create ActionDashboardService class with static methods
    - Implement get_or_create_settings() to fetch or create default DashboardSettings
    - Implement update_settings() for workspace configuration
    - _Requirements: 7.1, 7.2, 7.3_
  
  - [x] 2.2 Implement priority calculation methods
    - Implement prioritize_stale_contacts() - query contacts with high lead_score and old last_activity_at
    - Implement prioritize_deals() - query deals near close date, stale stage, or inactive negotiation
    - Implement prioritize_overdue_tasks() - query tasks with due_date before or equal to today
    - Each method returns list of ActionItem dataclass instances
    - Apply workspace_id filter to all queries
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 4.1, 4.2, 6.1, 6.3_
  
  - [x] 2.3 Implement ranking and filtering logic
    - Implement rank_and_merge() to combine candidates from all sources
    - Filter out dismissed actions using DismissedAction table
    - Sort by priority_score descending
    - Return top N items (default 10)
    - _Requirements: 1.2, 5.2, 9.5_
  
  - [x] 2.4 Implement calculate_action_items() orchestrator
    - Call get_or_create_settings() to get thresholds
    - Call all three priority methods (contacts, deals, tasks)
    - Query dismissed actions for current user
    - Call rank_and_merge() with all candidates
    - Return final list of ActionItem objects
    - _Requirements: 1.2, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 4.1, 4.2_
  
  - [x] 2.5 Implement action management methods
    - Implement dismiss_action() - create DismissedAction record with expires_at = now + 24h
    - Implement complete_action() - mark task as completed if action_type is 'task_overdue', otherwise dismiss
    - Implement track_engagement() - create WidgetEngagement record for analytics
    - _Requirements: 5.2, 5.3, 5.5, 8.1, 8.2, 8.3, 8.4_

- [x] 3. Checkpoint - Verify service layer logic
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Create API routes
  - [x] 4.1 Create routes/dashboard.py blueprint
    - Create Flask Blueprint with url_prefix='/api/dashboard'
    - Import ActionDashboardService and required models
    - Register blueprint in app.py
    - _Requirements: 1.1, 6.4_
  
  - [x] 4.2 Implement GET /api/dashboard/actions endpoint
    - Add @login_required decorator
    - Call ActionDashboardService.calculate_action_items() with current_user.workspace_id and current_user.id
    - Track widget_viewed engagement event
    - Return JSON with actions list and count
    - _Requirements: 1.1, 1.2, 1.5, 6.2, 8.1_
  
  - [x] 4.3 Implement POST /api/dashboard/actions/<action_id>/dismiss endpoint
    - Add @login_required decorator
    - Validate workspace_id matches current_user.workspace_id
    - Call ActionDashboardService.dismiss_action()
    - Track action_dismissed engagement event
    - Return success response
    - _Requirements: 5.2, 6.4, 8.3_
  
  - [x] 4.4 Implement POST /api/dashboard/actions/<action_id>/complete endpoint
    - Add @login_required decorator
    - Validate workspace_id matches current_user.workspace_id
    - Call ActionDashboardService.complete_action()
    - Track action_completed engagement event
    - Return success response
    - _Requirements: 5.3, 5.5, 6.4, 8.4_
  
  - [x] 4.5 Implement GET /api/dashboard/settings endpoint
    - Add @login_required decorator
    - Call ActionDashboardService.get_or_create_settings()
    - Return settings as JSON
    - _Requirements: 7.1, 7.3_
  
  - [x] 4.6 Implement PUT /api/dashboard/settings endpoint
    - Add @login_required decorator
    - Validate user has admin role (check current_user.role)
    - Call ActionDashboardService.update_settings() with request JSON
    - Return updated settings
    - _Requirements: 7.4, 7.5_

- [x] 5. Checkpoint - Test API endpoints
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement frontend bell component
  - [x] 6.1 Create static/action-bell.js
    - Create ActionBell class following notification-bell.js pattern
    - Implement init(), createBellHTML(), attachEventListeners() methods
    - Implement loadActions() to fetch from /api/dashboard/actions
    - Implement 5-minute auto-refresh using setInterval
    - Insert bell icon into topbar next to notification bell
    - _Requirements: 1.1, 1.4, 8.1_
  
  - [x] 6.2 Implement action item rendering in dropdown
    - Implement renderActions() to generate HTML for dropdown list
    - Apply priority-based border colors (urgent: red, high: orange, medium: yellow)
    - Display entity_name, recommended_action, context metadata, priority badges
    - Show "Harika iş! Bugün için yapılacak aksiyon yok" when list is empty
    - _Requirements: 1.2, 1.3, 1.5_
  
  - [x] 6.3 Implement action buttons and click handlers
    - Render dismiss button (X icon) for all actions
    - Render complete button (checkmark icon) only for task_overdue actions
    - Implement dismissAction() to POST to /api/dashboard/actions/<id>/dismiss
    - Implement completeAction() to POST to /api/dashboard/actions/<id>/complete
    - Implement onActionClick() to navigate to entity detail page
    - _Requirements: 5.1, 5.2, 5.3, 8.2_
  
  - [x] 6.4 Implement badge count display
    - Update badge with action count from API response
    - Show badge only when count > 0
    - Display "99+" for counts over 99
    - Update badge on every refresh
    - _Requirements: 1.2, 1.4_
  
  - [x] 6.5 Add mobile-responsive styling
    - Use Tailwind CSS responsive classes for dropdown width
    - Ensure dropdown doesn't overflow on mobile screens
    - Test touch interactions for dismiss/complete buttons
    - Ensure bell icon is visible and clickable on mobile
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [x] 7. Integrate bell into topbar globally
  - [x] 7.1 Add action-bell.js to base template
    - Include <script src="/static/action-bell.js"></script> in base template or topbar partial
    - Ensure script loads on all pages (not just dashboard)
    - Position bell icon between notification bell and user menu in topbar
    - Test bell appears and functions on multiple pages (contacts, deals, tasks, etc.)
    - _Requirements: 1.1, 10.1_
  
  - [x] 7.2 Test bell integration across pages
    - Verify bell displays on all authenticated pages
    - Verify auto-refresh works every 5 minutes
    - Verify dismiss and complete actions work from any page
    - Verify navigation to entity detail pages works
    - Verify dropdown closes when clicking outside
    - _Requirements: 1.1, 1.4, 5.1, 5.2, 5.3_

- [x] 8. Add settings UI to settings page
  - [x] 8.1 Modify templates/settings.html
    - Add "Dashboard Settings" section with form fields
    - Add input fields for high_score_threshold, medium_score_threshold
    - Add input fields for staleness days (high_score_staleness_days, medium_score_staleness_days)
    - Add input fields for deal thresholds (deal_close_warning_days, deal_stage_stale_days, deal_negotiation_stale_days)
    - Add save button with form submission handler
    - _Requirements: 7.4_
  
  - [x] 8.2 Add settings JavaScript to static/settings.js or inline
    - Implement fetch to GET /api/dashboard/settings on page load
    - Populate form fields with current settings
    - Implement form submission to PUT /api/dashboard/settings
    - Show success/error messages after save
    - _Requirements: 7.4, 7.5_

- [x] 9. Final checkpoint - End-to-end testing
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All database queries filtered by workspace_id for multi-tenant isolation
- Service layer handles all business logic, routes only handle HTTP
- ActionItem is an ephemeral dataclass, not persisted to database
- Dismissed actions expire after 24 hours automatically
- Bell component follows notification-bell.js pattern for consistent UX
- Bell appears in topbar on ALL pages, not just dashboard
- Badge shows action count, dropdown shows full list on click
- Migration must be added to app.py run_migrations() for Render deployment
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
