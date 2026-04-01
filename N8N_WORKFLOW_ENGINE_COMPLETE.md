# n8n-Style Workflow Engine - Implementation Complete

## Summary

Enterprise-grade n8n-style workflow engine implementation for Sadas CRM, featuring directed graph execution, expression evaluation, and real-time execution state synchronization.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (React + ReactFlow)                 │
├─────────────────────────────────────────────────────────────────────┤
│  WorkflowCanvas.tsx  │  ExpressionEditor.tsx  │  NodePropertiesPanel│
│  └─ ReactFlow Canvas     └─ Variable Picker        └─ Config Forms  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ REST API / WebSocket
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Backend (Flask + SQLAlchemy)                 │
├─────────────────────────────────────────────────────────────────────┤
│  routes/workflows.py                                                │
│   └─ POST /api/v1/workflows/{id}/execute   (execute workflow)      │
│   └─ POST /api/v1/workflows/{id}/test-run   (dry-run workflow)      │
│   └─ GET  /api/v1/workflows/executions/{id} (get execution status)  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Services (Business Logic)                         │
├─────────────────────────────────────────────────────────────────────┤
│  workflow_graph_runner.py  │  workflow_node_handlers.py             │
│   └─ DirectedGraph execution    └─ Node type handlers (30+ types)    │
│   └─ Topological sort          └─ TriggerHandler                    │
│   └─ Retry logic              └─ ConditionHandler                   │
│   └─ Error handling            └─ ActionHandler                      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Expression Engine                                 │
├─────────────────────────────────────────────────────────────────────┤
│  services/expression_engine/                                         │
│   └─ evaluator.py         (expression parsing & evaluation)          │
│   └─ sandbox.py           (safe variable resolution)                │
│   └─ ast_validator.py     (AST-based security validation)           │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Node Execution Contexts                           │
├─────────────────────────────────────────────────────────────────────┤
│  services/node_context/                                              │
│   └─ base.py           (BaseNodeContext - credentials & params)   │
│   └─ execute.py         (ExecuteContext - HTTP, binary data)       │
│   └─ webhook.py         (WebhookContext - request/response)        │
│   └─ trigger.py         (TriggerContext - polling, scheduling)     │
│   └─ credentials.py     (CredentialsManager - AES-256-GCM encrypt) │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Files Created

### Backend Services

| File | Purpose |
|------|---------|
| [`services/directed_graph.py`](services/directed_graph.py) | DirectedGraph class with cycle detection, topological sort, partial execution |
| [`services/expression_engine/__init__.py`](services/expression_engine/__init__.py) | Module initialization |
| [`services/expression_engine/evaluator.py`](services/expression_engine/evaluator.py) | Expression evaluation (`{{ $node["X"].json.field }}`) |
| [`services/expression_engine/sandbox.py`](services/expression_engine/sandbox.py) | Sandboxed environment for safe variable resolution |
| [`services/expression_engine/ast_validator.py`](services/expression_engine/ast_validator.py) | AST-based security validation |
| [`services/node_context/base.py`](services/node_context/base.py) | BaseNodeContext (credentials, parameters) |
| [`services/node_context/execute.py`](services/node_context/execute.py) | ExecuteContext (HTTP requests, binary data) |
| [`services/node_context/webhook.py`](services/node_context/webhook.py) | WebhookContext (request/response) |
| [`services/node_context/trigger.py`](services/node_context/trigger.py) | TriggerContext (polling, scheduling) |
| [`services/node_context/credentials.py`](services/node_context/credentials.py) | CredentialsManager (AES-256-GCM encryption) |

### Database Migrations

| File | Purpose |
|------|---------|
| [`migrations/add_workflow_execution_tables.sql`](migrations/add_workflow_execution_tables.sql) | PostgreSQL schema for execution tracking |

### Frontend Components

| File | Purpose |
|------|---------|
| [`../vite/workflow-ui/src/components/ExpressionEditor.tsx`](../vite/workflow-ui/src/components/ExpressionEditor.tsx) | n8n-style expression editor with variable picker |
| [`../vite/workflow-ui/src/store/executionSocket.ts`](../vite/workflow-ui/src/store/executionSocket.ts) | WebSocket service for real-time execution updates |
| [`../vite/workflow-ui/src/store/workflowStore.ts`](../vite/workflow-ui/src/store/workflowStore.ts) | Updated with execution state management |

### API Routes

| File | Purpose |
|------|---------|
| [`routes/workflows.py`](routes/workflows.py) | Added `GET /executions/{id}` endpoint |

---

## Key Features

### 1. Expression Engine
```python
# Supports n8n-style expressions
"Hello {{ $node["Webhook"].json.body.name }}"
"Total: {{ $variables.sum_result * 2 }}"
"{{ $env.NODE_ENV }}"

# AST-based validation prevents code injection
# Sandboxed evaluation keeps expressions safe
```

### 2. Node Execution Contexts
```python
# Trigger Context (polling/scheduled)
ctx.emit({'contact_id': 123, 'name': 'John'})

# Execute Context (HTTP requests)
response = ctx.http_request({
    'url': 'https://api.example.com',
    'method': 'POST',
    'body': ctx.getInputData()
})

# Webhook Context (request/response)
request_body = ctx.getRequestBody()
ctx.sendResponse(200, {'success': True})
```

### 3. Credentials Management
```python
# AES-256-GCM encrypted credentials
creds = credentials_manager.get_credentials(
    credential_id=123,
    credential_type='http_query_auth',
    workspace_id=1
)
# Cached for 1 hour, auto-decrypted
```

### 4. Real-time Execution (Frontend)
```typescript
// Polling-based execution status
executionSocket.startPolling(executionId)

// Subscribe to updates
const unsubscribe = executionSocket.subscribe((update) => {
    if (update.type === 'node_started') {
        console.log(`Node ${update.nodeId} started`)
    }
})

// Update store in real-time
store.setExecutionState({
    isRunning: true,
    currentNodeId: update.nodeId,
    nodeResults: { ... }
})
```

---

## API Endpoints

### Execute Workflow
```
POST /api/v1/workflows/{workflow_id}/execute
{
    "entity_type": "contact",
    "entity_id": 123,
    "canvas_data": {
        "nodes": [...],
        "edges": [...]
    }
}
```

### Dry Run
```
POST /api/v1/workflows/{workflow_id}/execute/dry-run
{
    "entity_type": "contact",
    "entity_id": 123
}
```

### Get Execution Status
```
GET /api/v1/workflows/executions/{execution_id}
{
    "workflow_id": 1,
    "execution_id": 456,
    "status": "running",
    "started_at": "2026-03-31T15:00:00",
    "node_results": [
        {
            "node_id": "trigger-1",
            "status": "success",
            "output": {...}
        }
    ]
}
```

---

## Node Types Supported

### Triggers
- `contact_created`, `contact_updated`, `contact_tag_added`
- `deal_created`, `deal_stage_changed`, `deal_won`, `deal_lost`
- `task_created`, `task_completed`
- `schedule` (cron-based)

### Conditions
- `check_field`, `check_score`, `if`
- `loop_over_items`, `split_in_batches`

### Actions
- `create_task`, `send_email`, `send_whatsapp`
- `update_deal_stage`, `update_contact_field`
- `add_tag`, `remove_tag`, `assign_owner`
- `webhook`, `http_request`, `code`
- `wait`, `wait_until`, `set_node`
- `ai_agent`, `call_workflow`

---

## Security Features

1. **Expression Sandboxing**: AST validation prevents dangerous operations
2. **Credentials Encryption**: AES-256-GCM with per-workspace keys
3. **CSRF Protection**: All API endpoints require CSRF token
4. **IDOR Protection**: Workspace-based access control
5. **Input Validation**: All inputs sanitized before use

---

## Execution Flow

```
1. Trigger Event (schedule, webhook, entity change)
   ↓
2. Load Workflow & Canvas Data
   ↓
3. Build Directed Graph
   ↓
4. Topological Sort (execution order)
   ↓
5. For Each Node:
   ├─ Load Credentials (decrypt)
   ├─ Resolve Expressions
   ├─ Execute Node Handler
   ├─ Store Output (for downstream)
   └─ Handle Errors / Retries
   ↓
6. Update Execution Status
   ↓
7. Notify Downstream Systems
```

---

## Testing

```bash
# Test workflow execution
python test_workflow_e2e.py

# Test expression engine
# Manual testing via API:
POST /api/v1/workflows/{id}/test-run
```

---

## Production Checklist

- [ ] Set `N8N_ENCRYPTION_KEY` environment variable (32 bytes)
- [ ] Configure PostgreSQL for production (not SQLite)
- [ ] Set up Redis for credentials caching
- [ ] Configure WebSocket server for real-time updates
- [ ] Set up monitoring (Sentry, DataDog)
- [ ] Configure rate limiting
- [ ] Set up backup strategy for PostgreSQL

---

## References

- n8n Architecture: `../n8n-master/packages/core/src/`
- ReactFlow: `@xyflow/react`
- Expression Parser: inspired by n8n's expression evaluation
