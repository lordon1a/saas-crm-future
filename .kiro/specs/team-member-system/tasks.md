# Implementation Plan: Team Member Management System

## Overview

This implementation plan breaks down the team member management system into discrete coding tasks. Each task builds on previous steps and includes specific references to requirements. The system extends the existing WhatsApp CRM to support multi-user workspaces with role-based access control.

## Tasks

- [x] 1. Extend User model and create TeamInvitation model
  - Add role, is_active, created_at, last_login, deleted_at columns to User model in models.py
  - Create TeamInvitation model with all fields (workspace_id, inviter_id, invitee_email, role, token, status, expires_at, created_at, accepted_at)
  - Add indexes and unique constraints as specified in design
  - Run `flask db migrate -m "Add team member fields to User and create TeamInvitation table"`
  - Run `flask db upgrade`
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 17.1, 17.2, 17.3, 17.4_

- [ ] 2. Add assignment fields to CRM entities
  - [x] 2.1 Add assigned_to column to Contact model in models_crm.py
    - Add foreign key to users.id with index
    - _Requirements: 6.1, 6.2_
  
  - [x] 2.2 Add assigned_to column to Company model in models_crm.py
    - Add foreign key to users.id with index
    - _Requirements: 6.1, 6.2_
  
  - [x] 2.3 Run migration for CRM entity assignment fields
    - Run `flask db migrate -m "Add assigned_to fields to Contact and Company"`
    - Run `flask db upgrade`
    - _Requirements: 17.5, 17.6, 17.7_

- [ ] 3. Implement TeamService for team management
  - [x] 3.1 Create services/team_service.py with TeamService class
    - Implement invite_member method (validate email, check duplicates, generate token, create invitation)
    - Implement accept_invitation method (validate token, create user, update invitation status)
    - Implement cancel_invitation method (update status to cancelled)
    - Implement list_team_members method (query active users by workspace)
    - Implement list_pending_invitations method (query pending invitations)
    - Implement update_member_role method (update user role with validation)
    - Implement remove_member method (soft delete user)
    - Implement transfer_ownership method (swap owner and admin roles)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 10.1, 10.2, 10.3, 10.4, 10.5, 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7_

- [ ] 4. Implement AssignmentService for entity assignments
  - [x] 4.1 Create services/assignment_service.py with AssignmentService class
    - Implement assign_entity method (validate assignee, update entity, create activity)
    - Implement get_assignable_members method (query active users)
    - Support entity types: contact, company, deal, task, conversation
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_

- [ ] 5. Extend EmailService for team notifications
  - [x] 5.1 Create or extend services/email_service.py
    - Implement send_invitation_email method (render HTML template, send via SMTP)
    - Implement send_assignment_notification method (send assignment emails)
    - Handle SMTP not configured gracefully (log instead of fail)
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.7_

- [ ] 6. Create team management API routes
  - [x] 6.1 Create routes/team.py with Blueprint
    - Implement GET /api/team/members (list team members and invitations)
    - Implement POST /api/team/invite (send invitation)
    - Implement POST /api/team/invitations/<id>/cancel (cancel invitation)
    - Implement PUT /api/team/members/<id>/role (update role)
    - Implement DELETE /api/team/members/<id> (remove member)
    - Implement POST /api/team/transfer-ownership (transfer ownership)
    - Add @login_required decorator to all endpoints
    - Add role-based permission checks (owner/admin)
    - Wrap all db.session.commit() in try/except with rollback
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 10.1, 10.2, 10.3, 10.4, 10.5, 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7, 18.1, 18.2, 18.3, 18.4, 18.5, 18.6, 18.7_
  
  - [x] 6.2 Register team blueprint in app.py
    - Import team blueprint
    - Register with app.register_blueprint
    - _Requirements: 18.1_

- [ ] 7. Extend auth routes for invitation acceptance
  - [x] 7.1 Add invitation acceptance endpoints to routes/auth.py
    - Implement GET /accept-invitation/<token> (display acceptance form)
    - Implement POST /accept-invitation (process acceptance, create user, create session)
    - Validate token, expiration, and status
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

- [ ] 8. Create assignment API routes
  - [x] 8.1 Create routes/assignments.py with Blueprint
    - Implement PUT /api/assignments/<entity_type>/<id> (assign entity)
    - Implement GET /api/assignments/members (get assignable members)
    - Add @login_required decorator
    - Add role-based permission checks
    - Wrap all db.session.commit() in try/except with rollback
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 18.1, 18.2, 18.3, 18.4, 18.5, 18.6, 18.7_
  
  - [x] 8.2 Register assignments blueprint in app.py
    - Import assignments blueprint
    - Register with app.register_blueprint
    - _Requirements: 18.1_

- [x] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Create team management frontend page
  - [x] 10.1 Create templates/team.html
    - Create team members table with columns: name, email, role, last_login, actions
    - Create pending invitations table with columns: email, role, invited by, expires, actions
    - Add "Invite Team Member" button
    - Add modal for invitation form (email, role selection)
    - Use Tailwind CSS for styling
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_
  
  - [~] 10.2 Create static/team.js for team management functionality
    - Implement loadTeamMembers function (fetch and render team members)
    - Implement loadPendingInvitations function (fetch and render invitations)
    - Implement showInviteModal function (display invitation form)
    - Implement sendInvitation function (POST to /api/team/invite)
    - Implement cancelInvitation function (POST to cancel endpoint)
    - Implement updateMemberRole function (PUT to role endpoint)
    - Implement removeMember function (DELETE to member endpoint)
    - Implement transferOwnership function (POST to transfer endpoint)
    - Add confirmation dialogs for destructive actions
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 10.1, 10.2, 10.3, 10.4, 10.5, 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7_

- [ ] 11. Create invitation acceptance frontend page
  - [~] 11.1 Create templates/accept_invitation.html
    - Create registration form with fields: name, password, confirm password
    - Pre-fill email from invitation (read-only)
    - Display workspace name and role
    - Add submit button
    - Use Tailwind CSS for styling
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

- [ ] 12. Create team member selector component
  - [~] 12.1 Create static/team-selector.js
    - Implement TeamMemberSelector class
    - Implement init method (load members, render dropdown)
    - Implement loadMembers method (fetch from /api/assignments/members)
    - Implement render method (create select element with options)
    - Support includeUnassigned option
    - Emit memberSelected custom event on change
    - Display members as "Name (Role)"
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7_

- [ ] 13. Integrate assignment UI into existing CRM pages
  - [~] 13.1 Add assignment dropdown to contact detail page
    - Add team member selector to templates/contact_detail.html (if exists) or relevant contact template
    - Wire up assignment change event to call /api/assignments/contact/<id>
    - Update UI on successful assignment
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_
  
  - [~] 13.2 Add assignment dropdown to company detail page
    - Add team member selector to company detail template
    - Wire up assignment change event to call /api/assignments/company/<id>
    - Update UI on successful assignment
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_
  
  - [~] 13.3 Add assignment dropdown to deal detail page
    - Add team member selector to deal detail template (use owner_id field)
    - Wire up assignment change event to call /api/assignments/deal/<id>
    - Update UI on successful assignment
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_
  
  - [~] 13.4 Add assignment dropdown to task detail page
    - Add team member selector to task detail template (use assignee_id field)
    - Wire up assignment change event to call /api/assignments/task/<id>
    - Update UI on successful assignment
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_
  
  - [x] 13.5 Add assignment dropdown to conversation sidebar
    - Add team member selector to conversation template (use assigned_to field)
    - Wire up assignment change event to call /api/assignments/conversation/<id>
    - Send Socket.IO notification on assignment
    - Update UI on successful assignment
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_

- [ ] 14. Add assignment filters to CRM list views
  - [x] 14.1 Add assignee filter to contacts list page
    - Add filter dropdown with team members, "Unassigned", and "All" options
    - Update contacts query to filter by assigned_to
    - Persist filter selection in session
    - Default to "All"
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_
  
  - [ ] 14.2 Add assignee filter to companies list page
    - Add filter dropdown with team members, "Unassigned", and "All" options
    - Update companies query to filter by assigned_to
    - Persist filter selection in session
    - Default to "All"
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_
  
  - [~] 14.3 Add assignee filter to deals list page
    - Add filter dropdown with team members, "Unassigned", and "All" options
    - Update deals query to filter by owner_id
    - Persist filter selection in session
    - Default to "All"
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_
  
  - [~] 14.4 Add assignee filter to tasks list page
    - Add filter dropdown with team members, "Unassigned", and "All" options
    - Update tasks query to filter by assignee_id
    - Persist filter selection in session
    - Default to "All"
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

- [ ] 15. Implement activity timeline for team actions
  - [~] 15.1 Update Activity model to record team member actions
    - Ensure Activity records include user_id for all CRM entity changes
    - Add activity types for: assignment_changed, role_changed, member_added, member_removed, ownership_transferred
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_
  
  - [~] 15.2 Update activity display to show team member names
    - Modify activity rendering to display team member name who performed action
    - Display assignment changes with old and new assignee names
    - Display role changes with old and new role values
    - Sort activities by created_at descending
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_

- [ ] 16. Create email templates for notifications
  - [~] 16.1 Create templates/emails/invitation.html
    - Create HTML email template for team invitations
    - Include workspace name, inviter name, role, invitation link, expiration date
    - Add plain text fallback
    - Style with inline CSS
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.7_
  
  - [~] 16.2 Create templates/emails/assignment.html
    - Create HTML email template for assignment notifications
    - Include entity type, entity name, assigner name, direct link to entity
    - Add plain text fallback
    - Style with inline CSS
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_

- [ ] 17. Implement role-based permission checks
  - [~] 17.1 Create utils/permissions.py with permission system
    - Define ROLE_PERMISSIONS dictionary with all role capabilities
    - Implement require_permission decorator
    - Implement check_permission function
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_
  
  - [~] 17.2 Apply permission checks to all team management endpoints
    - Add permission checks to team routes
    - Add permission checks to assignment routes
    - Return 403 Forbidden for unauthorized actions
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 18.1, 18.2, 18.3, 18.4, 18.5, 18.6, 18.7_

- [ ] 18. Handle team member deactivation gracefully
  - [~] 18.1 Update queries to exclude deactivated members from assignment dropdowns
    - Filter by is_active=True in get_assignable_members
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7_
  
  - [~] 18.2 Preserve historical data for deactivated members
    - Keep assigned_to references intact when member is removed
    - Display deactivated member names in activity history
    - Add "Deactivated" badge in admin views
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7_
  
  - [~] 18.3 Prevent login for deactivated members
    - Update login logic in routes/auth.py to check is_active
    - Return appropriate error message for deactivated accounts
    - _Requirements: 9.4, 19.4_

- [ ] 19. Add team management link to navigation
  - [~] 19.1 Add "Team" link to sidebar navigation
    - Add link to /team page in sidebar (after Settings, before Logout)
    - Show only for owner and admin roles
    - Use appropriate icon
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [~] 20. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All database changes require migration: `flask db migrate` and `flask db upgrade`
- All endpoints must use @login_required decorator
- All db.session.commit() must be wrapped in try/except with rollback
- Follow existing patterns: Blueprint routes, service layer, Tailwind CSS
- SMTP configuration is optional - log if not configured
- Maintain workspace_id isolation for all operations
- Preserve backward compatibility with existing single-user workspaces
- Socket.IO notifications use existing gevent-based implementation
