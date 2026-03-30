# Workflow Automation System - Implementation Plan

## Overview

Implementing a Pipedrive-level, production-ready Workflow Automation system where users create "IF X happens → THEN do Y" rules. The CRM runs these rules in the background with no manual intervention.

### Architecture Decisions

1. **Parallel System**: New `workflow_automations` table coexists with existing `automation_rules`
2. **Future Integration**: Old AutoReply/Assignment systems will become "preset templates" on top of new Workflow engine (architectural preparation, not implementation)
3. **Email**: Use existing `services/email_hub_service.py` SMTP infrastructure

---

## Phase 1: Database Models (Week 1 - Foundation)

### 1.1 Create Migration Script
**File:** `migrations/add_workflow_automation_tables.py`

```python
# Tables to create:
# - workflow_automations
# - workflow_conditions  
# - workflow_actions
# - workflow_executions
# - workflow_execution_queue
```

### 1.2 Database Models
**File:** `models_crm.py` additions

```python
class WorkflowAutomation(db.Model):
    """Main workflow rule"""
    # id, workspace_id, name, description
    # is_active (bool, default True)
    # trigger_type (str)
    # trigger_config (JSON)
    # condition_logic (str) — "AND" | "OR"
    # created_by, created_at, updated_at
    # run_count (int), last_run_at

class WorkflowCondition(db.Model):
    """Condition for workflow execution"""
    # id, workflow_id, workspace_id
    # field_name, operator, value
    # order_index

class WorkflowAction(db.Model):
    """Action to execute"""
    # id, workflow_id, workspace_id
    # action_type, action_config (JSON)
    # delay_minutes, order_index

class WorkflowExecution(db.Model):
    """Execution log"""
    # id, workflow_id, workspace_id
    # entity_type, entity_id
    # status (pending/running/completed/failed/skipped)
    # triggered_by, started_at, completed_at
    # error_message, actions_executed (JSON)

class WorkflowExecutionQueue(db.Model):
    """Delayed action queue"""
    # id, workflow_id, workspace_id
    # entity_type, entity_id
    # action_id, scheduled_at, executed_at
    # status (pending/executed/cancelled)
```

### 1.3 Indexes
```sql
idx_workflow_workspace_active ON workflow_automations(workspace_id, is_active)
idx_workflow_condition_workflow ON workflow_conditions(workflow_id)
idx_workflow_action_workflow ON workflow_actions(workflow_id)
idx_execution_workflow ON workflow_executions(workflow_id, created_at)
idx_execution_entity ON workflow_executions(entity_type, entity_id)
idx_queue_scheduled ON workflow_execution_queue(scheduled_at, status)
idx_queue_workspace ON workflow_execution_queue(workspace_id, status)
```

---

## Phase 2: Core Service Layer (Week 1)

### 2.1 Create WorkflowService
**File:** `services/workflow_service.py`

```python
class WorkflowService:
    
    @staticmethod
    def trigger_event(workspace_id, trigger_type, entity_type, entity_id, context={}):
        """Find matching workflows, evaluate conditions, queue actions"""
    
    @staticmethod
    def evaluate_conditions(workflow, entity, context):
        """Evaluate AND/OR conditions"""
    
    @staticmethod
    def execute_action(action, entity, context):
        """Execute single action, create execution log"""
    
    @staticmethod
    def process_queue():
        """APScheduler job: process delayed actions"""
    
    @staticmethod
    def check_time_based_triggers():
        """APScheduler job: daily check for scheduled triggers"""
    
    @staticmethod
    def resolve_template(template_str, entity, context):
        """Jinja2-style {{contact.first_name}} → actual value"""
```

### 2.2 Trigger Types (Phase 1)
```python
TRIGGER_TYPES = {
    "deal_stage_changed": "Anlaşma aşaması değişti",
    "deal_created": "Yeni anlaşma oluşturuldu",
    "deal_won": "Anlaşma kazanıldı",
    "deal_lost": "Anlaşma kaybedildi",
    "contact_created": "Yeni kişi eklendi",
}
```

### 2.3 Action Handlers (Phase 1)
```python
# Action: create_task
- Create task linked to deal/contact
- Assign to owner or specific user
- Set priority and due date

# Action: notify_owner  
- Send internal notification to entity owner
- Use existing notification_service.py

# Action: update_deal_field
- Update any deal field
- Support stage changes

# Action: send_email
- Use existing email_hub_service.py
- Template variable support
```

---

## Phase 3: API Routes (Week 1)

### 3.1 Create Workflow Routes
**File:** `routes/workflows.py`

```
GET    /api/v1/workflows              — List all workflows
POST   /api/v1/workflows              — Create workflow
GET    /api/v1/workflows/<id>         — Get workflow details
PUT    /api/v1/workflows/<id>         — Update workflow
DELETE /api/v1/workflows/<id>         — Delete workflow
PATCH  /api/v1/workflows/<id>/toggle  — Toggle active status
GET    /api/v1/workflows/<id>/executions — Execution history
GET    /api/v1/workflows/<id>/stats   — Statistics
POST   /api/v1/workflows/<id>/test    — Test workflow

GET    /api/v1/workflows/templates    — Built-in templates
POST   /api/v1/workflows/templates/<id>/use — Create from template
```

### 3.2 Integration Points
Add trigger calls to existing routes:
```python
# routes/deals.py — when deal stage changes:
WorkflowService.trigger_event(workspace_id, "deal_stage_changed", "deal", deal.id,
    {"from_stage_id": old_stage, "to_stage_id": new_stage})

# routes/deals.py — when deal is won/lost:
WorkflowService.trigger_event(workspace_id, "deal_won", "deal", deal.id)

# routes/contacts.py — when contact created:
WorkflowService.trigger_event(workspace_id, "contact_created", "contact", contact.id)
```

---

## Phase 4: APScheduler Integration (Week 1)

### 4.1 Update TaskScheduler
**File:** `services/task_scheduler.py`

Add two new jobs:
```python
# Every minute: process delayed actions
scheduler.add_job(
    func=WorkflowService.process_queue,
    trigger="interval",
    minutes=1,
    id="workflow_queue_processor"
)

# Daily at 00:05: check time-based triggers
scheduler.add_job(
    func=WorkflowService.check_time_based_triggers,
    trigger="cron",
    hour=0,
    minute=5,
    id="workflow_time_triggers"
)
```

---

## Phase 5: Frontend Builder UI (Week 2)

### 5.1 Workflow Builder Page
**File:** `templates/automation.html` (add new section) or `templates/workflows.html`

**Layout:**
```
┌─────────────────────────────────────────────┐
│  SOL: Workflow Listesi                       │
│  - Aktif/Pasif toggle                        │
│  - Run count, son çalışma                    │
│  - Yeni Oluştur butonu                       │
├─────────────────────────────────────────────┤
│  SAĞ: Workflow Builder                        │
│  ┌─────────────────────────────────────────┐ │
│  │ 1. TETİKLEYICI                          │ │
│  │ [Dropdown] [Config alanları]             │ │
│  ├─────────────────────────────────────────┤ │
│  │ 2. KOŞULLAR (opsiyonel)                 │ │
│  │ [Alan] [Operatör] [Değer] [+Ekle]       │ │
│  │ AND / OR toggle                         │ │
│  ├─────────────────────────────────────────┤ │
│  │ 3. AKSİYONLAR                           │ │
│  │ [Tip] [Config] [+Ekle]                  │ │
│  │ (Sürükle-bırak sıralama)                │ │
│  └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### 5.2 Dynamic UI Features
- Trigger dropdown → dynamic config fields
- Action type → dynamic config form (email: subject+body, task: title+due)
- `{{` autocomplete for template variables
- Test button (simulate without executing)
- Execution history tab

---

## Phase 6: Built-in Templates (Week 2)

```python
WORKFLOW_TEMPLATES = [
    {
        "id": "new_lead_welcome",
        "name": "Yeni Lead Karşılama",
        "description": "Yeni kişi eklendiğinde otomatik karşılama emaili gönder ve takip görevi oluştur",
        "icon": "🤝",
        "trigger": "contact_created",
        "actions": ["send_email", "create_task"]
    },
    {
        "id": "deal_won_celebration", 
        "name": "Anlaşma Kazanıldı",
        "description": "Deal kazanılınca müşteriye teşekkür emaili gönder, onboarding görevi oluştur",
        "icon": "🏆",
        "trigger": "deal_won",
        "actions": ["send_email", "create_task", "notify_owner"]
    },
    {
        "id": "stage_follow_up",
        "name": "Teklif Sonrası Takip",
        "description": "Deal aşama değişince 2 gün sonra takip emaili gönder",
        "icon": "📧",
        "trigger": "deal_stage_changed",
        "actions": ["wait", "send_email"]
    },
]
```

---

## Implementation Sequence

### Week 1 — Core (Deal Triggers)
- [ ] Database models + migration
- [ ] WorkflowService skeleton with `trigger_event`, `evaluate_conditions`
- [ ] API routes (CRUD + test)
- [ ] `deal_stage_changed` trigger
- [ ] `create_task` action
- [ ] `notify_owner` action
- [ ] APScheduler jobs
- [ ] Basic frontend list view

### Week 2 — Expansion
- [ ] `deal_won` and `deal_lost` triggers
- [ ] `send_email` action (using existing SMTP)
- [ ] `update_deal_field` action
- [ ] Workflow builder UI (full 3-section form)
- [ ] Template variable autocomplete
- [ ] Built-in templates
- [ ] Execution history UI

### Week 3 — Contact Side
- [ ] `contact_created` trigger
- [ ] `add_tag` action
- [ ] `contact_no_activity` trigger (30-day inactivity)
- [ ] Condition operators: `contains`, `is_empty`, `changed_to`
- [ ] Advanced condition UI

---

## Security & Performance

- All queries must include `workspace_id` filter (multi-tenant isolation)
- Workflow max 1000 executions per day per workspace
- Cooldown: same entity + workflow combo limited (1hr to 24hr based on trigger type)
- Email rate limit: 100 emails/hour per workspace
- Webhook timeout: 10 seconds, 3 retries
- Circular workflow prevention: max 3 levels deep for `trigger_another_workflow`

---

## Key Files to Create/Modify

| File | Action |
|------|--------|
| `migrations/add_workflow_automation_tables.py` | Create |
| `models_crm.py` | Add 5 new model classes |
| `services/workflow_service.py` | Create |
| `services/email_hub_service.py` | Add `send_workflow_email()` |
| `routes/workflows.py` | Create (new blueprint) |
| `services/task_scheduler.py` | Add APScheduler jobs |
| `routes/deals.py` | Add trigger calls |
| `routes/contacts.py` | Add trigger calls |
| `static/workflow-builder.js` | Create |
| `templates/automation.html` | Add workflows tab |
| `app.py` | Register new blueprint |
