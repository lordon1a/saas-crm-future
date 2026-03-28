# Design Document: Daily Action Dashboard

## Overview

The Daily Action Dashboard is a prioritized action list widget that surfaces high-value tasks for sales representatives. The system combines existing lead scoring, activity tracking, deal management, and task data to generate a ranked list of recommended actions. This feature aims to reduce decision fatigue, prevent lead churn, and increase daily active usage by providing clear, actionable next steps.

### Key Design Principles

1. **Non-Intrusive**: Widget integrates into existing dashboard without disrupting current workflows
2. **Performance-First**: Asynchronous calculation with caching to maintain sub-500ms response times
3. **Multi-Tenant Isolation**: All queries filtered by workspace_id with team member assignment support
4. **Service Layer Pattern**: Business logic in dedicated service, routes handle HTTP only
5. **Mobile-Responsive**: Tailwind CSS with mobile-first approach

### Technology Stack

- **Backend**: Flask + SQLAlchemy + gevent (existing stack)
- **Frontend**: Vanilla JavaScript + Tailwind CSS (no new frameworks)
- **Caching**: In-memory cache with 5-minute TTL per user
- **Database**: PostgreSQL with optimized indexes on scoring columns

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Dashboard Page                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │         Action Widget (HTML Component)                │  │
│  │  - Top 10 prioritized actions                         │  │
│  │  - Auto-refresh every 5 minutes                       │  │
│  │  - Click handlers for dismiss/complete                │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              routes/dashboard.py (New)                      │
│  - GET /api/dashboard/actions                               │
│  - POST /api/dashboard/actions/<id>/dismiss                 │
│  - POST /api/dashboard/actions/<id>/complete                │
│  - GET /api/dashboard/settings                              │
│  - PUT /api/dashboard/settings                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│         services/action_dashboard_service.py (New)          │
│  - calculate_action_items()                                 │
│  - prioritize_stale_contacts()                              │
│  - prioritize_deals()                                       │
│  - prioritize_overdue_tasks()                               │
│  - rank_and_merge()                                         │
│  - dismiss_action()                                         │
│  - complete_action()                                        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  models_crm.py (Extended)                   │
│  - ActionItem (New Model)                                   │
│  - DismissedAction (New Model)                              │
│  - DashboardSettings (New Model)                            │
│  - WidgetEngagement (New Model)                             │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **User loads dashboard** → Frontend requests `/api/dashboard/actions`
2. **Route handler** → Calls `ActionDashboardService.calculate_action_items()`
3. **Service layer** → Queries contacts, deals, tasks with workspace_id filter
4. **Priority engine** → Scores and ranks candidates, applies thresholds
5. **Cache layer** → Stores result for 5 minutes per user
6. **Response** → Returns top 10 actions as JSON
7. **Frontend** → Renders widget, sets 5-minute auto-refresh timer

### Background Processing

```python
# Asynchronous calculation using gevent
def calculate_action_items_async(workspace_id, user_id):
    """
    Spawns gevent greenlet for calculation.
    Returns cached result immediately if available.
    """
    cache_key = f"actions:{workspace_id}:{user_id}"
    cached = cache.get(cache_key)
    
    if cached:
        return cached
    
    # Spawn async calculation
    gevent.spawn(
        _calculate_and_cache,
        workspace_id,
        user_id,
        cache_key
    )
    
    # Return empty list on first load
    return []
```

## Components and Interfaces

### 1. Database Models

#### ActionItem (Ephemeral - Not Persisted)

```python
@dataclass
class ActionItem:
    """
    Ephemeral action item (not a DB model).
    Generated on-demand by priority engine.
    """
    id: str  # Format: "{type}:{entity_id}"
    action_type: str  # 'contact_followup', 'deal_update', 'task_overdue'
    priority: str  # 'urgent', 'high', 'medium'
    priority_score: int  # 0-100 for sorting
    entity_type: str  # 'contact', 'deal', 'task'
    entity_id: int
    entity_name: str
    recommended_action: str  # "Follow up with John Doe"
    context: dict  # Additional metadata
    last_activity_at: datetime
    created_at: datetime
```

#### DismissedAction (New Model)

```python
class DismissedAction(db.Model):
    """
    Tracks dismissed action items to hide them for 24 hours.
    """
    __tablename__ = 'dismissed_actions'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), 
                            nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), 
                       nullable=False, index=True)
    action_id = db.Column(db.String(100), nullable=False, index=True)
    dismissed_at = db.Column(db.DateTime, default=datetime.utcnow, 
                            nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    
    __table_args__ = (
        db.Index('idx_dismissed_workspace_user', 'workspace_id', 'user_id'),
        db.Index('idx_dismissed_expires', 'expires_at'),
    )
```

#### DashboardSettings (New Model)

```python
class DashboardSettings(db.Model):
    """
    Workspace-level configuration for action priority thresholds.
    """
    __tablename__ = 'dashboard_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), 
                            nullable=False, unique=True, index=True)
    
    # Lead score thresholds
    high_score_threshold = db.Column(db.Integer, default=70, nullable=False)
    medium_score_threshold = db.Column(db.Integer, default=50, nullable=False)
    
    # Staleness thresholds (days)
    high_score_staleness_days = db.Column(db.Integer, default=3, nullable=False)
    medium_score_staleness_days = db.Column(db.Integer, default=7, nullable=False)
    
    # Deal thresholds
    deal_close_warning_days = db.Column(db.Integer, default=7, nullable=False)
    deal_stage_stale_days = db.Column(db.Integer, default=14, nullable=False)
    deal_negotiation_stale_days = db.Column(db.Integer, default=5, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, 
                          onupdate=datetime.utcnow)
```

#### WidgetEngagement (New Model)

```python
class WidgetEngagement(db.Model):
    """
    Tracks user interactions with the action widget for analytics.
    """
    __tablename__ = 'widget_engagements'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), 
                            nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), 
                       nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    # 'widget_viewed', 'action_clicked', 'action_dismissed', 'action_completed'
    action_id = db.Column(db.String(100), nullable=True, index=True)
    action_type = db.Column(db.String(50), nullable=True)
    priority = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, 
                          nullable=False, index=True)
    
    __table_args__ = (
        db.Index('idx_engagement_workspace_user', 'workspace_id', 'user_id'),
        db.Index('idx_engagement_event_type', 'event_type'),
        db.Index('idx_engagement_created', 'created_at'),
    )
```

### 2. Service Layer

#### ActionDashboardService

```python
class ActionDashboardService:
    """
    Business logic for daily action dashboard.
    Calculates, ranks, and manages action items.
    """
    
    @staticmethod
    def calculate_action_items(workspace_id: int, user_id: int, 
                               limit: int = 10) -> List[ActionItem]:
        """
        Calculate and return prioritized action items for a user.
        
        Algorithm:
        1. Get workspace settings (or defaults)
        2. Query stale high-score contacts
        3. Query deals needing attention
        4. Query overdue/due-today tasks
        5. Filter out dismissed actions
        6. Score and rank all candidates
        7. Return top N items
        
        Returns:
            List of ActionItem objects, sorted by priority_score desc
        """
        
    @staticmethod
    def prioritize_stale_contacts(workspace_id: int, user_id: int, 
                                  settings: DashboardSettings) -> List[ActionItem]:
        """
        Find contacts with high lead scores and no recent activity.
        
        Query:
        - lead_score >= high_score_threshold AND 
          last_activity_at < (now - high_score_staleness_days)
          → Priority: High, Score: 90
        
        - lead_score >= medium_score_threshold AND 
          last_activity_at < (now - medium_score_staleness_days)
          → Priority: Medium, Score: 70
        """
        
    @staticmethod
    def prioritize_deals(workspace_id: int, user_id: int, 
                        settings: DashboardSettings) -> List[ActionItem]:
        """
        Find deals requiring attention based on close date, stage, activity.
        
        Query:
        - expected_close_date within deal_close_warning_days AND 
          status = 'open'
          → Priority: High, Score: 95
        
        - stage_entered_at > deal_stage_stale_days
          → Priority: Medium, Score: 75
        
        - stage in ('Negotiation', 'Proposal') AND 
          last_activity_at < (now - deal_negotiation_stale_days)
          → Priority: High, Score: 85
        """
        
    @staticmethod
    def prioritize_overdue_tasks(workspace_id: int, user_id: int) -> List[ActionItem]:
        """
        Find overdue and due-today tasks.
        
        Query:
        - due_date < today AND status != 'completed'
          → Priority: Urgent, Score: 100
        
        - due_date = today AND status != 'completed'
          → Priority: High, Score: 90
        """
        
    @staticmethod
    def rank_and_merge(candidates: List[ActionItem], 
                      dismissed_ids: Set[str]) -> List[ActionItem]:
        """
        Filter dismissed items, sort by priority_score, return top N.
        """
        
    @staticmethod
    def dismiss_action(workspace_id: int, user_id: int, 
                      action_id: str) -> bool:
        """
        Mark action as dismissed for 24 hours.
        Creates DismissedAction record with expires_at = now + 24h.
        """
        
    @staticmethod
    def complete_action(workspace_id: int, user_id: int, 
                       action_id: str) -> bool:
        """
        Complete the underlying task if action_type is 'task_overdue'.
        For other types, just dismiss the action.
        """
        
    @staticmethod
    def track_engagement(workspace_id: int, user_id: int, 
                        event_type: str, action_id: str = None, 
                        action_type: str = None, priority: str = None):
        """
        Log widget engagement event for analytics.
        """
        
    @staticmethod
    def get_or_create_settings(workspace_id: int) -> DashboardSettings:
        """
        Get workspace settings or create with defaults.
        """
        
    @staticmethod
    def update_settings(workspace_id: int, data: dict) -> DashboardSettings:
        """
        Update workspace dashboard settings.
        """
```

### 3. API Routes

#### routes/dashboard.py (New File)

```python
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from services.action_dashboard_service import ActionDashboardService
from models import db

bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')

@bp.route('/actions', methods=['GET'])
@login_required
def get_actions():
    """
    Get prioritized action items for current user.
    
    Response:
    {
        "actions": [
            {
                "id": "contact:123",
                "action_type": "contact_followup",
                "priority": "high",
                "priority_score": 90,
                "entity_type": "contact",
                "entity_id": 123,
                "entity_name": "John Doe",
                "recommended_action": "Follow up with John Doe",
                "context": {
                    "lead_score": 85,
                    "days_since_activity": 5,
                    "company_name": "Acme Corp"
                },
                "last_activity_at": "2024-01-15T10:30:00Z"
            }
        ],
        "count": 10
    }
    """
    
@bp.route('/actions/<action_id>/dismiss', methods=['POST'])
@login_required
def dismiss_action(action_id):
    """
    Dismiss an action item for 24 hours.
    """
    
@bp.route('/actions/<action_id>/complete', methods=['POST'])
@login_required
def complete_action(action_id):
    """
    Complete an action item (marks task as completed if applicable).
    """
    
@bp.route('/settings', methods=['GET'])
@login_required
def get_settings():
    """
    Get dashboard settings for current workspace.
    """
    
@bp.route('/settings', methods=['PUT'])
@login_required
def update_settings():
    """
    Update dashboard settings (admin only).
    """
```

### 4. Frontend Component

#### templates/dashboard.html (Modified)

```html
<!-- Add widget to existing dashboard -->
<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
    <!-- Existing dashboard content -->
    
    <!-- New Action Widget -->
    <div class="lg:col-span-1">
        <div id="action-widget" class="bg-white rounded-lg shadow p-6">
            <h3 class="text-lg font-semibold mb-4">Today's Actions</h3>
            <div id="action-list" class="space-y-3">
                <!-- Populated by JavaScript -->
            </div>
        </div>
    </div>
</div>
```

#### static/action-widget.js (New File)

```javascript
class ActionWidget {
    constructor() {
        this.refreshInterval = 5 * 60 * 1000; // 5 minutes
        this.init();
    }
    
    async init() {
        await this.loadActions();
        this.startAutoRefresh();
        this.trackView();
    }
    
    async loadActions() {
        const response = await fetch('/api/dashboard/actions');
        const data = await response.json();
        this.renderActions(data.actions);
    }
    
    renderActions(actions) {
        const container = document.getElementById('action-list');
        
        if (actions.length === 0) {
            container.innerHTML = `
                <p class="text-gray-500 text-center py-4">
                    No actions for today - great job!
                </p>
            `;
            return;
        }
        
        container.innerHTML = actions.map(action => `
            <div class="action-item border-l-4 ${this.getBorderColor(action.priority)} 
                        bg-gray-50 p-3 rounded">
                <div class="flex justify-between items-start">
                    <div class="flex-1">
                        <p class="font-medium text-sm">${action.recommended_action}</p>
                        <p class="text-xs text-gray-500 mt-1">
                            ${this.formatContext(action)}
                        </p>
                    </div>
                    <div class="flex space-x-2 ml-2">
                        ${this.renderActionButtons(action)}
                    </div>
                </div>
            </div>
        `).join('');
        
        this.attachEventListeners();
    }
    
    getBorderColor(priority) {
        const colors = {
            'urgent': 'border-red-500',
            'high': 'border-orange-500',
            'medium': 'border-yellow-500'
        };
        return colors[priority] || 'border-gray-300';
    }
    
    formatContext(action) {
        const { context, last_activity_at } = action;
        const parts = [];
        
        if (context.lead_score) {
            parts.push(`Score: ${context.lead_score}`);
        }
        if (context.days_since_activity) {
            parts.push(`${context.days_since_activity} days ago`);
        }
        if (context.company_name) {
            parts.push(context.company_name);
        }
        
        return parts.join(' • ');
    }
    
    renderActionButtons(action) {
        let buttons = `
            <button class="action-dismiss text-gray-400 hover:text-gray-600"
                    data-action-id="${action.id}">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M6 18L18 6M6 6l12 12"/>
                </svg>
            </button>
        `;
        
        if (action.action_type === 'task_overdue') {
            buttons += `
                <button class="action-complete text-green-500 hover:text-green-700"
                        data-action-id="${action.id}">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                              d="M5 13l4 4L19 7"/>
                    </svg>
                </button>
            `;
        }
        
        return buttons;
    }
    
    attachEventListeners() {
        document.querySelectorAll('.action-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (!e.target.closest('button')) {
                    this.handleActionClick(e.currentTarget);
                }
            });
        });
        
        document.querySelectorAll('.action-dismiss').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.dismissAction(btn.dataset.actionId);
            });
        });
        
        document.querySelectorAll('.action-complete').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.completeAction(btn.dataset.actionId);
            });
        });
    }
    
    async dismissAction(actionId) {
        await fetch(`/api/dashboard/actions/${actionId}/dismiss`, {
            method: 'POST'
        });
        this.loadActions();
    }
    
    async completeAction(actionId) {
        await fetch(`/api/dashboard/actions/${actionId}/complete`, {
            method: 'POST'
        });
        this.loadActions();
    }
    
    handleActionClick(element) {
        // Navigate to entity detail page
        const actionId = element.querySelector('[data-action-id]').dataset.actionId;
        const [entityType, entityId] = actionId.split(':');
        
        const routes = {
            'contact': `/contacts/${entityId}`,
            'deal': `/deals/${entityId}`,
            'task': `/tasks/${entityId}`
        };
        
        if (routes[entityType]) {
            window.location.href = routes[entityType];
        }
    }
    
    startAutoRefresh() {
        setInterval(() => this.loadActions(), this.refreshInterval);
    }
    
    async trackView() {
        await fetch('/api/dashboard/engagement', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ event_type: 'widget_viewed' })
        });
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('action-widget')) {
        new ActionWidget();
    }
});
```

## Data Models

### Database Schema

```sql
-- DismissedAction
CREATE TABLE dismissed_actions (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    action_id VARCHAR(100) NOT NULL,
    dismissed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    
    INDEX idx_dismissed_workspace_user (workspace_id, user_id),
    INDEX idx_dismissed_expires (expires_at)
);

-- DashboardSettings
CREATE TABLE dashboard_settings (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL UNIQUE REFERENCES workspaces(id),
    high_score_threshold INTEGER NOT NULL DEFAULT 70,
    medium_score_threshold INTEGER NOT NULL DEFAULT 50,
    high_score_staleness_days INTEGER NOT NULL DEFAULT 3,
    medium_score_staleness_days INTEGER NOT NULL DEFAULT 7,
    deal_close_warning_days INTEGER NOT NULL DEFAULT 7,
    deal_stage_stale_days INTEGER NOT NULL DEFAULT 14,
    deal_negotiation_stale_days INTEGER NOT NULL DEFAULT 5,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- WidgetEngagement
CREATE TABLE widget_engagements (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    event_type VARCHAR(50) NOT NULL,
    action_id VARCHAR(100),
    action_type VARCHAR(50),
    priority VARCHAR(20),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    INDEX idx_engagement_workspace_user (workspace_id, user_id),
    INDEX idx_engagement_event_type (event_type),
    INDEX idx_engagement_created (created_at)
);
```

### Required Indexes on Existing Tables

```sql
-- Optimize contact queries for staleness
CREATE INDEX IF NOT EXISTS idx_contact_lead_score_activity 
    ON contacts(workspace_id, lead_score, last_activity_at) 
    WHERE is_deleted = FALSE;

-- Optimize deal queries for close date and stage staleness
CREATE INDEX IF NOT EXISTS idx_deal_close_date 
    ON deals(workspace_id, expected_close_date, status) 
    WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_deal_stage_entered 
    ON deals(workspace_id, stage_entered_at, status) 
    WHERE is_deleted = FALSE;

-- Optimize task queries for due date
CREATE INDEX IF NOT EXISTS idx_task_due_date 
    ON tasks(workspace_id, due_date, status);
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

