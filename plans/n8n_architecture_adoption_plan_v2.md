# n8n Architecture Adoption Plan v2 - Sadas CRM

## Decision Points (ANSWERED)

### 1. Database: PostgreSQL (Required for Enterprise)

**Rationale:**
- Partial execution requires checkpointing with concurrent access
- SQLite has only 1 writer - blocks all readers during write
- n8n uses PostgreSQL/MySQL in production
- Concurrent workflow executions need row-level locking
- Binary data (workflow data) can be stored in database or S3

```sql
-- Required tables for enterprise workflow
workflow_executions (
  id, workflow_id, status, 
  checkpoint_data JSONB,  -- for resume
  run_data JSONB,
  started_at, finished_at,
  mode VARCHAR -- 'trigger', 'webhook', 'scheduled', 'test'
)

workflow_execution_data (
  execution_id, 
  node_id,
  data JSONB,
  INDEX idx_execution_node (execution_id, node_id)
)
```

### 2. Expression Sandbox: **subprocess isolation + AST parsing**

**Why NOT RestrictedPython alone:**
- RestrictedPython only restricts dangerous AST patterns
- Doesn't prevent infinite loops, memory exhaustion
- Doesn't handle n8n's complex syntax like `$node["Node Name"].json["field-name"]`

**Recommended Approach:**
```
Tier 1: AST-based validation (RestrictedPython pattern)
  - Blocks: import, exec, eval, os/, sys/, open()
  - Allows: math, string ops, dict access

Tier 2: Subprocess timeout (for Code node)
  - Run Python in subprocess with ulimit
  - 5 second timeout, 100MB memory limit
  - Docker container for production

Tier 3: Jinja2 for template expressions (current)
  - {{ $json.property }} - already works
  - {{ $vars.name }} - already works
  - Extend with custom filters
```

**n8n Syntax Support Target:**
```python
# Must support:
{{ $json.contact.firstName }}
{{ $node["HTTP Request"].json.data[0].id }}
{{ $vars.counter + 1 }}
{{ $binary.image.fileName }}
{{ $credentials.api_key }}
{{ $workflow.id }}
{{ Date.now() }}  # JavaScript only in Code node
```

### 3. Credentials: **Database + Redis hybrid**

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Redis     │────▶│  Database   │────▶│   Memory    │
│  (cache)    │     │ (encrypted) │     │  (decrypted)│
└─────────────┘     └─────────────┘     └─────────────┘
   1hr TTL          AES-256             Per-execution
```

**Why:**
- Credentials decrypted only in node execution context
- Redis caches decrypted creds for 1 hour (not on disk)
- Database stores AES-encrypted credentials
- Encryption key from ENVIRONMENT VARIABLE

---

## Phase 2: Expression Engine (DETAILED)

### Current State
```python
# Sadas current implementation
def resolve_template(self, template: str, context: Dict) -> str:
    pattern = r'\{\{([^}]+)\}\}'
    # Simple regex replacement
```

### Target: n8n-style Expression Evaluator

**Reference:** `../n8n-master/packages/workflow/src/expression.ts` (19KB)

```python
# services/expression_engine/
# ├── __init__.py
# ├── evaluator.py        # Main Expression class
# ├── ast_builder.py      # Parse {{ }} to AST
# ├── sandbox.py          # Safe evaluation context
# ├── jinja_extensions.py # Custom Jinja2 filters
# └── types.py

# Expression Evaluator Architecture
"""
{{ $node["HTTP Request"].json.data[0].id }}
         │
         ▼
┌─────────────────┐
│   AST Builder   │  Tokenize → Parse → AST
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Sandboxed Env │  $node, $json, $vars, $binary, $credentials
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Evaluator    │  Walk AST, resolve references
└────────┬────────┘
         │
         ▼
      result
"""
```

### Implementation Details

```python
# services/expression_engine/evaluator.py
class ExpressionEvaluator:
    """n8n Expression class port"""
    
    SUPPORTED_SYNTAX = [
        # Variable access
        '$json.key', '$json.key.nested',
        '$vars.name',
        '$node["NodeName"].json.field',
        '$node["NodeName"].binary.data.fileName',
        '$credentials.type.field',
        '$workflow.id',
        '$input.item.json.field',
        
        # Operators
        '+', '-', '*', '/', '%',
        '==', '!=', '<', '>', '<=', '>=',
        '&&', '||', '!',
        
        # Functions
        'Date.now()', 'Date.parse()', 'Math.random()',
        'Object.keys()', 'Object.values()',
        'String.slice()', 'Array.isArray()',
    ]
    
    def __init__(self, context: 'ExecutionContext'):
        self.context = context
        self.env = SandboxedEnvironment(context)
    
    def evaluate(self, expression: str) -> Any:
        """Main entry point"""
        # 1. Tokenize
        tokens = tokenize(expression)
        # 2. Build AST
        ast = parse_to_ast(tokens)
        # 3. Validate AST against allowed patterns
        if not self._is_safe(ast):
            raise SecurityError(f"Blocked expression: {expression}")
        # 4. Evaluate with sandbox
        return self._eval(ast, self.env)
```

### Security Implementation

```python
# services/expression_engine/sandbox.py
import ast
import subprocess
import resource

class SandboxedEnvironment:
    """Safe environment for expression evaluation"""
    
    BLOCKED_MODULES = {
        'os', 'sys', 'subprocess', 'importlib',
        'builtins'  # partially blocked
    }
    
    BLOCKED_ATTRS = {
        '__import__', 'eval', 'exec', 'compile',
        'open', 'file', 'input', 'print'  # print allowed in debug
    }
    
    ALLOWED_BUILTINS = {
        'True', 'False', 'None',
        'abs', 'all', 'any', 'bool', 'dict', 'float',
        'int', 'list', 'len', 'max', 'min', 'ord', 'chr',
        'range', 'reversed', 'sorted', 'str', 'sum',
        'tuple', 'type', 'zip',
    }
    
    def resolve(self, path: str) -> Any:
        """Resolve expression path like $node["HTTP"].json.data"""
        parts = path.split('.')
        current = self.context
        
        for part in parts:
            if part.startswith('$'):
                current = self._resolve_variable(part, current)
            elif '[' in part:
                # Handle $node["Name"] or array[0]
                current = self._resolve_bracket(current, part)
            else:
                current = getattr(current, part, None)
        
        return current
```

### Code Node (Python/JS Execution)

```python
# services/expression_engine/code_sandbox.py

class CodeSandbox:
    """
    For {{ $json.code }} expressions that contain Python/JS
    Reference: ../n8n-master/packages/nodes-base/nodes/Code/
    """
    
    def execute_python(self, code: str, context: dict, timeout: int = 5) -> Any:
        """Execute Python code in subprocess with limits"""
        
        # Security: AST validate first
        tree = ast.parse(code)
        self._validate_ast(tree)
        
        # Prepare sandboxed globals
        sandbox_globals = {
            '__builtins__': self.ALLOWED_BUILTINS,
            'json': context.get('$json', {}),
            'vars': context.get('$vars', {}),
        }
        
        # Run with timeout and memory limit
        try:
            result = subprocess.run(
                ['python', '-c', code],
                input=json.dumps(context),
                capture_output=True,
                timeout=timeout,
                memory_limit=100 * 1024 * 1024  # 100MB
            )
            
            if result.returncode != 0:
                raise CodeExecutionError(result.stderr)
            
            return json.loads(result.stdout)
            
        except subprocess.TimeoutExpired:
            raise CodeExecutionError("Code execution timed out")
        except subprocess.MemoryError:
            raise CodeExecutionError("Code exceeded memory limit")
    
    # JavaScript uses isolated-vm (Node.js subprocess)
    def execute_javascript(self, code: str, context: dict) -> Any:
        """Execute JS in Node.js subprocess"""
        # Similar to Python but uses Node.js with vm2 or isolated-vm
```

### Phase 2 Effort Estimation

| Task | Best Case | Expected | Worst Case |
|------|-----------|----------|------------|
| AST Builder | 3 days | 5 days | 10 days |
| Sandboxed Env | 2 days | 4 days | 7 days |
| Code Sandbox | 5 days | 10 days | 20 days |
| Node Access ($node) | 2 days | 3 days | 5 days |
| Tests | 3 days | 5 days | 10 days |
| **TOTAL** | **15 days** | **27 days** | **52 days** |

---

## Phase 3: Node Execution Context (DETAILED)

### Reference Architecture

**n8n:** `packages/core/src/execution-engine/node-execution-context/`
```
base-execute-context.ts     # 7.7KB - Base class
execute-context.ts          # 7.2KB - Main execution
supply-data-context.ts      # 10KB - Trigger context
webhook-context.ts          # 4.6KB - Webhook handling
```

### Python Class Hierarchy

```python
# services/node_context/
# ├── __init__.py
# ├── base.py
# ├── execute.py
# ├── webhook.py
# ├── trigger.py
# ├── credentials.py
# └── helpers.py

# services/node_context/base.py
class BaseNodeContext:
    """n8n BaseExecuteContext port"""
    
    def __init__(self, execution_data: dict, node: dict):
        self._execution_data = execution_data
        self._node = node
        self._parameters = node.get('parameters', {})
        self._credentials = None  # Loaded on demand
    
    # ─── Parameter Access ───
    def getNodeParameter(self, param_name: str, default: Any = None) -> Any:
        """Get parameter value, evaluating expressions"""
        value = self._parameters.get(param_name, default)
        if isinstance(value, str) and '{{' in value:
            return self._evaluate_expression(value)
        return value
    
    def getNodeParameters(self) -> dict:
        """Get all parameters (raw or evaluated)"""
        return self._parameters
    
    # ─── Credentials ───
    def getCredentials(self, credential_type: str) -> dict:
        """
        Decrypt and return credentials for this node
        n8n: this.httpRequestWithCredentials
        """
        if self._credentials is None:
            creds_id = self._parameters.get(f'{credential_type}_id')
            self._credentials = self._load_credentials(creds_id, credential_type)
        return self._credentials
    
    # ─── Workflow Data ───
    def getWorkflowStaticData(self, type: str = 'node') -> dict:
        """Persistent data across executions (n8n $data)"""
        # Returns workflow-level or node-level static data
    
    def getInputData(self, index: int = 0) -> list:
        """Get data from previous node"""
        return self._execution_data.get('inputData', [{}])[index]
    
    def getWorkflowId(self) -> str:
        return self._execution_data.get('workflow_id')
    
    # ─── Logging ───
    def log(self, level: str, message: str, **kwargs):
        """Wrapper for logger with node context"""
        logger.log(level, f"[{self._node['name']}] {message}", **kwargs)


# services/node_context/execute.py
class ExecuteContext(BaseNodeContext):
    """
    n8n ExecuteContext port
    Context for regular node execution
    """
    
    def __init__(self, execution_data: dict, node: dict, index: int):
        super().__init__(execution_data, node)
        self._index = index  # Input index
    
    # ─── HTTP Requests ───
    def httpRequest(self, options: dict) -> Any:
        """
        n8n: this.helpers.httpRequest
        Makes authenticated HTTP requests
        """
        # 1. Merge credentials
        # 2. Apply timeout, headers
        # 3. Handle pagination
        # 4. Return parsed response
        pass
    
    # ─── Binary Data ───
    def getBinaryData(self, key: str = 'input') -> Any:
        """Get binary data for processing"""
        pass
    
    def prepareOutputData(self, data: Any) -> list:
        """Format output data for next node"""
        pass
    
    # ─── Helpers ───
    def helpers(self) -> 'NodeHelpers':
        """Return helper class instance"""
        return NodeHelpers(self)
    
    def evaluateExpression(self, expr: str, item_index: int = 0) -> Any:
        """Evaluate expression with item context"""
        context = {
            '$input': self.getInputData(self._index),
            '$json': self.getInputData(self._index)[item_index].get('json', {}),
            '$node': self._execution_data.get('nodes', {}),
        }
        return ExpressionEvaluator(context).evaluate(expr)


# services/node_context/webhook.py
class WebhookContext(BaseNodeContext):
    """
    n8n WebhookContext port
    Context for webhook trigger nodes
    """
    
    def __init__(self, execution_data: dict, node: dict, request: dict):
        super().__init__(execution_data, node)
        self._request = request
    
    def getRequestObject(self) -> dict:
        """Get raw HTTP request"""
        return self._request
    
    def getHeader(self, name: str, default: str = None) -> str:
        """Get request header"""
        return self._request.get('headers', {}).get(name.lower(), default)
    
    def getBody(self) -> Any:
        """Get request body (parsed)"""
        return self._request.get('body')
    
    def getQueryParam(self, name: str, default: str = None) -> str:
        """Get query parameter"""
        return self._request.get('query', {}).get(name, default)
    
    def respond(self, options: dict):
        """Send webhook response"""
        # options: { statusCode, body, headers }
        pass


# services/node_context/trigger.py  
class TriggerContext(BaseNodeContext):
    """
    n8n SupplyDataContext port
    Context for trigger nodes (polling/webhook)
    """
    
    def __init__(self, execution_data: dict, node: dict):
        super().__init__(execution_data, node)
        self._data_items = []
    
    def emit(self, data: list):
        """Emit data to workflow"""
        self._data_items.extend(data)
    
    def emitError(self, error: Exception):
        """Emit error"""
        self._data_items.append({'error': str(error)})
    
    def getDataItems(self) -> list:
        """Get all emitted items"""
        return self._data_items


# services/node_context/credentials.py
class CredentialsContext:
    """
    Handles credential loading and decryption
    Reference: ../n8n-master/packages/core/src/credentials.ts
    """
    
    def __init__(self, encryption_key: str):
        self._encryption_key = encryption_key
        self._cache = {}  # Redis fallback
    
    def load(self, credential_id: int, credential_type: str) -> dict:
        """Load and decrypt credential"""
        
        # 1. Check cache (Redis or memory)
        cache_key = f"{credential_type}:{credential_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 2. Load from database
        cred = db.session.get(Credential, credential_id)
        if not cred or cred.type != credential_type:
            raise CredentialNotFoundError(credential_id, credential_type)
        
        # 3. Decrypt using AES-256-GCM
        decrypted = self._decrypt(cred.encrypted_data)
        
        # 4. Cache for 1 hour
        self._cache[cache_key] = decrypted
        
        return decrypted
    
    def _decrypt(self, data: str) -> dict:
        """AES-256-GCM decryption"""
        # Uses self._encryption_key from environment
        pass
```

### Node Helpers (n8n-style)

```python
# services/node_context/helpers.py
class NodeHelpers:
    """
    n8n: IExecuteFunctions helpers
    Reference: packages/core/src/execution-engine/node-execution-context/utils/
    """
    
    def __init__(self, context: ExecuteContext):
        self._context = context
    
    def httpRequest(self, options: dict) -> Any:
        """Authenticated HTTP request with automatic credential injection"""
        # 1. Get credentials if auth configured
        # 2. Apply auth headers (Bearer, Basic, OAuth2)
        # 3. Execute request
        # 4. Handle pagination automatically
        pass
    
    def requestWithCredentials(self, options: dict) -> Any:
        """HTTP request using node's attached credentials"""
        pass
    
    def jsonParse(self, json_str: str) -> Any:
        """Safe JSON parsing"""
        return json.loads(json_str)
    
    def returnJsonArray(self, *args) -> list:
        """Convert arguments to JSON array format"""
        return [{'json': arg} for arg in args]
    
    def copyInputItems(self, items: list, properties: list) -> list:
        """Copy items with specified properties only"""
        pass
    
    def binaryToString(self, binary_data: bytes, encoding: str = 'utf-8') -> str:
        """Convert binary to string"""
        return binary_data.decode(encoding)
    
    def getInputConnectionData(self, node: str, index: int) -> Any:
        """Get data from specific node output"""
        pass
```

### Phase 3 Effort Estimation

| Task | Best Case | Expected | Worst Case |
|------|-----------|----------|------------|
| BaseNodeContext | 2 days | 3 days | 5 days |
| ExecuteContext | 3 days | 5 days | 8 days |
| WebhookContext | 2 days | 3 days | 5 days |
| TriggerContext | 2 days | 3 days | 5 days |
| CredentialsContext | 3 days | 5 days | 10 days |
| NodeHelpers | 5 days | 8 days | 15 days |
| HTTP helpers | 3 days | 5 days | 8 days |
| Tests | 5 days | 10 days | 20 days |
| **TOTAL** | **25 days** | **42 days** | **76 days** |

---

## Phase 4: Frontend UI (NEW SECTION)

### Reference: n8n Frontend

**Location:** `../n8n-master/packages/editor-ui/`
- Vue.js (not React)
- Vue Flow for canvas
- Monaco Editor for code/expressions

### Sadas Tech Stack

```
Frontend: React 19 + ReactFlow + Monaco Editor
Backend:  Flask + Flask-SocketIO
Real-time: WebSocket for execution state
```

### Component Architecture

```tsx
// vite/workflow-ui/src/
# ├── components/
# │   ├── canvas/
# │   │   ├── WorkflowCanvas.tsx      # Main ReactFlow wrapper
# │   │   ├── CanvasToolbar.tsx      # Zoom, fit, undo/redo
# │   │   ├── MiniMap.tsx            # Navigation minimap
# │   │   └── CanvasControls.tsx     # Fit, lock, align
# │   ├── nodes/
# │   │   ├── BaseNode.tsx           # Shared node wrapper
# │   │   ├── TriggerNode.tsx        # Trigger (blue)
# │   │   ├── ActionNode.tsx         # Action (green)
# │   │   ├── ConditionNode.tsx      # Condition (yellow)
# │   │   └── OutputNode.tsx         # Output/Result
# │   ├── sidebar/
# │   │   ├── NodeLibrary.tsx        # Left panel - node palette
# │   │   ├── NodeConfig.tsx         # Right panel - node settings
# │   │   └── WorkflowSettings.tsx   # Workflow-level settings
# │   ├── editor/
# │   │   ├── ExpressionEditor.tsx   # Monaco-based expression editor
# │   │   ├── CodeEditor.tsx         # Python/JS code editor
# │   │   └── JsonEditor.tsx         # JSON editor
# │   └── execution/
# │       ├── ExecutionOverlay.tsx   # Live execution state
# │       ├── NodeStatusBadge.tsx    # Running/success/error icons
# │       └── ExecutionHistory.tsx   # Past executions
# ├── stores/
# │   ├── workflowStore.ts            # Zustand - workflow state
# │   ├── executionStore.ts          # Execution state
# │   └── nodeLibraryStore.ts        # Available nodes
# ├── hooks/
# │   ├── useWebSocket.ts            # SocketIO connection
# │   ├── useExpressionParser.ts     # Client-side expression preview
# │   └── useWorkflowExecution.ts    # Execute workflow
# └── api/
#     └── workflows.ts               # API client
```

### ReactFlow Custom Node Implementation

```tsx
// vite/workflow-ui/src/components/nodes/BaseNode.tsx
interface BaseNodeProps {
  id: string;
  data: NodeData;
  selected: boolean;
  type: 'trigger' | 'action' | 'condition' | 'output';
}

export const BaseNode: React.FC<BaseNodeProps> = ({ id, data, selected, type }) => {
  const colorMap = {
    trigger: 'bg-blue-500',
    action: 'bg-green-500', 
    condition: 'bg-yellow-500',
    output: 'bg-purple-500',
  };
  
  return (
    <div className={`
      ${colorMap[type]} rounded-lg shadow-lg border-2
      ${selected ? 'border-blue-400 ring-2 ring-blue-200' : 'border-transparent'}
      min-w-[200px] max-w-[300px]
    `}>
      {/* Node Header */}
      <div className="px-3 py-2 border-b border-white/20">
        <div className="text-white font-medium">{data.label}</div>
        <div className="text-white/70 text-xs">{data.subtype}</div>
      </div>
      
      {/* Node Body */}
      <div className="px-3 py-2">
        {/* Config summary */}
        {data.config && (
          <div className="text-white/80 text-sm">
            {Object.entries(data.config).slice(0, 2).map(([k, v]) => (
              <div key={k} className="truncate">{k}: {String(v).slice(0, 20)}</div>
            ))}
          </div>
        )}
      </div>
      
      {/* Status Indicator (WebSocket) */}
      <ExecutionStatus id={id} />
      
      {/* Handles */}
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />
    </div>
  );
};
```

### Expression Editor Integration

```tsx
// vite/workflow-ui/src/components/editor/ExpressionEditor.tsx
import MonacoEditor from '@monaco-editor/react';

interface ExpressionEditorProps {
  value: string;
  onChange: (value: string) => void;
  context: Record<string, any>;  // $vars, $node, etc.
}

export const ExpressionEditor: React.FC<ExpressionEditorProps> = ({
  value, onChange, context
}) => {
  // Autocomplete for expression variables
  const completions = generateCompletions(context);
  
  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="bg-gray-100 px-3 py-1 text-xs text-gray-500">
        Expression Editor (Ctrl+Space for autocomplete)
      </div>
      <MonacoEditor
        height="100px"
        language="expression"  // Custom language mode
        value={value}
        onChange={(v) => onChange(v || '')}
        options={{
          minimap: { enabled: false },
          lineNumbers: 'off',
          wordWrap: 'on',
          fontSize: 13,
        }}
        beforeMount={(monaco) => {
          // Register expression language
          monaco.languages.registerCompletionItemProvider('expression', {
            provideCompletionItems: () => completions
          });
        }}
      />
    </div>
  );
};
```

### WebSocket Execution State

```tsx
// vite/workflow-ui/src/stores/executionStore.ts
import { create } from 'zustand';
import { io, Socket } from 'socket.io-client';

interface ExecutionState {
  status: 'idle' | 'running' | 'paused' | 'error';
  nodeStates: Record<string, 'pending' | 'running' | 'success' | 'error'>;
  currentNode: string | null;
}

export const useExecutionStore = create<ExecutionState>((set) => {
  const socket = io('/workflow');
  
  socket.on('node:start', (data: { nodeId: string }) => {
    set((state) => ({
      nodeStates: { ...state.nodeStates, [data.nodeId]: 'running' },
      currentNode: data.nodeId,
    }));
  });
  
  socket.on('node:complete', (data: { nodeId: string, status: string }) => {
    set((state) => ({
      nodeStates: { ...state.nodeStates, [data.nodeId]: data.status },
      currentNode: null,
    }));
  });
  
  socket.on('execution:complete', () => {
    set({ status: 'idle', currentNode: null });
  });
  
  return {
    status: 'idle',
    nodeStates: {},
    currentNode: null,
  };
});
```

### Node Status Badge

```tsx
// vite/workflow-ui/src/components/execution/NodeStatusBadge.tsx
export const ExecutionStatus: React.FC<{ id: string }> = ({ id }) => {
  const state = useExecutionStore((s) => s.nodeStates[id]);
  
  const statusConfig = {
    pending: { icon: Circle, color: 'text-gray-400', pulse: false },
    running: { icon: Loader2, color: 'text-blue-500', pulse: true },
    success: { icon: CheckCircle, color: 'text-green-500', pulse: false },
    error: { icon: XCircle, color: 'text-red-500', pulse: false },
  };
  
  const config = statusConfig[state || 'pending'];
  
  return (
    <div className={`absolute -top-2 -right-2 ${config.color}`}>
      <config.icon className={config.pulse ? 'animate-spin' : ''} size={16} />
    </div>
  );
};
```

### Node Library (Drag & Drop)

```tsx
// vite/workflow-ui/src/components/sidebar/NodeLibrary.tsx
const TRIGGER_NODES = [
  { type: 'manual', label: 'Manual Trigger', icon: Play },
  { type: 'schedule', label: 'Schedule', icon: Clock },
  { type: 'webhook', label: 'Webhook', icon: Globe },
  { type: 'email', label: 'Email Trigger', icon: Mail },
];

const ACTION_NODES = [
  { type: 'http_request', label: 'HTTP Request', icon: Send },
  { type: 'code', label: 'Code', icon: Code },
  { type: 'condition', label: 'IF', icon: GitBranch },
  { type: 'loop', label: 'Loop', icon: Repeat },
  { type: 'notify', label: 'Notify', icon: Bell },
];

export const NodeLibrary: React.FC = () => {
  const onDragStart = (event: DragEvent, nodeType: string) => {
    event.dataTransfer.setData('application/reactflow', nodeType);
    event.dataTransfer.effectAllowed = 'move';
  };
  
  return (
    <div className="w-64 bg-white border-r overflow-y-auto">
      <div className="p-3 border-b">
        <h3 className="font-medium">Triggers</h3>
        {TRIGGER_NODES.map((node) => (
          <div
            key={node.type}
            draggable
            onDragStart={(e) => onDragStart(e, node.type)}
            className="flex items-center gap-2 p-2 hover:bg-gray-100 rounded cursor-grab"
          >
            <node.icon size={16} />
            <span className="text-sm">{node.label}</span>
          </div>
        ))}
      </div>
      
      <div className="p-3 border-b">
        <h3 className="font-medium">Actions</h3>
        {ACTION_NODES.map((node) => (
          <div
            key={node.type}
            draggable
            onDragStart={(e) => onDragStart(e, node.type)}
            className="flex items-center gap-2 p-2 hover:bg-gray-100 rounded cursor-grab"
          >
            <node.icon size={16} />
            <span className="text-sm">{node.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
```

### Phase 4 Effort Estimation

| Task | Best Case | Expected | Worst Case |
|------|-----------|----------|------------|
| ReactFlow Canvas Setup | 2 days | 3 days | 5 days |
| Custom Nodes (4 types) | 3 days | 5 days | 8 days |
| Node Library Sidebar | 2 days | 3 days | 5 days |
| Node Config Panel | 3 days | 5 days | 8 days |
| Expression Editor (Monaco) | 3 days | 5 days | 10 days |
| WebSocket State Sync | 2 days | 3 days | 5 days |
| Execution Status UI | 2 days | 3 days | 5 days |
| Drag & Drop | 1 day | 2 days | 3 days |
| **TOTAL** | **18 days** | **29 days** | **49 days** |

---

## COMPLETE Effort Estimation Summary

| Phase | Best | Expected | Worst |
|-------|------|----------|-------|
| Phase 1: Core Engine | 10 days | 18 days | 30 days |
| Phase 2: Expression Engine | 15 days | 27 days | 52 days |
| Phase 3: Node Context | 25 days | 42 days | 76 days |
| Phase 4: Frontend UI | 18 days | 29 days | 49 days |
| Phase 5: Credentials | 8 days | 14 days | 25 days |
| Phase 6: Advanced Features | 10 days | 18 days | 35 days |
| Phase 7: Testing | 15 days | 25 days | 45 days |
| **TOTAL** | **101 days** | **173 days** | **312 days** |

---

## Recommended Implementation Order

```
Month 1:
├── Phase 1: Core Engine (DirectedGraph, CycleDetection, PartialExec)
└── Phase 4: Frontend Canvas (basic ReactFlow, no execution)

Month 2:
├── Phase 2: Expression Engine (Jinja2 + Security layer)
└── Phase 3: Node Context (ExecuteContext only)

Month 3:
├── Phase 4: Frontend Full (Expression editor, WebSocket)
├── Phase 5: Credentials
└── Phase 3: Webhook/Trigger contexts

Month 4:
├── Phase 6: Binary data, Event bus
└── Phase 7: Testing & Polish
```

---

## Technology Decisions Summary

| Decision | Choice | Reason |
|----------|--------|--------|
| Database | PostgreSQL | Concurrent execution, row-level locking |
| Expression | Jinja2 + AST validation | n8n syntax compatibility |
| Code Sandbox | Subprocess + timeout | Memory/CPU isolation |
| Credentials | DB (AES-256) + Redis cache | Security + performance |
| Frontend | React + ReactFlow | Current stack compatibility |
| Real-time | Flask-SocketIO | Existing backend |
| Expression Editor | Monaco | VS Code quality |
