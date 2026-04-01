# n8n Architecture Adoption Plan for Sadas CRM

## Overview

This plan outlines how to upgrade Sadas CRM's workflow engine from MVP to enterprise-grade by adopting n8n's architecture patterns.

## n8n Source Reference

**Location:** `../n8n-master/`

### Key Packages Analyzed

| Package | Size | Purpose |
|---------|------|---------|
| `packages/workflow/` | ~500KB | Core interfaces, expression evaluation, workflow validation |
| `packages/core/` | ~200KB | Execution engine, node execution contexts |
| `packages/nodes-base/` | ~1MB+ | 400+ node implementations |

### Critical Files to Reference

1. **Execution Engine:** `packages/core/src/execution-engine/workflow-execute.ts` (86KB)
2. **Directed Graph:** `packages/core/src/execution-engine/partial-execution-utils/directed-graph.ts` (14KB)
3. **Node Base Class:** `packages/workflow/src/node-helpers.ts` (59KB)
4. **Interfaces:** `packages/workflow/src/interfaces.ts` (103KB)

## Architecture Comparison

```
n8n Structure                          Sadas Current
─────────────────────────────────────────────────────────────
packages/
├── workflow/                          services/
│   ├── interfaces.ts (103KB)         models_crm.py
│   ├── node-helpers.ts (59KB)        workflow_node_handlers.py
│   ├── expression.ts (19KB)           resolve_template()
│   └── workflow.ts                   workflow_service.py
├── core/
│   └── execution-engine/
│       ├── workflow-execute.ts (86KB)  workflow_graph_runner.py
│       ├── routing-node.ts (32KB)
│       ├── partial-execution-utils/     (MISSING)
│       └── node-execution-context/      (MISSING)
└── nodes-base/
    └── nodes/ (400+ nodes)            workflow_node_handlers.py (19 handlers)
```

## Implementation Phases

### Phase 1: Core Engine Foundation

**Goal:** Implement n8n-style execution engine with proper state management

#### 1.1 RunExecutionData System
```
n8n: run-execution-data/run-execution-data.ts
     run-execution-data.v0.ts, v1.ts

Sadas: Need to implement
├── workflow_execution_data table
│   ├── workflow_id
│   ├── execution_id
│   ├── run_data (JSON)
│   ├── checkpoint_data (JSON)
│   └── status (running/completed/failed)
└── services/execution_data.py
```

#### 1.2 Directed Graph with Cycle Detection
```
n8n: partial-execution-utils/directed-graph.ts (14KB)
     partial-execution-utils/handle-cycles.ts

Implement:
├── services/directed_graph.py
│   ├── findStartNodes()
│   ├── findSubgraph()
│   ├── handleCycles()
│   └── rewireGraph()
└── Update workflow_graph_runner.py
```

#### 1.3 Partial Execution (Resume from Failure)
```
n8n: partial-execution-utils/recreate-node-execution-stack.ts

Implement:
├── services/partial_execution.py
│   ├── recreateExecutionStack()
│   ├── getWaitingNodes()
│   └── resumeExecution()
└── Add checkpoint to workflow_executions table
```

### Phase 2: Expression Engine

**Goal:** Replace simple template replacement with n8n-style expressions

```
n8n: packages/workflow/src/expression.ts (19KB)
     packages/workflow/src/expression-evaluator-proxy.ts
     packages/workflow/src/expression-sandboxing.ts (17KB)

Implement:
├── services/expression_engine/
│   ├── __init__.py
│   ├── evaluator.py      # n8n Expression class port
│   ├── sandbox.py         # n8n ExpressionSandboxing port
│   ├── proxy.py           # n8n ExpressionEvaluatorProxy port
│   └── jinja_extensions.py # Custom filters for CRM
└── Supported syntax:
    - {{ $json.property }}
    - {{ $vars.name }}
    - {{ $workflow.id }}
    - {{ $node["NodeName"].data }}
    - {{ $binary.data }}
    - {{ $credentials.api }}
```

### Phase 3: Node Execution Context

**Goal:** Implement n8n-style node context with full API access

```
n8n: packages/core/src/execution-engine/node-execution-context/

Sadas:
├── services/node_context/
│   ├── base_context.py     # BaseExecuteContext
│   ├── execute_context.py  # ExecuteContext
│   ├── webhook_context.py  # WebhookContext
│   ├── trigger_context.py  # TriggerContext
│   └── supply_data_context.py
└── Each context provides:
    - getWorkflowStaticData()
    - getNodeParameters()
    - getCredentials()
    - helpers (httpRequest, jsonParse, etc.)
```

### Phase 4: Credentials System

**Goal:** Implement encrypted credentials like n8n

```
n8n: packages/core/src/credentials.ts
     packages/workflow/src/workflow-data-proxy.ts (credentials part)

Implement:
├── models_crm.py additions:
│   └── Credential model
│       ├── id, name, type
│       ├── data (encrypted JSON)
│       └── encrypted (boolean)
├── services/credentials/
│   ├── manager.py          # Credential CRUD
│   ├── encryption.py        # AES encryption
│   └── proxy.py            # Credential access in nodes
└── Migration:
    └── migrations/add_credentials_table.py
```

### Phase 5: Node Implementation (CRM-Focused)

**Goal:** Implement key CRM nodes matching n8n's quality

#### Priority 1: Core CRM Nodes
```
1. HubSpot.node.ts           # CRM integration
2. Salesforce.node.ts         # CRM integration  
3. PostgreSQL.node.ts         # Database
4. HTTPRequest.node.ts       # API calls
5. Webhook.node.ts           # Triggers
6. Code.node.ts              # Custom code (JS/Python)
```

#### Priority 2: Logic Nodes
```
7. If.node.ts                # Conditional branching
8. Switch.node.ts            # Multi-branch
9. SplitInBatches.node.ts    # Loops
10. Wait.node.ts             # Delay
```

#### Priority 3: Integration Nodes
```
11. EmailSend.node.ts
12. Telegram.node.ts
13. Slack.node.ts
14. GoogleSheets.node.ts
```

### Phase 6: Advanced Features

#### 6.1 Binary Data Handling
```
n8n: packages/core/src/execution-engine/node-execution-context/utils/binary-helper-functions.ts (10KB)

Implement: services/binary_data.py
- Binary mode streaming
- File operations
- Image processing
```

#### 6.2 Message Event Bus
```
n8n: packages/workflow/src/message-event-bus.ts (9KB)

Implement: services/event_bus.py
- Internal event routing
- Webhook callbacks
```

#### 6.3 External Secrets
```
n8n: packages/core/src/execution-engine/external-secrets-proxy.ts

Implement: services/secrets_proxy.py
- HashiCorp Vault
- AWS Secrets Manager
- Environment variables
```

### Phase 7: Testing & Documentation

```
├── __tests__/
│   ├── test_workflow_execution.py
│   ├── test_node_execution.py
│   ├── test_expressions.py
│   ├── test_credentials.py
│   └── test_partial_execution.py
└── Documentation:
    ├── docs/workflow-nodes.md
    ├── docs/expression-syntax.md
    └── docs/credentials-setup.md
```

## Key Architectural Patterns from n8n

### 1. Dependency Injection
```typescript
// n8n style
constructor(
  private readonly logger: Logger,
  private readonly loadOptionsContext: LoadOptionsContext,
) {}
```

### 2. Interface-Based Design
```typescript
// Every node implements INode
interface INode {
  execute(context: IExecuteFunctions): Promise<INodeExecutionData[][]>;
  webhook?(context: IWebhookFunctions): Promise<IWebhookResponseData>;
}
```

### 3. Execution Data Immutable Updates
```typescript
// n8n uses DataModel pattern for run data
// Sadas should use JSON patch for incremental updates
```

## Migration Strategy

### Step 1: Backward Compatibility
Keep existing `workflow_node_handlers.py` working alongside new system

### Step 2: Incremental Adoption
Add new components without breaking existing workflows

### Step 3: Flag-Based Switching
```python
# Feature flag for new engine
WORKFLOW_ENGINE_V2 = os.getenv('WORKFLOW_ENGINE_V2', 'false')
```

## Effort Estimation

| Phase | Complexity | Files to Create | Lines of Code |
|-------|-----------|----------------|---------------|
| Phase 1 | High | 5-8 | 2000-3000 |
| Phase 2 | High | 4-6 | 1500-2500 |
| Phase 3 | Very High | 8-12 | 3000-5000 |
| Phase 4 | Medium | 4-6 | 1000-1500 |
| Phase 5 | High | 15+ | 5000+ |
| Phase 6 | Medium | 4-6 | 1000-2000 |
| Phase 7 | Low | 10+ tests | 2000+ |

## Decision Points

1. **Python-first vs Hybrid:** Should we keep Python or add Node.js service?
2. **Sandboxing:** Should we use PyPy/cpython or subprocess isolation?
3. **Database:** Current SQLite sufficient or need PostgreSQL for concurrency?
4. **Credentials:** Redis-backed encryption or database-only?

## Recommended Next Steps

1. **Immediate:** Implement `directed-graph.ts` port for cycle detection
2. **This Week:** Add `partial-execution-utils` for resume capability
3. **This Month:** Complete expression engine with sandbox
4. **This Quarter:** Core CRM nodes (HubSpot, PostgreSQL, HTTPRequest)
