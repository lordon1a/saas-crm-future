"""
Workflow Graph Runner — n8n-style Execution Engine
====================================================
This is the core orchestration layer that executes workflows as directed graphs.

Architecture:
1. Parse workflow JSON (nodes + edges)
2. Build execution graph (adjacency list)
3. Topological sort for execution order
4. Execute nodes sequentially, passing data between them
5. Handle branches (true/false outputs from condition nodes)
6. Manage state, retries, and error recovery

Key Design Decisions:
- State is passed between nodes as a context dict
- Each node can read from context and write to context
- Condition nodes produce a boolean output that determines which branch executes
- Error handling is per-node with configurable retry logic
"""
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict, deque
from enum import Enum

logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class ExecutionMode(Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


class WorkflowGraphRunner:
    """
    Core execution engine for n8n-style workflows.
    
    This class takes a workflow definition (nodes + edges) and executes it
    as a directed acyclic graph (DAG), passing data between nodes.
    """
    
    # Node type categories
    TRIGGER_NODES = {
        'contact_created', 'contact_updated', 'contact_tag_added', 'contact_no_activity',
        'deal_created', 'deal_stage_changed', 'deal_won', 'deal_lost',
        'deal_amount_changed', 'deal_no_activity',
        'task_created', 'task_completed', 'deal_close_date_approaching',
        'manual', 'schedule', 'webhook_trigger',
    }
    
    CONDITION_NODES = {
        'check_field', 'check_score', 'if', 'if_else', 'loop_over_items',
        'error_trigger', 'split_in_batches',
    }
    
    ACTION_NODES = {
        'create_task', 'send_email', 'send_whatsapp', 'notify_owner',
        'update_deal_stage', 'update_deal_field', 'update_contact_field',
        'add_tag', 'remove_tag', 'assign_owner',
        'create_note', 'webhook', 'delay', 'wait', 'http_request',
        'find_records', 'delete_record',
        'code', 'wait_until', 'set_node', 'ai_agent', 'call_workflow',
    }
    
    def __init__(self):
        self.node_handlers = {}
        self._register_handlers()
    
    def _register_handlers(self):
        """Register all node handlers"""
        from services.workflow_node_handlers import NodeHandlerRegistry
        self.node_handlers = NodeHandlerRegistry.get_all_handlers()
    
    def execute_workflow(self, workflow_id: int, canvas_data: Dict, 
                         entity: Any, context: Dict = None,
                         execution_id: int = None, dry_run: bool = False,
                         workspace_id: int = None) -> Dict:
        """
        Main entry point for workflow execution.
        
        Args:
            workflow_id: The workflow ID
            canvas_data: {nodes: [...], edges: [...]} from ReactFlow
            entity: The entity that triggered the workflow (Deal, Contact, etc.)
            context: Additional context from the trigger
            execution_id: Optional execution log ID
        
        Returns:
            dict with execution results
        """
        context = context or {}
        start_time = datetime.utcnow()
        
        execution_result = {
            'workflow_id': workflow_id,
            'execution_id': execution_id,
            'status': NodeStatus.RUNNING.value,
            'started_at': start_time.isoformat(),
            'completed_at': None,
            'node_results': [],
            'error': None,
            'duration_ms': 0,
        }
        
        try:
            # Step 1: Parse and validate canvas data
            graph = self._build_graph(canvas_data)
            
            # Step 2: Initialize execution context
            exec_context = self._init_context(entity, context)
            
            # Step 3: Find trigger node and validate
            trigger_node = self._find_trigger_node(graph)
            if not trigger_node:
                raise ValueError("No trigger node found in workflow")
            
            # Step 4: Execute the graph
            node_results = self._execute_graph(graph, exec_context)
            
            # Step 5: Compile results
            execution_result['node_results'] = node_results
            execution_result['status'] = self._determine_final_status(node_results)
            execution_result['completed_at'] = datetime.utcnow().isoformat()
            execution_result['duration_ms'] = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )
            
            logger.info(
                f"Workflow {workflow_id} executed: "
                f"status={execution_result['status']}, "
                f"nodes={len(node_results)}, "
                f"duration={execution_result['duration_ms']}ms"
            )
            
            # Track usage
            if not dry_run:
                self._track_usage(workspace_id, node_results, execution_result)
            
        except Exception as e:
            logger.error(f"Workflow {workflow_id} execution failed: {e}", exc_info=True)
            execution_result['status'] = NodeStatus.FAILED.value
            execution_result['error'] = str(e)
            execution_result['completed_at'] = datetime.utcnow().isoformat()
        
        return execution_result
    
    def _build_graph(self, canvas_data: Dict) -> Dict:
        """
        Build execution graph from canvas data.
        
        Returns:
            {
                'nodes': {node_id: node_data},
                'adjacency': {node_id: [child_node_ids]},
                'reverse_adj': {node_id: [parent_node_ids]},
                'edges': [{source, target, sourceHandle, targetHandle}],
            }
        """
        nodes = {}
        adjacency = defaultdict(list)
        reverse_adj = defaultdict(list)
        edges = []
        
        for node in canvas_data.get('nodes', []):
            node_id = node['id']
            nodes[node_id] = node.get('data', {})
        
        for edge in canvas_data.get('edges', []):
            source = edge['source']
            target = edge['target']
            source_handle = edge.get('sourceHandle')
            target_handle = edge.get('targetHandle')
            
            adjacency[source].append({
                'target': target,
                'sourceHandle': source_handle,
                'targetHandle': target_handle,
            })
            reverse_adj[target].append(source)
            edges.append(edge)
        
        return {
            'nodes': nodes,
            'adjacency': dict(adjacency),
            'reverse_adj': dict(reverse_adj),
            'edges': edges,
        }
    
    def _init_context(self, entity: Any, trigger_context: Dict) -> Dict:
        """
        Initialize execution context with entity data and trigger context.
        
        The context is passed between nodes and accumulates data.
        """
        context = {
            'entity': self._entity_to_dict(entity),
            'entity_type': entity.__class__.__name__.lower(),
            'entity_id': getattr(entity, 'id', None),
            'workspace_id': getattr(entity, 'workspace_id', None),
            'trigger': trigger_context or {},
            'variables': {},  # Node outputs stored here
            'metadata': {
                'execution_id': str(uuid.uuid4()),
                'started_at': datetime.utcnow().isoformat(),
            },
        }
        
        # Add entity-specific fields to context root for easy access
        if hasattr(entity, 'to_dict'):
            try:
                entity_dict = entity.to_dict()
                context['entity'].update(entity_dict)
            except:
                pass
        
        return context
    
    def _entity_to_dict(self, entity: Any) -> Dict:
        """Convert entity to dict, handling SQLAlchemy models"""
        result = {}
        for col in entity.__table__.columns:
            value = getattr(entity, col.name, None)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[col.name] = value
        return result
    
    def _find_trigger_node(self, graph: Dict) -> Optional[Dict]:
        """Find the trigger node in the graph"""
        for node_id, node_data in graph['nodes'].items():
            node_type = node_data.get('nodeType') or node_data.get('node_type')
            if node_type == 'trigger':
                return {'id': node_id, **node_data}
        return None
    
    def _execute_graph(self, graph: Dict, context: Dict) -> List[Dict]:
        """
        Execute the graph using BFS with branch handling.
        
        This is the core orchestration logic:
        1. Start from trigger node
        2. Execute each node
        3. Based on node output, determine which children to execute
        4. Handle condition branches (true/false paths)
        5. Handle loops and batches
        """
        results = []
        visited = set()
        queue = deque()
        
        # Find trigger node
        trigger_node = self._find_trigger_node(graph)
        if not trigger_node:
            raise ValueError("No trigger node found")
        
        # Start with trigger
        queue.append({
            'node_id': trigger_node['id'],
            'branch': None,  # 'true', 'false', or None
            'depth': 0,
        })
        
        max_depth = 100  # Prevent infinite loops
        max_nodes = 50   # Prevent runaway executions
        
        while queue and len(results) < max_nodes:
            item = queue.popleft()
            node_id = item['node_id']
            branch = item['branch']
            depth = item['depth']
            
            if node_id in visited:
                continue
            
            if depth > max_depth:
                logger.warning(f"Max depth exceeded at node {node_id}")
                continue
            
            visited.add(node_id)
            node_data = graph['nodes'].get(node_id, {})
            
            # Execute the node
            node_result = self._execute_node(node_id, node_data, context, branch)
            results.append(node_result)
            
            # Determine which children to execute
            children = graph['adjacency'].get(node_id, [])
            
            if node_result['status'] == NodeStatus.FAILED.value:
                # Check error handling config
                error_config = node_data.get('config', {}).get('on_error_action', 'stop')
                if error_config == 'stop':
                    logger.warning(f"Node {node_id} failed, stopping execution")
                    continue
                elif error_config == 'continue':
                    # Continue with children
                    pass
                elif error_config == 'retry':
                    # Retry logic handled in _execute_node
                    pass
            
            # Add children to queue
            for child_edge in children:
                child_id = child_edge['target']
                source_handle = child_edge.get('sourceHandle')
                
                # For condition nodes, only follow the matching branch
                if node_result.get('output') and 'condition_result' in node_result['output']:
                    condition_result = node_result['output']['condition_result']
                    if source_handle == 'true' and condition_result:
                        queue.append({'node_id': child_id, 'branch': 'true', 'depth': depth + 1})
                    elif source_handle == 'false' and not condition_result:
                        queue.append({'node_id': child_id, 'branch': 'false', 'depth': depth + 1})
                    elif source_handle is None:
                        # Default edge from condition - follow if true
                        if condition_result:
                            queue.append({'node_id': child_id, 'branch': None, 'depth': depth + 1})
                else:
                    # Non-condition node - follow all children
                    queue.append({'node_id': child_id, 'branch': None, 'depth': depth + 1})
        
        return results
    
    def _execute_node(self, node_id: str, node_data: Dict, context: Dict, 
                      branch: str = None) -> Dict:
        """
        Execute a single node with retry logic.
        
        Returns:
            {
                'node_id': str,
                'node_type': str,
                'subtype': str,
                'status': 'success' | 'failed' | 'skipped',
                'started_at': str,
                'completed_at': str,
                'duration_ms': int,
                'output': dict,
                'error': str (optional),
                'retries': int,
            }
        """
        subtype = node_data.get('subtype', '')
        node_type = node_data.get('nodeType') or node_data.get('node_type', 'action')
        config = node_data.get('config', {})
        
        result = {
            'node_id': node_id,
            'node_type': node_type,
            'subtype': subtype,
            'status': NodeStatus.PENDING.value,
            'started_at': datetime.utcnow().isoformat(),
            'completed_at': None,
            'duration_ms': 0,
            'output': {},
            'error': None,
            'retries': 0,
        }
        
        # Skip if branch doesn't match
        if branch == 'skipped':
            result['status'] = NodeStatus.SKIPPED.value
            result['completed_at'] = datetime.utcnow().isoformat()
            return result
        
        start_time = time.time()
        result['status'] = NodeStatus.RUNNING.value
        
        # Get retry config
        max_retries = config.get('max_retries', 0)
        retry_delay = config.get('retry_delay', 1)
        
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                result['retries'] = attempt
                
                # Get handler for this node type
                handler = self.node_handlers.get(subtype)
                if not handler:
                    # Try to find a generic handler
                    handler = self._get_fallback_handler(node_type, subtype)
                
                if not handler:
                    raise ValueError(f"No handler found for node type: {subtype}")
                
                # Execute the handler
                output = handler(node_data, context, config)
                
                result['output'] = output
                result['status'] = NodeStatus.SUCCESS.value
                
                # Store output in context for downstream nodes
                output_var = config.get('output_variable', f'{subtype}_{node_id}')
                context['variables'][output_var] = output
                
                break  # Success, exit retry loop
                
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Node {node_id} ({subtype}) attempt {attempt + 1} failed: {e}"
                )
                
                if attempt < max_retries:
                    time.sleep(retry_delay)
        
        end_time = time.time()
        result['duration_ms'] = int((end_time - start_time) * 1000)
        result['completed_at'] = datetime.utcnow().isoformat()
        
        if result['status'] != NodeStatus.SUCCESS.value:
            result['status'] = NodeStatus.FAILED.value
            result['error'] = last_error
        
        return result
    
    def execute_graph(self, canvas_data: Dict, context: Dict,
                      dry_run: bool = False) -> Dict:
        """
        Execute a workflow graph using a pre-built context dict.
        Used by CRM event triggers (_execute_graph_workflow) and the
        run-manual / test-run endpoints.

        Unlike execute_workflow(), this method does NOT accept a raw entity
        object — the caller is responsible for building the context dict.
        """
        start_time = datetime.utcnow()
        execution_result = {
            'status': NodeStatus.RUNNING.value,
            'started_at': start_time.isoformat(),
            'completed_at': None,
            'node_results': [],
            'error': None,
            'duration_ms': 0,
        }

        try:
            graph = self._build_graph(canvas_data)

            trigger_node = self._find_trigger_node(graph)
            if not trigger_node:
                raise ValueError("No trigger node found in workflow")

            if dry_run:
                # Dry-run: just report what would execute, don't call action handlers
                node_results = []
                for node_id, node_data in graph['nodes'].items():
                    node_results.append({
                        'node_id': node_id,
                        'node_type': node_data.get('nodeType', 'unknown'),
                        'subtype': node_data.get('subtype', ''),
                        'status': 'skipped',
                        'output': {},
                        'error': None,
                        'duration_ms': 0,
                    })
            else:
                # Make sure context has required keys
                context.setdefault('variables', {})
                node_results = self._execute_graph(graph, context)

            execution_result['node_results'] = node_results
            execution_result['status'] = self._determine_final_status(node_results) if not dry_run else 'completed'
            execution_result['completed_at'] = datetime.utcnow().isoformat()
            execution_result['duration_ms'] = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )

        except Exception as e:
            logger.error(f"execute_graph failed: {e}", exc_info=True)
            execution_result['status'] = NodeStatus.FAILED.value
            execution_result['error'] = str(e)
            execution_result['completed_at'] = datetime.utcnow().isoformat()

        return execution_result

    def _get_fallback_handler(self, node_type: str, subtype: str):
        """Get a fallback handler based on node type"""
        from services.workflow_node_handlers import (
            TriggerHandler, ConditionHandler, ActionHandler
        )
        
        if subtype in self.TRIGGER_NODES or node_type == 'trigger':
            return TriggerHandler.handle
        elif subtype in self.CONDITION_NODES or node_type == 'condition':
            return ConditionHandler.handle
        elif subtype in self.ACTION_NODES or node_type == 'action':
            return ActionHandler.handle
        return None
    
    def _determine_final_status(self, node_results: List[Dict]) -> str:
        """Determine overall execution status"""
        if not node_results:
            return NodeStatus.FAILED.value
        
        failed = [r for r in node_results if r['status'] == NodeStatus.FAILED.value]
        if failed:
            return NodeStatus.FAILED.value
        
        return NodeStatus.SUCCESS.value
    
    def resolve_template(self, template: str, context: Dict) -> str:
        """
        Resolve template variables in a string.
        
        Supports:
        - {{entity.field_name}}
        - {{trigger.field_name}}
        - {{variables.var_name}}
        - {{contact.first_name}} (shorthand for entity.first_name)
        """
        if not template or not isinstance(template, str):
            return template
        
        import re
        
        def replace_var(match):
            var_path = match.group(1).strip()
            return str(self._resolve_path(var_path, context))
        
        # Match {{variable}} patterns
        pattern = r'\{\{([^}]+)\}\}'
        return re.sub(pattern, replace_var, template)
    
    def _resolve_path(self, path: str, context: Dict) -> Any:
        """Resolve a dotted path against context"""
        parts = path.split('.')
        current = context
        
        for part in parts:
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(part)
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
        
        return current


    @staticmethod
    def _track_usage(workspace_id: int, node_results: list, execution_result: dict):
        """Track workflow execution usage for credits/limits dashboard"""
        from models_crm import WorkflowUsage
        from models import db
        
        now = datetime.utcnow()
        year = now.year
        month = now.month
        
        usage = WorkflowUsage.query.filter_by(
            workspace_id=workspace_id,
            year=year,
            month=month,
        ).first()
        
        if not usage:
            usage = WorkflowUsage(
                workspace_id=workspace_id,
                year=year,
                month=month,
                total_executions=0,
                total_actions=0,
                total_errors=0,
                total_duration_ms=0,
                action_breakdown='{}',
            )
        
        usage.total_executions += 1
        usage.total_duration_ms += execution_result.get('duration_ms', 0)
        
        # Count actions and errors
        action_breakdown = {}
        try:
            import json
            action_breakdown = json.loads(usage.action_breakdown) if usage.action_breakdown else {}
        except:
            pass
        
        for nr in node_results:
            node_type = nr.get('node_type', 'unknown')
            subtype = nr.get('subtype', '')
            status = nr.get('status', '')
            
            if node_type == 'action':
                usage.total_actions += 1
                key = subtype or 'unknown'
                action_breakdown[key] = action_breakdown.get(key, 0) + 1
            
            if status == 'failed':
                usage.total_errors += 1
        
        import json
        usage.action_breakdown = json.dumps(action_breakdown)
        
        try:
            db.session.add(usage)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.warning(f"Failed to track workflow usage: {e}")


# ─── Template Resolution Utility ───────────────────────────────────────

def resolve_template_string(template: str, entity: Any = None, 
                            context: Dict = None) -> str:
    """
    Standalone template resolution for backward compatibility.
    Used by existing workflow_service.py methods.
    """
    if not template or not isinstance(template, str):
        return template
    
    runner = WorkflowGraphRunner()
    
    # Build context
    ctx = {
        'entity': {},
        'trigger': context or {},
        'variables': {},
    }
    
    if entity:
        for col in entity.__table__.columns:
            value = getattr(entity, col.name, None)
            if isinstance(value, datetime):
                value = value.isoformat()
            ctx['entity'][col.name] = value
        
        # Also add shorthand access
        entity_type = entity.__class__.__name__.lower()
        ctx[entity_type] = ctx['entity']
        ctx['contact'] = ctx['entity']  # Alias
        ctx['deal'] = ctx['entity']     # Alias
    
    return runner.resolve_template(template, ctx)
