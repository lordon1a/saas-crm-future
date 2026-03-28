# Requirements Document

## Introduction

The Daily Action Dashboard is a prioritized action list widget that helps sales representatives identify their most important tasks each day. By combining existing lead scoring data with activity tracking, the system surfaces high-value contacts and deals that need immediate attention, reducing churn and increasing daily active usage.

## Glossary

- **Action_Widget**: The dashboard component that displays the prioritized daily action list
- **Lead_Score**: Numerical value (0-100) indicating contact engagement and conversion likelihood
- **Activity_Tracker**: System component that monitors contact interactions and timestamps
- **Priority_Engine**: Algorithm that combines lead score and activity data to rank actions
- **Action_Item**: A recommended task for a sales representative (e.g., follow up with contact, update deal)
- **Workspace**: Multi-tenant isolation unit identified by workspace_id
- **Sales_Rep**: User with sales role who uses the CRM daily
- **Stale_Contact**: Contact with no activity for a configurable time period
- **Hot_Lead**: Contact with lead score above a configurable threshold

## Requirements

### Requirement 1: Display Daily Action List

**User Story:** As a sales representative, I want to see a prioritized list of actions when I open the dashboard, so that I know exactly what to work on first.

#### Acceptance Criteria

1. WHEN a Sales_Rep logs in, THE Action_Widget SHALL display on the main dashboard page
2. THE Action_Widget SHALL show the top 10 highest priority Action_Items for the current Workspace
3. WHEN the Action_Widget is empty, THE Action_Widget SHALL display a message "No actions for today - great job!"
4. THE Action_Widget SHALL refresh automatically every 5 minutes while the dashboard is open
5. FOR ALL Action_Items displayed, THE Action_Widget SHALL show contact name, action type, priority score, and last activity timestamp

### Requirement 2: Prioritize High-Score Stale Contacts

**User Story:** As a sales representative, I want to be notified about high-scoring contacts I haven't contacted recently, so that I don't lose hot leads.

#### Acceptance Criteria

1. WHEN a contact has Lead_Score above 70 AND no activity for 3 days, THE Priority_Engine SHALL create an Action_Item with priority "High"
2. WHEN a contact has Lead_Score above 50 AND no activity for 7 days, THE Priority_Engine SHALL create an Action_Item with priority "Medium"
3. THE Priority_Engine SHALL calculate staleness based on the most recent activity timestamp in Activity_Tracker
4. WHERE a contact has multiple qualifying conditions, THE Priority_Engine SHALL use the highest priority level
5. THE Action_Item SHALL include the recommended action "Follow up with [contact_name]"

### Requirement 3: Surface Deals Requiring Attention

**User Story:** As a sales representative, I want to see deals that need updates or are approaching deadlines, so that I can close more deals on time.

#### Acceptance Criteria

1. WHEN a deal has expected_close_date within 7 days AND stage is not "Won" or "Lost", THE Priority_Engine SHALL create an Action_Item with priority "High"
2. WHEN a deal has been in the same pipeline stage for more than 14 days, THE Priority_Engine SHALL create an Action_Item with priority "Medium"
3. WHEN a deal has no activity for 5 days AND stage is "Negotiation" or "Proposal", THE Priority_Engine SHALL create an Action_Item with priority "High"
4. THE Action_Item SHALL include the deal name, current stage, and days since last activity
5. THE Action_Item SHALL include the recommended action "Update deal: [deal_name]"

### Requirement 4: Highlight Overdue Tasks

**User Story:** As a sales representative, I want to see my overdue tasks prominently, so that I can catch up on missed commitments.

#### Acceptance Criteria

1. WHEN a task has due_date before today AND status is not "Completed", THE Priority_Engine SHALL create an Action_Item with priority "Urgent"
2. WHEN a task has due_date equal to today AND status is not "Completed", THE Priority_Engine SHALL create an Action_Item with priority "High"
3. THE Action_Item SHALL display the task title, associated contact or deal, and days overdue
4. THE Priority_Engine SHALL sort Urgent priority items before all other priorities
5. THE Action_Item SHALL include a direct link to complete or reschedule the task

### Requirement 5: Enable Action Item Interaction

**User Story:** As a sales representative, I want to take action directly from the widget, so that I can work efficiently without navigating away.

#### Acceptance Criteria

1. WHEN a Sales_Rep clicks an Action_Item, THE Action_Widget SHALL navigate to the relevant contact, deal, or task detail page
2. WHEN a Sales_Rep clicks "Dismiss" on an Action_Item, THE Action_Widget SHALL remove it from the list for 24 hours
3. WHEN a Sales_Rep clicks "Complete" on a task Action_Item, THE Action_Widget SHALL mark the task as completed and remove it from the list
4. THE Action_Widget SHALL persist dismissed items in the database with workspace_id and user_id
5. WHEN an Action_Item is completed through any interface, THE Action_Widget SHALL remove it from the list within 5 minutes

### Requirement 6: Respect Multi-Tenant Isolation

**User Story:** As a workspace administrator, I want action items to be isolated per workspace, so that users only see data from their own workspace.

#### Acceptance Criteria

1. THE Priority_Engine SHALL filter all contacts, deals, and tasks by the current workspace_id
2. THE Action_Widget SHALL display only Action_Items belonging to the authenticated user's workspace_id
3. WHEN calculating priorities, THE Priority_Engine SHALL consider only data within the same workspace_id
4. THE Action_Widget SHALL prevent access to Action_Items from other workspaces through API validation
5. WHERE team member assignments exist, THE Action_Widget SHALL show only items assigned to the current Sales_Rep or unassigned items

### Requirement 7: Configure Priority Thresholds

**User Story:** As a workspace administrator, I want to configure the thresholds for action priorities, so that I can customize the system to my team's workflow.

#### Acceptance Criteria

1. WHERE workspace settings exist, THE Priority_Engine SHALL use workspace-specific thresholds for lead score cutoffs
2. WHERE workspace settings exist, THE Priority_Engine SHALL use workspace-specific thresholds for staleness days
3. WHEN workspace settings are not configured, THE Priority_Engine SHALL use default values (lead_score: 70/50, staleness: 3/7 days)
4. THE Settings page SHALL provide input fields for administrators to modify these thresholds
5. WHEN threshold settings are updated, THE Priority_Engine SHALL apply new values within 5 minutes

### Requirement 8: Track Widget Engagement

**User Story:** As a product manager, I want to track how users interact with the action widget, so that I can measure feature adoption and value.

#### Acceptance Criteria

1. WHEN a Sales_Rep views the Action_Widget, THE Activity_Tracker SHALL log a "widget_viewed" event with timestamp and user_id
2. WHEN a Sales_Rep clicks an Action_Item, THE Activity_Tracker SHALL log a "action_clicked" event with action type and priority
3. WHEN a Sales_Rep dismisses an Action_Item, THE Activity_Tracker SHALL log a "action_dismissed" event
4. WHEN a Sales_Rep completes an Action_Item, THE Activity_Tracker SHALL log a "action_completed" event
5. THE Activity_Tracker SHALL store all widget events with workspace_id for analytics queries

### Requirement 9: Optimize Performance for Large Datasets

**User Story:** As a system administrator, I want the action widget to load quickly even with thousands of contacts, so that user experience remains smooth.

#### Acceptance Criteria

1. THE Priority_Engine SHALL calculate Action_Items asynchronously in a background process
2. THE Priority_Engine SHALL cache calculated Action_Items for 5 minutes per user
3. WHEN the Action_Widget requests data, THE system SHALL respond within 500ms for workspaces with up to 10,000 contacts
4. THE Priority_Engine SHALL use database indexes on workspace_id, lead_score, last_activity_date, and due_date columns
5. THE Priority_Engine SHALL limit calculations to the top 50 candidates per category before final ranking

### Requirement 10: Provide Mobile-Responsive Display

**User Story:** As a sales representative, I want to view my daily actions on mobile devices, so that I can work from anywhere.

#### Acceptance Criteria

1. WHEN the dashboard is viewed on a screen width below 768px, THE Action_Widget SHALL display in a single-column layout
2. THE Action_Widget SHALL maintain full functionality on touch devices
3. WHEN viewed on mobile, THE Action_Widget SHALL show abbreviated action descriptions with expand option
4. THE Action_Widget SHALL use responsive Tailwind CSS classes for all layout elements
5. THE Action_Widget SHALL load within 2 seconds on 3G mobile connections

