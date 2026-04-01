# n8n-Style Workflow Engine Implementation Plan

## Overview

This document describes the implementation of an n8n-style workflow execution engine for the CRM system. The engine executes workflows as directed graphs, passing data between nodes, with support for branching, conditions, and error recovery.

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    Workflow System Architecture                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Frontend    │    │    Backend    │    │   Database    │      │
│  │  (ReactFlow)  │───▶│  (Flask API) │───▶│  (PostgreSQL) │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                    │                                   │
│         │                    │                                   │
│  ┌──────┴──────┐    ┌───────┴──────────┐                       │
│  │ Canvas Data │    │  Graph Runner    │                       │
│  │ (nodes+edges)│    │  (Execution Engine)│                    │
│  └─────────────┘    └──────────────────┘                       │
│                              │                                   │
│                       ┌──────┴──────┐                           │
│                       │Node Handlers│                           │
│                       │(Trigger/Cond/Action)│                   │
│                       └─────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Schema First**: Workflow schema is defined as JSON (nodes + edges) — this is the contract
2. **Graph Runner Core**: The execution engine is written once, handles orchestration
3. **Node Handlers**: Individual node handlers are modular and can be AI-generated
4. **State Passing**: Data flows between nodes via a shared context dictionary
5. **Error Recovery**: Per-node retry logic with configurable policies

## Workflow Schema (JSON Contract)

```json
{
  "nodes": [
    {
      "id": "trigger_1",
      "position": { "x": 250, "y": 80 },
      "data": {
        "nodeType": "trigger",
        "subtype": "deal_stage_changed",
        "label": "Anlaşma Aşaması Değişti",
        "config": {
          "from_stage_id": 3,
          "to_stage_id": 5
        }
      }
    },
    {
      "id": "condition_1",
      "position": { "x": 250, "y": 260 },
      "data": {
        "nodeType": "condition",
        "subtype": "check_field",
        "label": "Alan Kontrol Et",
        "config": {
          "field_name": "deal_amount",
          "operator": "greater_than",
          "value": "10000"
        }
      }
    },
    {
      "id": "action_1",
      "position": { "x": 100, "y": 440 },
      "data": {
        "nodeType": "action",
        "subtype": "notify_owner",
        "label": "Sahiplere Bildirim Gönder",
        "config": {
          "message": "Yüksek değerli anlaşma: {{deal.name}}"
        }
      }
    },
    {
      "id": "action_2",
      "position": { "x": 400, "y": 440 },
      "data": {
        "nodeType": "action",
        "subtype": "create_task",
        "label": "Görev Oluştur",
        "config": {
          "title": "{{deal.name}} için takip",
          "due_in_days": 3,
          "assign_to": "deal_owner"
        }
      }
    }
  ],
  "edges": [
    {
      "id": "e1",
      "source": "trigger_1",
      "target": "condition_1"
    },
    {
      "id": "e2",
      "source": "condition_1",
      "target": "action_1",
      "sourceHandle": "true"
    },
    {
      "id": "e3",
      "source": "condition_1",
      "target": "action_2",
      "sourceHandle": "false"
    }
  ]
}
```

## Node Types

### Triggers (Blue)
| Node Type | Description | Config Fields |
|-----------|-------------|---------------|
| `contact_created` | Yeni kişi eklendi | - |
| `contact_updated` | Kişi güncellendi | - |
| `contact_tag_added` | Etiket eklendi | `tag_name` |
| `contact_no_activity` | Kişi aktivitesiz | `days`, `min_lead_score` |
| `deal_created` | Yeni anlaşma | - |
| `deal_stage_changed` | Aşama değişti | `from_stage_id`, `to_stage_id` |
| `deal_won` | Anlaşma kazanıldı | - |
| `deal_lost` | Anlaşma kaybedildi | - |
| `deal_amount_changed` | Tutar değişti | - |
| `deal_no_activity` | Anlaşma aktivitesiz | `days` |
| `task_created` | Görev oluşturuldu | - |
| `task_completed` | Görev tamamlandı | - |
| `deal_close_date_approaching` | Kapanış tarihi yaklaşıyor | `days_before` |

### Conditions (Yellow)
| Node Type | Description | Config Fields |
|-----------|-------------|---------------|
| `check_field` | Alan kontrol et | `field_name`, `operator`, `value` |
| `check_score` | Skor kontrol et | `operator`, `value` |
| `if` | IF/Else | `conditions` (JSON array) |

### Actions (Green)
| Node Type | Description | Config Fields |
|-----------|-------------|---------------|
| `create_task` | Görev oluştur | `title`, `due_in_days`, `assign_to` |
| `send_email` | Email gönder | `to`, `subject`, `body` |
| `send_whatsapp` | WhatsApp mesajı | `message` |
| `notify_owner` | Bildirim gönder | `message`, `title` |
| `update_deal_stage` | Aşama güncelle | `stage_id` |
| `update_deal_field` | Anlaşma alanı güncelle | `field_name`, `field_value` |
| `update_contact_field` | Kişi alanı güncelle | `field_name`, `field_value` |
| `add_tag` | Etiket ekle | `tag_name` |
| `remove_tag` | Etiket kaldır | `tag_name` |
| `assign_owner` | Sahip ata | `assign_to` |
| `create_note` | Not oluştur | `content` |
| `webhook` | Webhook gönder | `url`, `method` |
| `wait` | Bekle | `delay_minutes` |
| `http_request` | HTTP isteği | `url`, `method`, `auth_type`, `header_key`, `header_value`, `body`, `timeout` |
| `code` | Kod çalıştır | `language`, `code` |
| `wait_until` | Tarihe kadar bekle | `timestamp_field`, `timeout_hours` |
| `set_node` | Değer ayarla | `field_name`, `field_value` |
| `ai_agent` | AI Agent | `provider`, `model`, `system_prompt`, `user_prompt`, `max_tokens`, `output_variable`, `temperature` |

## Execution Flow

```
1. Parse Canvas Data
   └── Build Graph (adjacency list)
   
2. Find Trigger Node
   └── Validate workflow has exactly one trigger
   
3. Initialize Context
   └── Load entity data
   └── Set up variables dictionary
   
4. Execute Graph (BFS)
   └── For each node:
       ├── Get handler from registry
       ├── Execute handler with context
       ├── Store output in context
       └── Determine which children to execute
           ├── Condition nodes: follow true/false branch
           └── Other nodes: follow all edges
   
5. Compile Results
   └── Update execution log
   └── Update workflow statistics
```

## File Structure

```
services/
├── workflow_graph_runner.py      # Core execution engine (graph runner)
├── workflow_node_handlers.py     # Individual node handlers
└── workflow_service.py           # Legacy service (backward compatible)

routes/
└── workflows.py                  # API endpoints (updated with graph execution)

plans/
└── n8n_workflow_engine_implementation.md  # This file
```

## API Endpoints

### Execute Workflow Graph
```
POST /api/v1/workflows/:id/execute

Request:
{
  "entity_type": "deal",
  "entity_id": 123,
  "context": {"from_stage_id": 3, "to_stage_id": 5},
  "canvas_data": {...}  // optional, uses stored canvas_data if not provided
}

Response:
{
  "workflow_id": 1,
  "execution_id": 456,
  "status": "success",
  "started_at": "2026-03-31T11:30:00",
  "completed_at": "2026-03-31T11:30:02",
  "node_results": [
    {
      "node_id": "trigger_1",
      "node_type": "trigger",
      "subtype": "deal_stage_changed",
      "status": "success",
      "duration_ms": 5,
      "output": {"trigger": "deal_stage_changed", "entity": {...}}
    },
    {
      "node_id": "condition_1",
      "node_type": "condition",
      "subtype": "check_field",
      "status": "success",
      "duration_ms": 2,
      "output": {"condition_result": true, "field_value": 15000}
    },
    {
      "node_id": "action_1",
      "node_type": "action",
      "subtype": "notify_owner",
      "status": "success",
      "duration_ms": 150,
      "output": {"status": "success", "owner_id": 42}
    }
  ],
  "duration_ms": 157
}
```

### Dry Run Workflow Graph
```
POST /api/v1/workflows/:id/execute/dry-run

Returns execution plan without executing actions.
Useful for debugging and validation.
```

## Template Variables

All action configs support template variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `{{entity.field}}` | Entity field | `{{entity.name}}` |
| `{{entity.first_name}}` | Contact first name | `{{entity.first_name}}` |
| `{{trigger.field}}` | Trigger context field | `{{trigger.from_stage_id}}` |
| `{{variables.name}}` | Previous node output | `{{variables.ai_response}}` |
| `{{contact.first_name}}` | Shorthand for entity | `{{contact.first_name}}` |
| `{{deal.name}}` | Shorthand for entity | `{{deal.name}}` |

## Error Handling

Each node supports configurable error handling:

```json
{
  "config": {
    "on_error_action": "stop" | "continue" | "retry",
    "max_retries": 3,
    "retry_delay": 1
  }
}
```

- **stop**: Stop execution on error (default)
- **continue**: Continue with next node
- **retry**: Retry with configurable attempts

## Security Considerations

1. **Code Execution**: The `code` node is disabled by default for security
2. **HTTP Requests**: External URLs are allowed — consider adding allowlist
3. **AI Providers**: API keys are read from workspace settings, not hardcoded
4. **DB Transactions**: All DB operations wrapped in try/except with rollback

## Migration Notes

- Existing `workflow_service.py` remains backward compatible
- New graph execution is opt-in via `/execute` endpoint
- Canvas data stored in `workflow_automations.canvas_data` column
- No schema changes required — uses existing tables

## Testing

### Unit Tests
```python
# Test graph building
def test_build_graph():
    canvas_data = {"nodes": [...], "edges": [...]}
    runner = WorkflowGraphRunner()
    graph = runner._build_graph(canvas_data)
    assert len(graph['nodes']) == 4
    assert len(graph['edges']) == 3

# Test condition evaluation
def test_condition_branch():
    context = {"entity": {"deal_amount": 15000}}
    config = {"field_name": "deal_amount", "operator": "greater_than", "value": "10000"}
    result = ConditionHandler._check_field({}, context, config)
    assert result['condition_result'] == True
```

### Integration Tests
```bash
# Execute workflow
curl -X POST http://localhost:5000/api/v1/workflows/1/execute \
  -H "Content-Type: application/json" \
  -d '{"entity_type": "deal", "entity_id": 123}'

# Dry run
curl -X POST http://localhost:5000/api/v1/workflows/1/execute/dry-run \
  -H "Content-Type: application/json" \
  -d '{"entity_type": "deal", "entity_id": 123}'
```

## Future Enhancements

1. **Parallel Execution**: Support parallel node execution for independent branches
2. **Webhook Triggers**: External webhook URLs that trigger workflows
3. **Scheduled Execution**: Cron-based workflow scheduling
4. **Sub-workflows**: Call other workflows as sub-graphs
5. **Loop/Batch Processing**: Iterate over collections with concurrency control
6. **Visual Debug Mode**: Show execution flow on canvas in real-time
