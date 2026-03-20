# Requirements Document

## Introduction

The Team Member Management System enables workspace collaboration in the WhatsApp CRM SaaS application. Currently, each workspace supports only a single user. This feature introduces multi-user workspaces with role-based access control, team member invitations, and assignment capabilities across all CRM entities (contacts, deals, tasks, etc.).

The system maintains the existing multi-tenant architecture with workspace_id isolation while extending the User model and related entities to support team collaboration workflows.

## Glossary

- **Workspace**: A multi-tenant isolation boundary representing a company account
- **Team_Member**: A User associated with a Workspace who has access to workspace data
- **Workspace_Owner**: The User who created the Workspace and has full administrative privileges
- **Invitation_System**: The email-based mechanism for inviting new Team_Members to a Workspace
- **Role**: A permission level assigned to a Team_Member (Owner, Admin, Member, Viewer)
- **Assignment_System**: The mechanism for associating CRM entities with specific Team_Members
- **Auth_System**: The existing session-based authentication mechanism
- **CRM_Entity**: Any of Contact, Company, Deal, Task, Activity, Document, or Conversation
- **Invitation_Token**: A unique, time-limited token used to validate invitation acceptance
- **Team_Management_UI**: The user interface for viewing and managing Team_Members

## Requirements

### Requirement 1: Team Member Data Model

**User Story:** As a developer, I want to extend the User model to support team membership, so that multiple users can belong to a workspace with different roles.

#### Acceptance Criteria

1. THE User SHALL have a role field with values: owner, admin, member, viewer
2. THE User SHALL have an is_active field to enable soft deletion of team members
3. THE User SHALL have a created_at timestamp field
4. THE User SHALL have a last_login timestamp field
5. THE User SHALL maintain the existing workspace_id foreign key relationship
6. THE User SHALL maintain backward compatibility with existing single-user workspaces

### Requirement 2: Invitation System Data Model

**User Story:** As a developer, I want to store invitation records, so that the system can track pending invitations and validate acceptance.

#### Acceptance Criteria

1. THE Invitation_System SHALL store invitation records with workspace_id, inviter_id, invitee_email, role, token, status, expires_at, created_at, and accepted_at fields
2. THE Invitation_Token SHALL be a unique UUID string
3. THE Invitation_System SHALL support status values: pending, accepted, expired, cancelled
4. THE Invitation_System SHALL enforce unique constraint on workspace_id and invitee_email for pending invitations
5. THE Invitation_System SHALL index the token field for fast lookup
6. THE Invitation_System SHALL index the expires_at field for cleanup queries

### Requirement 3: Send Team Member Invitation

**User Story:** As a Workspace_Owner or Admin, I want to invite team members via email, so that I can build my team.

#### Acceptance Criteria

1. WHEN a Workspace_Owner or Admin submits an invitation with email and role, THE Invitation_System SHALL validate the email format
2. WHEN a valid invitation is submitted, THE Invitation_System SHALL create an Invitation record with a unique token and 7-day expiration
3. WHEN an Invitation record is created, THE Invitation_System SHALL send an email containing the invitation link with the token
4. IF an invitation already exists for the email in the workspace, THEN THE Invitation_System SHALL return an error message
5. IF the invitee_email matches an existing Team_Member in the workspace, THEN THE Invitation_System SHALL return an error message
6. THE Invitation_System SHALL set the inviter_id to the current authenticated user
7. THE Invitation_System SHALL set the invitation status to pending

### Requirement 4: Accept Team Member Invitation

**User Story:** As an invited user, I want to accept an invitation via email link, so that I can join the workspace.

#### Acceptance Criteria

1. WHEN a user clicks an invitation link with a valid token, THE Auth_System SHALL display a registration form pre-filled with the invitee email
2. WHEN a user submits the registration form with name and password, THE Auth_System SHALL create a new User record with the specified role
3. WHEN a User record is created, THE Invitation_System SHALL update the invitation status to accepted and set accepted_at timestamp
4. IF the invitation token is invalid or not found, THEN THE Auth_System SHALL display an error message
5. IF the invitation has expired, THEN THE Auth_System SHALL display an expiration message and set status to expired
6. IF the invitation status is not pending, THEN THE Auth_System SHALL display an error message
7. WHEN invitation acceptance succeeds, THE Auth_System SHALL authenticate the new user and redirect to the dashboard

### Requirement 5: Role-Based Access Control

**User Story:** As a system administrator, I want to enforce role-based permissions, so that team members have appropriate access levels.

#### Acceptance Criteria

1. THE Auth_System SHALL grant owner role full access to all workspace features including team management, billing, and workspace deletion
2. THE Auth_System SHALL grant admin role access to all CRM features and team member management except billing and workspace deletion
3. THE Auth_System SHALL grant member role access to view and edit assigned CRM_Entities and create new entities
4. THE Auth_System SHALL grant viewer role read-only access to all CRM_Entities in the workspace
5. WHEN a Team_Member attempts an action, THE Auth_System SHALL verify the action is permitted for their role
6. IF a Team_Member attempts an unauthorized action, THEN THE Auth_System SHALL return a 403 Forbidden response
7. THE Auth_System SHALL allow Team_Members to view only CRM_Entities within their workspace_id

### Requirement 6: Assignment System for CRM Entities

**User Story:** As a Team_Member, I want to assign CRM entities to specific team members, so that responsibilities are clear.

#### Acceptance Criteria

1. THE Assignment_System SHALL add an assigned_to field (foreign key to User) to Contact, Company, Deal, and Task models
2. THE Assignment_System SHALL allow null values for assigned_to to support unassigned entities
3. WHEN a Team_Member assigns a CRM_Entity, THE Assignment_System SHALL validate the assignee belongs to the same workspace
4. WHEN a Team_Member assigns a CRM_Entity, THE Assignment_System SHALL create an Activity record documenting the assignment
5. THE Assignment_System SHALL allow owner and admin roles to assign any CRM_Entity to any Team_Member
6. THE Assignment_System SHALL allow member role to assign only CRM_Entities they own or are assigned to
7. THE Assignment_System SHALL prevent viewer role from making assignments

### Requirement 7: Team Member List View

**User Story:** As a Workspace_Owner or Admin, I want to view all team members, so that I can see who has access to the workspace.

#### Acceptance Criteria

1. WHEN a Workspace_Owner or Admin accesses the team management page, THE Team_Management_UI SHALL display all active Team_Members in the workspace
2. THE Team_Management_UI SHALL display each Team_Member's name, email, role, and last_login timestamp
3. THE Team_Management_UI SHALL display pending invitations with invitee_email, role, and expires_at
4. THE Team_Management_UI SHALL sort Team_Members by role (owner first) then by name
5. THE Team_Management_UI SHALL provide a button to invite new team members
6. IF the current user is not owner or admin, THEN THE Team_Management_UI SHALL return a 403 Forbidden response

### Requirement 8: Update Team Member Role

**User Story:** As a Workspace_Owner, I want to change team member roles, so that I can adjust permissions as needed.

#### Acceptance Criteria

1. WHEN a Workspace_Owner updates a Team_Member role, THE Team_Management_UI SHALL validate the new role is one of: admin, member, viewer
2. WHEN a role update is submitted, THE Team_Management_UI SHALL update the User record with the new role
3. WHEN a role is updated, THE Team_Management_UI SHALL create an Activity record documenting the change
4. THE Team_Management_UI SHALL prevent changing the role of the Workspace_Owner
5. THE Team_Management_UI SHALL prevent admin role from changing roles (only owner can)
6. IF the Team_Member does not belong to the workspace, THEN THE Team_Management_UI SHALL return a 404 Not Found response

### Requirement 9: Remove Team Member

**User Story:** As a Workspace_Owner or Admin, I want to remove team members, so that I can revoke access when needed.

#### Acceptance Criteria

1. WHEN a Workspace_Owner or Admin removes a Team_Member, THE Team_Management_UI SHALL set the User's is_active field to false
2. WHEN a Team_Member is removed, THE Team_Management_UI SHALL set a deleted_at timestamp
3. WHEN a Team_Member is removed, THE Team_Management_UI SHALL create an Activity record documenting the removal
4. WHEN a removed Team_Member attempts to log in, THE Auth_System SHALL deny access with an appropriate error message
5. THE Team_Management_UI SHALL prevent removing the Workspace_Owner
6. THE Team_Management_UI SHALL allow admin role to remove only member and viewer roles
7. THE Team_Management_UI SHALL allow owner role to remove any Team_Member except themselves

### Requirement 10: Cancel Pending Invitation

**User Story:** As a Workspace_Owner or Admin, I want to cancel pending invitations, so that I can revoke invitations sent in error.

#### Acceptance Criteria

1. WHEN a Workspace_Owner or Admin cancels an invitation, THE Invitation_System SHALL update the invitation status to cancelled
2. WHEN an invitation is cancelled, THE Invitation_System SHALL create an Activity record documenting the cancellation
3. IF a user attempts to accept a cancelled invitation, THEN THE Auth_System SHALL display an error message
4. THE Invitation_System SHALL allow cancelling only pending invitations
5. THE Invitation_System SHALL prevent cancelling invitations from other workspaces

### Requirement 11: Assignment Filter in CRM Views

**User Story:** As a Team_Member, I want to filter CRM entities by assignee, so that I can focus on my responsibilities.

#### Acceptance Criteria

1. WHEN a Team_Member views Contacts, Companies, Deals, or Tasks, THE Team_Management_UI SHALL provide an assignee filter dropdown
2. THE Team_Management_UI SHALL populate the assignee dropdown with all active Team_Members in the workspace plus "Unassigned" and "All" options
3. WHEN a Team_Member selects an assignee filter, THE Team_Management_UI SHALL display only CRM_Entities assigned to that Team_Member
4. WHEN a Team_Member selects "Unassigned", THE Team_Management_UI SHALL display only CRM_Entities with null assigned_to
5. WHEN a Team_Member selects "All", THE Team_Management_UI SHALL display all CRM_Entities in the workspace
6. THE Team_Management_UI SHALL persist the filter selection in the user's session
7. THE Team_Management_UI SHALL default to "All" when no filter is selected

### Requirement 12: Conversation Assignment

**User Story:** As a Team_Member, I want to assign conversations to team members, so that customer inquiries are handled by the right person.

#### Acceptance Criteria

1. THE Assignment_System SHALL use the existing assigned_to field in the Conversation model
2. WHEN a Team_Member assigns a Conversation, THE Assignment_System SHALL validate the assignee belongs to the same workspace
3. WHEN a Conversation is assigned, THE Assignment_System SHALL create a Message record in the conversation documenting the assignment
4. WHEN a Conversation is assigned, THE Assignment_System SHALL send a real-time notification via Socket.IO to the assignee
5. THE Assignment_System SHALL allow owner and admin roles to assign any Conversation
6. THE Assignment_System SHALL allow member role to assign Conversations they are assigned to or unassigned Conversations
7. THE Assignment_System SHALL prevent viewer role from assigning Conversations

### Requirement 13: Team Member Activity Timeline

**User Story:** As a Team_Member, I want to see team member actions in activity timelines, so that I can track collaboration history.

#### Acceptance Criteria

1. WHEN a Team_Member creates, updates, or deletes a CRM_Entity, THE Activity SHALL record the user_id of the Team_Member
2. WHEN displaying an Activity, THE Team_Management_UI SHALL show the Team_Member's name who performed the action
3. THE Team_Management_UI SHALL display assignment changes in the Activity timeline with old and new assignee names
4. THE Team_Management_UI SHALL display role changes in the Activity timeline with old and new role values
5. THE Team_Management_UI SHALL display team member additions and removals in the Activity timeline
6. THE Team_Management_UI SHALL sort activities by created_at in descending order

### Requirement 14: Email Notification for Assignments

**User Story:** As a Team_Member, I want to receive email notifications when assigned to entities, so that I am aware of new responsibilities.

#### Acceptance Criteria

1. WHEN a CRM_Entity is assigned to a Team_Member, THE Assignment_System SHALL send an email notification to the assignee's email address
2. THE Assignment_System SHALL include the entity type, entity name, and assigner name in the email
3. THE Assignment_System SHALL include a direct link to the entity in the email
4. WHERE SMTP configuration is available, THE Assignment_System SHALL send emails via the configured SMTP server
5. IF SMTP is not configured, THEN THE Assignment_System SHALL log the notification and skip email sending
6. THE Assignment_System SHALL not send email notifications to the Team_Member who performed the assignment

### Requirement 15: Workspace Owner Transfer

**User Story:** As a Workspace_Owner, I want to transfer ownership to another team member, so that I can delegate full control when needed.

#### Acceptance Criteria

1. WHEN a Workspace_Owner initiates ownership transfer, THE Team_Management_UI SHALL display a confirmation dialog with the new owner's name
2. WHEN ownership transfer is confirmed, THE Team_Management_UI SHALL update the current owner's role to admin
3. WHEN ownership transfer is confirmed, THE Team_Management_UI SHALL update the new owner's role to owner
4. WHEN ownership transfer is confirmed, THE Team_Management_UI SHALL create an Activity record documenting the transfer
5. THE Team_Management_UI SHALL allow transferring ownership only to active Team_Members with admin role
6. THE Team_Management_UI SHALL require the current Workspace_Owner to re-authenticate before transfer
7. IF the transfer fails, THEN THE Team_Management_UI SHALL rollback all changes and display an error message

### Requirement 16: Team Member Selector Component

**User Story:** As a developer, I want a reusable team member selector component, so that assignment UI is consistent across all CRM views.

#### Acceptance Criteria

1. THE Team_Management_UI SHALL provide a JavaScript component that renders a team member dropdown
2. THE Team_Management_UI SHALL populate the dropdown with active Team_Members in the current workspace
3. THE Team_Management_UI SHALL display each Team_Member as "Name (Role)" in the dropdown
4. THE Team_Management_UI SHALL support an optional "Unassigned" option in the dropdown
5. THE Team_Management_UI SHALL emit a custom event when a Team_Member is selected
6. THE Team_Management_UI SHALL accept an initial selected value parameter
7. THE Team_Management_UI SHALL disable the dropdown when the current user lacks assignment permissions

### Requirement 17: Migration from Single-User to Multi-User

**User Story:** As a system administrator, I want existing workspaces to migrate smoothly, so that current users are not disrupted.

#### Acceptance Criteria

1. WHEN the migration runs, THE Team_Management_UI SHALL set all existing Users to owner role
2. WHEN the migration runs, THE Team_Management_UI SHALL set all existing Users to is_active true
3. WHEN the migration runs, THE Team_Management_UI SHALL set created_at to the User's existing creation timestamp or current time
4. THE Team_Management_UI SHALL preserve all existing User data including workspace_id, name, email, and password_hash
5. THE Team_Management_UI SHALL add assigned_to columns to Contact, Company, Deal, and Task tables with null default
6. THE Team_Management_UI SHALL create indexes on all new assigned_to foreign key columns
7. THE Team_Management_UI SHALL complete the migration without data loss or downtime

### Requirement 18: API Endpoint Security

**User Story:** As a security engineer, I want all team management endpoints to be authenticated and authorized, so that unauthorized access is prevented.

#### Acceptance Criteria

1. THE Team_Management_UI SHALL apply @login_required decorator to all team management endpoints
2. WHEN a Team_Management_UI endpoint is accessed, THE Auth_System SHALL verify the user is authenticated
3. WHEN a Team_Management_UI endpoint is accessed, THE Auth_System SHALL verify the user belongs to the target workspace
4. WHEN a Team_Management_UI endpoint modifies data, THE Auth_System SHALL verify the user has the required role
5. IF authentication fails, THEN THE Auth_System SHALL return a 401 Unauthorized response
6. IF authorization fails, THEN THE Auth_System SHALL return a 403 Forbidden response
7. THE Team_Management_UI SHALL wrap all database commits in try-except blocks with rollback on error

### Requirement 19: Team Member Deactivation Cascade

**User Story:** As a system administrator, I want to handle team member removal gracefully, so that data integrity is maintained.

#### Acceptance Criteria

1. WHEN a Team_Member is removed, THE Assignment_System SHALL preserve all existing assignments (not set to null)
2. WHEN a Team_Member is removed, THE Team_Management_UI SHALL display the removed member's name in historical Activity records
3. WHEN a Team_Member is removed, THE Team_Management_UI SHALL prevent the removed member from appearing in assignment dropdowns
4. WHEN a Team_Member is removed, THE Team_Management_UI SHALL prevent the removed member from logging in
5. THE Assignment_System SHALL allow viewing CRM_Entities assigned to removed Team_Members
6. THE Assignment_System SHALL allow reassigning CRM_Entities from removed Team_Members to active Team_Members
7. THE Team_Management_UI SHALL display removed Team_Members with a "Deactivated" badge in admin views

### Requirement 20: Invitation Email Template

**User Story:** As a Workspace_Owner, I want invitation emails to be professional and clear, so that invitees understand the invitation.

#### Acceptance Criteria

1. THE Invitation_System SHALL use an HTML email template for invitations
2. THE Invitation_System SHALL include the workspace company_name in the email subject and body
3. THE Invitation_System SHALL include the inviter's name in the email body
4. THE Invitation_System SHALL include the assigned role in the email body
5. THE Invitation_System SHALL include a prominent "Accept Invitation" button with the invitation link
6. THE Invitation_System SHALL include the expiration date in the email body
7. THE Invitation_System SHALL include a plain text fallback for email clients that don't support HTML
