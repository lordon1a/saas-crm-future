"""
Workflow API Routes
===================
REST API endpoints for workflow automation management.

Prefix: /api/v1/workflows
"""
import logging
from flask import Blueprint, request, jsonify, session
from models import db
from models_crm import (
    WorkflowAutomation, WorkflowCondition, WorkflowAction,
    WorkflowExecution, WorkflowExecutionQueue
)
from services.workflow_service import WorkflowService
from functools import wraps
import json
from datetime import datetime

logger = logging.getLogger(__name__)

bp = Blueprint('workflows', __name__, url_prefix='/api/v1/workflows')

VALID_RE_ENROLLMENT_MODES = {
    'always',
    'never',
    'once_per_day',
    'once_per_week',
}


def login_required_api(f):
    """Decorator for API authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'error': 'Unauthorized'}), 401
        if not session.get('workspace_id'):
            return jsonify({'error': 'Workspace context missing'}), 401
        return f(*args, **kwargs)
    return decorated


# ═══════════════════════════════════════════════════════════════════════════════
# WORKFLOW CRUD
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route('', methods=['GET'])
@login_required_api
def list_workflows():
    """List all workflows for the workspace"""
    workspace_id = session.get('workspace_id')
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    
    # Filter options
    is_active = request.args.get('is_active')
    trigger_type = request.args.get('trigger_type')
    
    query = WorkflowAutomation.query.filter_by(workspace_id=workspace_id)
    
    if is_active is not None:
        query = query.filter_by(is_active=is_active.lower() == 'true')
    
    if trigger_type:
        query = query.filter_by(trigger_type=trigger_type)
    
    pagination = query.order_by(WorkflowAutomation.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    result = []
    for workflow in pagination.items:
        workflow_data = workflow.to_dict()
        # Add conditions and actions count
        workflow_data['conditions_count'] = workflow.conditions.count()
        workflow_data['actions_count'] = workflow.actions.count()
        result.append(workflow_data)
    
    return jsonify({
        'workflows': result,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page
    }), 200


@bp.route('', methods=['POST'])
@login_required_api
def create_workflow():
    """Create a new workflow"""
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json()
    
    # Validate required fields
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Workflow name is required'}), 400
    
    trigger_type = data.get('trigger_type')
    if not trigger_type:
        return jsonify({'error': 'Trigger type is required'}), 400
    
    if trigger_type not in WorkflowService.TRIGGER_TYPES:
        return jsonify({'error': f'Invalid trigger type: {trigger_type}'}), 400

    re_enrollment_mode = data.get('re_enrollment_mode', 'always')
    if re_enrollment_mode not in VALID_RE_ENROLLMENT_MODES:
        return jsonify({'error': f'Invalid re_enrollment_mode: {re_enrollment_mode}'}), 400
    
    try:
        # Create workflow
        workflow = WorkflowAutomation(
            workspace_id=workspace_id,
            name=name,
            description=data.get('description', ''),
            is_active=data.get('is_active', True),
            trigger_type=trigger_type,
            trigger_config=json.dumps(data.get('trigger_config', {})),
            re_enrollment_mode=re_enrollment_mode,
            condition_logic=data.get('condition_logic', 'AND'),
            canvas_data=json.dumps(data.get('canvas_data')) if data.get('canvas_data') else None,
            created_by=user_id
        )
        db.session.add(workflow)
        db.session.flush()
        
        # Add conditions
        conditions = data.get('conditions', [])
        for i, cond in enumerate(conditions):
            condition = WorkflowCondition(
                workflow_id=workflow.id,
                workspace_id=workspace_id,
                field_name=cond.get('field_name', ''),
                operator=cond.get('operator', 'equals'),
                value=str(cond.get('value', '')),
                order_index=i
            )
            db.session.add(condition)
        
        # Add actions
        actions = data.get('actions', [])
        for i, act in enumerate(actions):
            action = WorkflowAction(
                workflow_id=workflow.id,
                workspace_id=workspace_id,
                action_type=act.get('action_type', ''),
                action_config=json.dumps(act.get('action_config', {})),
                delay_minutes=act.get('delay_minutes', 0),
                order_index=i
            )
            db.session.add(action)
        
        db.session.commit()
        
        # Return full workflow object so React can use it directly
        workflow_data = workflow.to_dict()
        workflow_data['conditions_count'] = workflow.conditions.count()
        workflow_data['actions_count'] = workflow.actions.count()
        return jsonify(workflow_data), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/<int:workflow_id>', methods=['GET'])
@login_required_api
def get_workflow(workflow_id):
    """Get workflow details including conditions and actions"""
    workspace_id = session.get('workspace_id')
    
    workflow = WorkflowAutomation.query.filter_by(
        id=workflow_id, workspace_id=workspace_id
    ).first()
    
    if not workflow:
        return jsonify({'error': 'Workflow not found'}), 404
    
    workflow_data = workflow.to_dict()
    
    # Add conditions
    workflow_data['conditions'] = [
        c.to_dict() for c in workflow.conditions.order_by(WorkflowCondition.order_index).all()
    ]
    
    # Add actions
    workflow_data['actions'] = [
        a.to_dict() for a in workflow.actions.order_by(WorkflowAction.order_index).all()
    ]
    
    return jsonify(workflow_data), 200


@bp.route('/<int:workflow_id>', methods=['PUT'])
@login_required_api
def update_workflow(workflow_id):
    """Update a workflow"""
    workspace_id = session.get('workspace_id')
    data = request.get_json()
    
    workflow = WorkflowAutomation.query.filter_by(
        id=workflow_id, workspace_id=workspace_id
    ).first()
    
    if not workflow:
        return jsonify({'error': 'Workflow not found'}), 404
    
    try:
        # Update basic fields
        if 'name' in data:
            workflow.name = data['name'].strip()
        if 'description' in data:
            workflow.description = data['description']
        if 'is_active' in data:
            workflow.is_active = data['is_active']
        if 'trigger_type' in data:
            workflow.trigger_type = data['trigger_type']
        if 'trigger_config' in data:
            workflow.trigger_config = json.dumps(data['trigger_config'])
        if 're_enrollment_mode' in data:
            re_enrollment_mode = data.get('re_enrollment_mode')
            if re_enrollment_mode not in VALID_RE_ENROLLMENT_MODES:
                return jsonify({'error': f'Invalid re_enrollment_mode: {re_enrollment_mode}'}), 400
            workflow.re_enrollment_mode = re_enrollment_mode
        if 'condition_logic' in data:
            workflow.condition_logic = data['condition_logic']
        if 'canvas_data' in data:
            workflow.canvas_data = json.dumps(data['canvas_data']) if data['canvas_data'] else None
        
        workflow.updated_at = datetime.utcnow()
        
        # Update conditions if provided
        if 'conditions' in data:
            # Delete existing conditions
            WorkflowCondition.query.filter_by(workflow_id=workflow.id).delete()
            
            # Add new conditions
            for i, cond in enumerate(data['conditions']):
                condition = WorkflowCondition(
                    workflow_id=workflow.id,
                    workspace_id=workspace_id,
                    field_name=cond.get('field_name', ''),
                    operator=cond.get('operator', 'equals'),
                    value=str(cond.get('value', '')),
                    order_index=i
                )
                db.session.add(condition)
        
        # Update actions if provided
        if 'actions' in data:
            # Delete existing actions
            WorkflowAction.query.filter_by(workflow_id=workflow.id).delete()
            
            # Add new actions
            for i, act in enumerate(data['actions']):
                action = WorkflowAction(
                    workflow_id=workflow.id,
                    workspace_id=workspace_id,
                    action_type=act.get('action_type', ''),
                    action_config=json.dumps(act.get('action_config', {})),
                    delay_minutes=act.get('delay_minutes', 0),
                    order_index=i
                )
                db.session.add(action)
        
        db.session.commit()
        
        return jsonify({'status': 'updated'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/<int:workflow_id>', methods=['DELETE'])
@login_required_api
def delete_workflow(workflow_id):
    """Delete a workflow and all its conditions/actions"""
    workspace_id = session.get('workspace_id')
    
    workflow = WorkflowAutomation.query.filter_by(
        id=workflow_id, workspace_id=workspace_id
    ).first()
    
    if not workflow:
        return jsonify({'error': 'Workflow not found'}), 404
    
    try:
        # Cascade delete handles conditions, actions, executions
        db.session.delete(workflow)
        db.session.commit()
        
        return jsonify({'status': 'deleted'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/<int:workflow_id>/toggle', methods=['PATCH'])
@login_required_api
def toggle_workflow(workflow_id):
    """Toggle workflow active status"""
    workspace_id = session.get('workspace_id')
    
    workflow = WorkflowAutomation.query.filter_by(
        id=workflow_id, workspace_id=workspace_id
    ).first()
    
    if not workflow:
        return jsonify({'error': 'Workflow not found'}), 404
    
    workflow.is_active = not workflow.is_active
    workflow.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'id': workflow.id,
        'is_active': workflow.is_active,
        'status': 'toggled'
    }), 200


# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTIONS & STATS
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route('/<int:workflow_id>/executions', methods=['GET'])
@login_required_api
def get_workflow_executions(workflow_id):
    """Get execution history for a workflow"""
    workspace_id = session.get('workspace_id')
    
    workflow = WorkflowAutomation.query.filter_by(
        id=workflow_id, workspace_id=workspace_id
    ).first()
    
    if not workflow:
        return jsonify({'error': 'Workflow not found'}), 404
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    
    pagination = WorkflowExecution.query.filter_by(
        workflow_id=workflow_id
    ).order_by(WorkflowExecution.started_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Enrich executions with entity names
    from models_crm import Contact, Deal, Task
    
    executions = []
    for e in pagination.items:
        e_dict = e.to_dict()
        
        # Try to get entity name
        entity_name = None
        try:
            if e.entity_type == 'contact':
                c = Contact.query.get(e.entity_id)
                entity_name = c.full_name if c and hasattr(c, 'full_name') else (c.name if c else None)
            elif e.entity_type == 'deal':
                d = Deal.query.get(e.entity_id)
                entity_name = d.name if d else None
            elif e.entity_type == 'task':
                t = Task.query.get(e.entity_id)
                entity_name = t.title if t else None
        except:
            pass
        
        e_dict['entity_name'] = entity_name
        executions.append(e_dict)
    
    return jsonify({
        'executions': executions,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page
    }), 200


@bp.route('/<int:workflow_id>/stats', methods=['GET'])
@login_required_api
def get_workflow_stats(workflow_id):
    """Get workflow statistics"""
    workspace_id = session.get('workspace_id')
    
    workflow = WorkflowAutomation.query.filter_by(
        id=workflow_id, workspace_id=workspace_id
    ).first()
    
    if not workflow:
        return jsonify({'error': 'Workflow not found'}), 404
    
    # Get execution stats from last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    recent_executions = WorkflowExecution.query.filter(
        WorkflowExecution.workflow_id == workflow_id,
        WorkflowExecution.started_at >= thirty_days_ago
    ).all()
    
    total = len(recent_executions)
    success = sum(1 for e in recent_executions if e.status == 'completed')
    failed = sum(1 for e in recent_executions if e.status == 'failed')
    
    return jsonify({
        'workflow_id': workflow.id,
        'run_count': workflow.run_count,
        'last_run_at': workflow.last_run_at.isoformat() if workflow.last_run_at else None,
        'recent_total': total,
        'recent_success': success,
        'recent_failed': failed,
        'success_rate': round(success / total * 100, 1) if total > 0 else 0
    }), 200


@bp.route('/<int:workflow_id>/test', methods=['POST'])
@login_required_api
def test_workflow(workflow_id):
    """
    Test a workflow without actually executing actions.
    Returns which entities would be affected.
    """
    workspace_id = session.get('workspace_id')
    data = request.get_json() or {}
    
    workflow = WorkflowAutomation.query.filter_by(
        id=workflow_id, workspace_id=workspace_id
    ).first()
    
    if not workflow:
        return jsonify({'error': 'Workflow not found'}), 404
    
    # Get test entity info
    entity_type = data.get('entity_type', 'deal')
    entity_id = data.get('entity_id')
    
    results = {
        'workflow_id': workflow_id,
        'workflow_name': workflow.name,
        'trigger_type': workflow.trigger_type,
        'test_entity': {'type': entity_type, 'id': entity_id},
        'conditions_met': None,
        'actions_would_execute': [],
        'simulation': True
    }
    
    try:
        # Load test entity
        entity = WorkflowService._load_entity(entity_type, entity_id)
        
        if not entity:
            results['error'] = 'Test entity not found'
            return jsonify(results), 200
        
        # Check conditions
        conditions_met = WorkflowService.evaluate_conditions(workflow, entity, {})
        results['conditions_met'] = conditions_met
        
        if conditions_met:
            # List actions that would execute
            actions = workflow.actions.order_by(WorkflowAction.order_index).all()
            for action in actions:
                results['actions_would_execute'].append({
                    'action_id': action.id,
                    'action_type': action.action_type,
                    'delay_minutes': action.delay_minutes,
                    'config': json.loads(action.action_config) if action.action_config else {}
                })
        
        return jsonify(results), 200
        
    except Exception as e:
        results['error'] = str(e)
        return jsonify(results), 200


# ═══════════════════════════════════════════════════════════════════════════════
# HTTP REQUEST TEST ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route('/http-test', methods=['POST'])
@login_required_api
def test_http_request():
    """
    Test an HTTP request configuration.
    Used to test http_request action nodes before saving.
    """
    import httpx
    import base64
    
    data = request.get_json() or {}
    
    url = data.get('url', '')
    method = data.get('method', 'GET').upper()
    auth_type = data.get('auth_type', 'none')
    header_key = data.get('header_key', '')
    header_value = data.get('header_value', '')
    body = data.get('body', '')
    timeout = data.get('timeout', 30)
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    headers = {}
    
    # Apply authentication
    if auth_type == 'bearer' and header_value:
        headers['Authorization'] = f'Bearer {header_value}'
    elif auth_type == 'basic' and header_value:
        encoded = base64.b64encode(header_value.encode()).decode()
        headers['Authorization'] = f'Basic {encoded}'
    elif auth_type == 'api_key' and header_key and header_value:
        headers[header_key] = header_value
    elif header_key and header_value:
        headers[header_key] = header_value
    
    # Set default content-type for body
    if body and 'Content-Type' not in headers:
        headers['Content-Type'] = 'application/json'
    
    result = {
        'success': False,
        'url': url,
        'method': method,
        'status': None,
        'data': None,
        'error': None,
        'duration_ms': None
    }
    
    try:
        start_time = datetime.utcnow()
        
        with httpx.Client(timeout=timeout) as client:
            if method == 'GET':
                response = client.get(url, headers=headers)
            elif method == 'POST':
                response = client.post(url, headers=headers, content=body)
            elif method == 'PUT':
                response = client.put(url, headers=headers, content=body)
            elif method == 'PATCH':
                response = client.patch(url, headers=headers, content=body)
            elif method == 'DELETE':
                response = client.delete(url, headers=headers)
            else:
                result['error'] = f'Unsupported method: {method}'
                return jsonify(result), 200
        
        end_time = datetime.utcnow()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        result['success'] = True
        result['status'] = response.status_code
        result['duration_ms'] = duration_ms
        
        # Try to parse response as JSON
        try:
            result['data'] = response.json()
        except:
            result['data'] = response.text[:1000] if response.text else ''
        
        return jsonify(result), 200
        
    except httpx.TimeoutException:
        result['error'] = f'Request timed out after {timeout} seconds'
        return jsonify(result), 200
    except httpx.ConnectError as e:
        result['error'] = f'Connection error: {str(e)}'
        return jsonify(result), 200
    except Exception as e:
        result['error'] = str(e)
        return jsonify(result), 200


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL EXECUTIONS
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route('/executions', methods=['GET'])
@login_required_api
def list_executions():
    """List all workflow executions for the workspace"""
    workspace_id = session.get('workspace_id')
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    
    # Filters
    status = request.args.get('status')
    workflow_id = request.args.get('workflow_id', type=int)
    
    query = WorkflowExecution.query.filter_by(workspace_id=workspace_id)
    
    if status:
        query = query.filter_by(status=status)
    if workflow_id:
        query = query.filter_by(workflow_id=workflow_id)
    
    pagination = query.order_by(WorkflowExecution.started_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Enrich with workflow names
    executions = []
    for e in pagination.items:
        e_dict = e.to_dict()
        workflow = WorkflowAutomation.query.get(e.workflow_id)
        if workflow:
            e_dict['workflow_name'] = workflow.name
        executions.append(e_dict)
    
    return jsonify({
        'executions': executions,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page
    }), 200


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route('/templates', methods=['GET'])
@login_required_api
def list_templates():
    """List available workflow templates"""
    templates = WorkflowService.WORKFLOW_TEMPLATES
    
    return jsonify({
        'templates': templates
    }), 200


@bp.route('/templates/<template_id>/use', methods=['POST'])
@login_required_api
def use_template(template_id):
    """Create a workflow from a template"""
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    
    # Find template
    template = None
    for t in WorkflowService.WORKFLOW_TEMPLATES:
        if t['id'] == template_id:
            template = t
            break
    
    if not template:
        return jsonify({'error': 'Template not found'}), 404
    
    try:
        canvas_data = template.get('canvas_data')

        workflow = WorkflowAutomation(
            workspace_id=workspace_id,
            name=template['name'],
            description=template['description'],
            is_active=True,
            trigger_type=template['trigger'],
            trigger_config=json.dumps(template.get('trigger_config', {})),
            condition_logic='AND',
            canvas_data=json.dumps(canvas_data) if canvas_data else None,
            created_by=user_id
        )
        db.session.add(workflow)
        db.session.flush()

        # Legacy action rows (for templates without canvas_data)
        if not canvas_data:
            for i, action_type in enumerate(template.get('actions', [])):
                action = WorkflowAction(
                    workflow_id=workflow.id,
                    workspace_id=workspace_id,
                    action_type=action_type,
                    action_config=json.dumps(WorkflowService._get_default_action_config(action_type)),
                    delay_minutes=1 if action_type == 'wait' else 0,
                    order_index=i,
                    created_by=user_id
                )
                db.session.add(action)

        db.session.commit()

        return jsonify({
            'id': workflow.id,
            'name': workflow.name,
            'description': workflow.description,
            'trigger_type': workflow.trigger_type,
            'is_active': workflow.is_active,
            'canvas_data': canvas_data,
            'run_count': 0,
            'last_run_at': None,
            'conditions_count': 0,
            'actions_count': len(template.get('actions', [])),
            'status': 'created_from_template',
            'template_id': template_id
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH EXECUTION (n8n-style)
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route('/<int:workflow_id>/execute', methods=['POST'])
@login_required_api
def execute_workflow_graph(workflow_id):
    """
    Execute a workflow using the n8n-style graph runner.
    
    This endpoint takes the canvas_data (nodes + edges) from the frontend
    and executes it as a directed graph, passing data between nodes.
    
    Request body:
    {
        "entity_type": "deal" | "contact" | "task",
        "entity_id": 123,
        "context": {...}  // optional trigger context
    }
    
    Returns:
    {
        "status": "success" | "failed",
        "execution_id": 456,
        "node_results": [...],
        "duration_ms": 1234
    }
    """
    from services.workflow_graph_runner import WorkflowGraphRunner
    from models_crm import WorkflowExecution
    
    workspace_id = session.get('workspace_id')
    data = request.get_json() or {}
    
    workflow = WorkflowAutomation.query.filter_by(
        id=workflow_id, workspace_id=workspace_id
    ).first()
    
    if not workflow:
        return jsonify({'error': 'Workflow not found'}), 404
    
    # Get entity info
    entity_type = data.get('entity_type', 'deal')
    entity_id = data.get('entity_id')
    trigger_context = data.get('context', {})
    
    if not entity_id:
        return jsonify({'error': 'entity_id is required'}), 400
    
    # Load the entity
    entity = WorkflowService._load_entity(entity_type, entity_id)
    if not entity:
        return jsonify({'error': f'Entity {entity_type}:{entity_id} not found'}), 404
    
    # Get canvas data from workflow or request
    canvas_data = None
    if workflow.canvas_data:
        try:
            canvas_data = json.loads(workflow.canvas_data)
        except:
            pass
    
    # Allow override from request for testing
    if data.get('canvas_data'):
        canvas_data = data['canvas_data']
    
    if not canvas_data or not canvas_data.get('nodes'):
        return jsonify({'error': 'No canvas data available'}), 400
    
    # Create execution log
    execution = None
    try:
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            status='running',
            triggered_by=workflow.trigger_type,
            started_at=datetime.utcnow()
        )
        db.session.add(execution)
        db.session.flush()
        execution_id = execution.id
    except Exception as e:
        logger.error(f"Failed to create execution log: {e}")
        execution_id = None
    
    # Execute the graph
    runner = WorkflowGraphRunner()
    result = runner.execute_workflow(
        workflow_id=workflow_id,
        canvas_data=canvas_data,
        entity=entity,
        context=trigger_context,
        execution_id=execution_id,
    )
    
    # Update execution log
    if execution:
        try:
            execution.status = result['status']
            execution.completed_at = datetime.utcnow()
            execution.actions_executed = json.dumps(result.get('node_results', []))
            if result.get('error'):
                execution.error_message = result['error']
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update execution log: {e}")
    
    # Update workflow stats
    try:
        workflow.run_count += 1
        workflow.last_run_at = datetime.utcnow()
        db.session.commit()
    except:
        db.session.rollback()
    
    return jsonify(result), 200


@bp.route('/<int:workflow_id>/execute/dry-run', methods=['POST'])
@login_required_api
def dry_run_workflow_graph(workflow_id):
    """
    Dry-run a workflow without executing actions.
    Returns the execution plan (which nodes would execute and in what order).
    
    Request body:
    {
        "entity_type": "deal" | "contact" | "task",
        "entity_id": 123,
        "context": {...}  // optional trigger context
    }
    """
    from services.workflow_graph_runner import WorkflowGraphRunner
    
    workspace_id = session.get('workspace_id')
    data = request.get_json() or {}
    
    workflow = WorkflowAutomation.query.filter_by(
        id=workflow_id, workspace_id=workspace_id
    ).first()
    
    if not workflow:
        return jsonify({'error': 'Workflow not found'}), 404
    
    # Get canvas data
    canvas_data = None
    if workflow.canvas_data:
        try:
            canvas_data = json.loads(workflow.canvas_data)
        except:
            pass
    
    if data.get('canvas_data'):
        canvas_data = data['canvas_data']
    
    if not canvas_data or not canvas_data.get('nodes'):
        return jsonify({'error': 'No canvas data available'}), 400
    
    # Build execution plan without running
    runner = WorkflowGraphRunner()
    graph = runner._build_graph(canvas_data)
    
    # Analyze the graph
    node_count = len(graph['nodes'])
    edge_count = len(graph['edges'])
    trigger_nodes = [nid for nid, ndata in graph['nodes'].items()
                     if ndata.get('nodeType') == 'trigger']
    condition_nodes = [nid for nid, ndata in graph['nodes'].items()
                       if ndata.get('nodeType') == 'condition']
    action_nodes = [nid for nid, ndata in graph['nodes'].items()
                    if ndata.get('nodeType') == 'action']
    
    # Build execution order (topological sort)
    execution_order = []
    visited = set()
    
    def visit(node_id):
        if node_id in visited:
            return
        visited.add(node_id)
        for child in graph['adjacency'].get(node_id, []):
            if isinstance(child, dict):
                visit(child['target'])
            else:
                visit(child)
        execution_order.append(node_id)
    
    for trigger in trigger_nodes:
        visit(trigger)
    
    execution_order.reverse()
    
    return jsonify({
        'workflow_id': workflow_id,
        'workflow_name': workflow.name,
        'execution_plan': {
            'total_nodes': node_count,
            'total_edges': edge_count,
            'trigger_nodes': trigger_nodes,
            'condition_nodes': condition_nodes,
            'action_nodes': action_nodes,
            'execution_order': execution_order,
        },
        'node_details': [
            {
                'id': nid,
                'type': ndata.get('nodeType', 'unknown'),
                'subtype': ndata.get('subtype', ''),
                'label': ndata.get('label', ''),
            }
            for nid, ndata in graph['nodes'].items()
        ]
    }), 200


# ═══════════════════════════════════════════════════════════════════════════════
# TRIGGER TYPE INFO
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route('/trigger-types', methods=['GET'])
@login_required_api
def list_trigger_types():
    """List all available trigger types"""
    return jsonify({
        'trigger_types': [
            {'id': k, 'name': v} for k, v in WorkflowService.TRIGGER_TYPES.items()
        ]
    }), 200


@bp.route('/action-types', methods=['GET'])
@login_required_api
def list_action_types():
    """List all available action types"""
    return jsonify({
        'action_types': [
            {'id': k, 'name': v} for k, v in WorkflowService.ACTION_TYPES.items()
        ]
    }), 200


# ═══════════════════════════════════════════════════════════════════════════════
# WORKFLOW VERSIONING
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route('/<int:workflow_id>/publish', methods=['POST'])
@login_required_api
def publish_workflow(workflow_id):
    """Publish current workflow state as a new version"""
    from models_crm import WorkflowVersion
    
    workflow = WorkflowAutomation.query.get(workflow_id)
    if not workflow:
        return jsonify({'error': 'Workflow not found'}), 404
    
    if workflow.workspace_id != session.get('workspace_id'):
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        # Get latest version number
        latest = WorkflowVersion.query.filter_by(
            workflow_id=workflow_id,
            workspace_id=workflow.workspace_id
        ).order_by(WorkflowVersion.version_number.desc()).first()
        
        next_version = (latest.version_number + 1) if latest else 1
        
        # Create version snapshot
        version = WorkflowVersion(
            workflow_id=workflow_id,
            workspace_id=workflow.workspace_id,
            version_number=next_version,
            name=workflow.name,
            description=workflow.description,
            trigger_type=workflow.trigger_type,
            trigger_config=workflow.trigger_config,
            condition_logic=workflow.condition_logic,
            canvas_data=workflow.canvas_data,
            status='published',
            created_by=session.get('user_id'),
            published_at=datetime.utcnow(),
        )
        
        db.session.add(version)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'version': version.to_dict(),
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/<int:workflow_id>/versions', methods=['GET'])
@login_required_api
def get_workflow_versions(workflow_id):
    """Get all versions of a workflow"""
    from models_crm import WorkflowVersion
    
    workflow = WorkflowAutomation.query.get(workflow_id)
    if not workflow:
        return jsonify({'error': 'Workflow not found'}), 404
    
    if workflow.workspace_id != session.get('workspace_id'):
        return jsonify({'error': 'Access denied'}), 403
    
    versions = WorkflowVersion.query.filter_by(
        workflow_id=workflow_id,
        workspace_id=workflow.workspace_id
    ).order_by(WorkflowVersion.version_number.desc()).all()
    
    return jsonify({
        'workflow_id': workflow_id,
        'versions': [v.to_dict() for v in versions],
    }), 200


@bp.route('/<int:workflow_id>/revert/<int:version_id>', methods=['POST'])
@login_required_api
def revert_to_version(workflow_id, version_id):
    """Revert workflow to a previous version"""
    from models_crm import WorkflowVersion
    
    workflow = WorkflowAutomation.query.get(workflow_id)
    if not workflow:
        return jsonify({'error': 'Workflow not found'}), 404
    
    if workflow.workspace_id != session.get('workspace_id'):
        return jsonify({'error': 'Access denied'}), 403
    
    version = WorkflowVersion.query.get(version_id)
    if not version or version.workflow_id != workflow_id:
        return jsonify({'error': 'Version not found'}), 404
    
    try:
        workflow.name = version.name
        workflow.description = version.description
        workflow.trigger_type = version.trigger_type
        workflow.trigger_config = version.trigger_config
        workflow.condition_logic = version.condition_logic
        workflow.canvas_data = version.canvas_data
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Reverted to version {version.version_number}',
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# WORKFLOW TESTING
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route('/<int:workflow_id>/test-run', methods=['POST'])
@login_required_api
def test_run_workflow(workflow_id):
    """
    Test workflow with mock/sample data.
    Executes the graph but with dry-run mode (no real actions).
    """
    from services.workflow_graph_runner import WorkflowGraphRunner
    
    workflow = WorkflowAutomation.query.get(workflow_id)
    if not workflow:
        return jsonify({'error': 'Workflow not found'}), 404
    
    if workflow.workspace_id != session.get('workspace_id'):
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json() or {}
    entity_type = data.get('entity_type', 'contact')
    entity_id = data.get('entity_id')
    
    # Build mock entity if not provided
    if not entity_id:
        mock_entity = _build_mock_entity(entity_type)
        context = {
            'entity': mock_entity,
            'entity_type': entity_type,
            'entity_id': 0,
            'workspace_id': workflow.workspace_id,
            'variables': {},
        }
    else:
        entity = WorkflowService._load_entity(entity_type, entity_id)
        if not entity:
            return jsonify({'error': f'{entity_type} not found'}), 404
        context = {
            'entity': entity.to_dict() if hasattr(entity, 'to_dict') else {},
            'entity_type': entity_type,
            'entity_id': entity_id,
            'workspace_id': workflow.workspace_id,
            'variables': {},
        }
    
    # Get canvas data
    canvas_data = data.get('canvas_data')
    if not canvas_data:
        canvas_data = workflow.canvas_data
    
    if not canvas_data:
        return jsonify({'error': 'No canvas data available'}), 400
    
    try:
        runner = WorkflowGraphRunner()
        result = runner.execute_graph(
            canvas_data=canvas_data,
            context=context,
            dry_run=True,
        )
        
        return jsonify({
            'success': True,
            'workflow_id': workflow_id,
            'test_result': result,
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _build_mock_entity(entity_type: str) -> dict:
    """Build a mock entity for testing"""
    if entity_type == 'contact':
        return {
            'id': 0,
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'phone': '+905551234567',
            'lead_score': 75,
            'labels': 'test,workflow',
            'created_at': datetime.utcnow().isoformat(),
        }
    elif entity_type == 'deal':
        return {
            'id': 0,
            'name': 'Test Deal',
            'deal_value': 15000,
            'stage_id': 3,
            'assigned_to': 1,
            'notes': 'Test deal for workflow testing',
            'created_at': datetime.utcnow().isoformat(),
        }
    elif entity_type == 'task':
        return {
            'id': 0,
            'title': 'Test Task',
            'description': 'Test task for workflow testing',
            'status': 'pending',
            'priority': 'medium',
            'due_date': datetime.utcnow().isoformat(),
        }
    return {'id': 0}


# ═══════════════════════════════════════════════════════════════════════════════
# BULK MANUAL TRIGGER
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route('/<int:workflow_id>/bulk-execute', methods=['POST'])
@login_required_api
def bulk_execute_workflow(workflow_id):
    """
    Execute workflow for multiple entities at once.
    Useful for manual bulk processing.
    """
    workflow = WorkflowAutomation.query.get(workflow_id)
    if not workflow:
        return jsonify({'error': 'Workflow not found'}), 404
    
    if workflow.workspace_id != session.get('workspace_id'):
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json() or {}
    entities = data.get('entities', [])
    
    if not entities:
        return jsonify({'error': 'No entities provided'}), 400
    
    if len(entities) > 100:
        return jsonify({'error': 'Maximum 100 entities per bulk execution'}), 400
    
    results = []
    for entity_data in entities:
        entity_type = entity_data.get('entity_type', 'contact')
        entity_id = entity_data.get('entity_id')
        
        try:
            entity = WorkflowService._load_entity(entity_type, entity_id)
            if not entity:
                results.append({
                    'entity_id': entity_id,
                    'entity_type': entity_type,
                    'status': 'failed',
                    'error': 'Entity not found',
                })
                continue
            
            result = WorkflowService.trigger_event(
                workspace_id=workflow.workspace_id,
                trigger_type=workflow.trigger_type,
                entity_type=entity_type,
                entity_id=entity_id,
            )
            
            results.append({
                'entity_id': entity_id,
                'entity_type': entity_type,
                'status': 'success',
                'workflows_triggered': result.get('workflows_triggered', 0),
            })
            
        except Exception as e:
            results.append({
                'entity_id': entity_id,
                'entity_type': entity_type,
                'status': 'failed',
                'error': str(e),
            })
    
    success_count = sum(1 for r in results if r['status'] == 'success')
    fail_count = len(results) - success_count
    
    return jsonify({
        'workflow_id': workflow_id,
        'total': len(results),
        'success': success_count,
        'failed': fail_count,
        'results': results,
    }), 200


# ═══════════════════════════════════════════════════════════════════════════════
# USAGE / CREDITS TRACKING
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route('/usage', methods=['GET'])
@login_required_api
def get_usage():
    """Get workflow usage statistics for current workspace"""
    from models_crm import WorkflowUsage
    
    workspace_id = session.get('workspace_id')
    
    now = datetime.utcnow()
    usage = WorkflowUsage.query.filter_by(
        workspace_id=workspace_id,
        year=now.year,
        month=now.month,
    ).first()
    
    if not usage:
        return jsonify({
            'year': now.year,
            'month': now.month,
            'total_executions': 0,
            'total_actions': 0,
            'total_errors': 0,
            'total_duration_ms': 0,
            'action_breakdown': {},
            'max_executions': 10000,
            'usage_percent': 0,
        }), 200
    
    return jsonify(usage.to_dict()), 200


@bp.route('/usage/history', methods=['GET'])
@login_required_api
def get_usage_history():
    """Get usage history for the last 6 months"""
    from models_crm import WorkflowUsage
    
    workspace_id = session.get('workspace_id')
    now = datetime.utcnow()
    
    # Get last 6 months
    history = []
    for i in range(6):
        month = now.month - i
        year = now.year
        if month <= 0:
            month += 12
            year -= 1
        
        usage = WorkflowUsage.query.filter_by(
            workspace_id=workspace_id,
            year=year,
            month=month,
        ).first()
        
        if usage:
            history.append(usage.to_dict())
        else:
            history.append({
                'year': year,
                'month': month,
                'total_executions': 0,
                'total_actions': 0,
                'total_errors': 0,
                'max_executions': 10000,
                'usage_percent': 0,
            })
    
    return jsonify({'history': history}), 200


# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTION STATUS (for polling)
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route('/executions/<int:execution_id>', methods=['GET'])
@login_required_api
def get_execution_status(execution_id):
    """
    Get execution status by ID.
    Used for polling execution progress from frontend.
    """
    from models_crm import WorkflowExecution
    
    workspace_id = session.get('workspace_id')
    
    # Get execution
    execution = WorkflowExecution.query.get(execution_id)
    
    if not execution:
        return jsonify({'error': 'Execution not found'}), 404
    
    if execution.workspace_id != workspace_id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Build response
    result = {
        'workflow_id': execution.workflow_id,
        'execution_id': execution.id,
        'status': execution.status,
        'started_at': execution.started_at.isoformat() if execution.started_at else None,
        'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
        'duration_ms': execution.duration_ms,
        'error': execution.error_message,
        'node_results': [],
    }
    
    # Get node results if any
    if execution.execution_data:
        try:
            import json
            data = json.loads(execution.execution_data)
            result['node_results'] = data.get('node_results', [])
        except:
            pass
    
    return jsonify(result), 200


# ═══════════════════════════════════════════════════════════════════════════════
# MANUAL TRIGGER
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route('/<int:workflow_id>/run-manual', methods=['POST'])
@login_required_api
def run_workflow_manual(workflow_id):
    """
    Manually fire a workflow that uses a 'manual' trigger node.
    Useful for on-demand execution from the UI.
    """
    from services.workflow_graph_runner import WorkflowGraphRunner
    from models_crm import WorkflowExecution

    workspace_id = session.get('workspace_id')
    data = request.get_json() or {}

    workflow = WorkflowAutomation.query.filter_by(
        id=workflow_id, workspace_id=workspace_id
    ).first()
    if not workflow:
        return jsonify({'error': 'Workflow not found'}), 404

    canvas_data = None
    if workflow.canvas_data:
        try:
            canvas_data = json.loads(workflow.canvas_data)
        except Exception:
            pass

    if not canvas_data or not canvas_data.get('nodes'):
        return jsonify({'error': 'No canvas data available'}), 400

    entity_type = data.get('entity_type', 'contact')
    entity_id = data.get('entity_id')

    if entity_id:
        entity_obj = WorkflowService._load_entity(entity_type, entity_id)
        entity = entity_obj.to_dict() if entity_obj and hasattr(entity_obj, 'to_dict') else {}
    else:
        entity = _build_mock_entity(entity_type)
        entity_id = 0

    context = {
        'entity': entity,
        'entity_type': entity_type,
        'entity_id': entity_id,
        'workspace_id': workspace_id,
        'variables': {},
        'trigger': {'type': 'manual'},
    }

    execution = None
    try:
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id or 0,
            status='running',
            triggered_by='manual',
            started_at=datetime.utcnow(),
        )
        db.session.add(execution)
        db.session.flush()
    except Exception as e:
        logger.error(f"Failed to create execution log: {e}")

    runner = WorkflowGraphRunner()
    result = runner.execute_graph(
        canvas_data=canvas_data,
        context=context,
        dry_run=False,
    )

    if execution:
        try:
            execution.status = result.get('status', 'completed')
            execution.completed_at = datetime.utcnow()
            execution.actions_executed = json.dumps(result.get('node_results', []))
            if result.get('error'):
                execution.error_message = result['error']
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update execution log: {e}")

    try:
        workflow.run_count = (workflow.run_count or 0) + 1
        workflow.last_run_at = datetime.utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()

    result['execution_id'] = execution.id if execution else None
    return jsonify(result), 200


# ═══════════════════════════════════════════════════════════════════════════════
# INCOMING WEBHOOK TRIGGER (public endpoint — no auth)
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route('/webhook/<string:node_id>', methods=['POST', 'GET'])
def handle_incoming_webhook(node_id):
    """
    Public webhook endpoint.  A 'webhook_trigger' node's URL points here.
    Finds any active workflow whose canvas_data contains this node_id.
    """
    from services.workflow_graph_runner import WorkflowGraphRunner
    from models_crm import WorkflowExecution, WorkflowAutomation

    payload = {}
    if request.method == 'POST':
        try:
            payload = request.get_json(force=True) or {}
        except Exception:
            payload = {}

    # Find all active workflows that contain this node_id in canvas_data
    matching = WorkflowAutomation.query.filter_by(is_active=True).all()
    triggered = []

    for wf in matching:
        if not wf.canvas_data:
            continue
        try:
            canvas = json.loads(wf.canvas_data)
        except Exception:
            continue

        node_ids = [n.get('id') for n in canvas.get('nodes', [])]
        if node_id not in node_ids:
            continue

        context = {
            'entity': {},
            'entity_type': 'webhook',
            'entity_id': 0,
            'workspace_id': wf.workspace_id,
            'variables': {},
            'trigger': {'type': 'webhook_trigger', 'payload': payload, 'node_id': node_id},
        }

        try:
            execution = WorkflowExecution(
                workflow_id=wf.id,
                workspace_id=wf.workspace_id,
                entity_type='webhook',
                entity_id=0,
                status='running',
                triggered_by='webhook_trigger',
                started_at=datetime.utcnow(),
            )
            db.session.add(execution)
            db.session.flush()
        except Exception:
            execution = None

        runner = WorkflowGraphRunner()
        result = runner.execute_graph(canvas_data=canvas, context=context, dry_run=False)

        if execution:
            try:
                execution.status = result.get('status', 'completed')
                execution.completed_at = datetime.utcnow()
                execution.actions_executed = json.dumps(result.get('node_results', []))
                db.session.commit()
            except Exception:
                db.session.rollback()

        triggered.append({'workflow_id': wf.id, 'status': result.get('status')})

    return jsonify({'received': True, 'triggered': triggered, 'node_id': node_id}), 200


# ═══════════════════════════════════════════════════════════════════════════════
# SSE — Live execution stream
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route('/executions/<int:execution_id>/stream', methods=['GET'])
@login_required_api
def stream_execution(execution_id):
    """
    Server-Sent Events stream for live execution progress.
    Polls execution status and streams updates until completed/failed.
    """
    import time
    from models_crm import WorkflowExecution

    workspace_id = session.get('workspace_id')

    def generate():
        max_polls = 120  # 2 min timeout at 1s interval
        polls = 0
        while polls < max_polls:
            try:
                exec_obj = WorkflowExecution.query.get(execution_id)
                if not exec_obj or exec_obj.workspace_id != workspace_id:
                    yield f"data: {json.dumps({'error': 'not_found'})}\n\n"
                    return

                node_results = []
                if exec_obj.actions_executed:
                    try:
                        node_results = json.loads(exec_obj.actions_executed)
                    except Exception:
                        pass

                payload = {
                    'execution_id': execution_id,
                    'status': exec_obj.status,
                    'node_results': node_results,
                    'started_at': exec_obj.started_at.isoformat() if exec_obj.started_at else None,
                    'completed_at': exec_obj.completed_at.isoformat() if exec_obj.completed_at else None,
                    'error': exec_obj.error_message,
                }
                yield f"data: {json.dumps(payload)}\n\n"

                if exec_obj.status in ('completed', 'failed', 'cancelled'):
                    return

                time.sleep(1)
                polls += 1
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                return

        yield f"data: {json.dumps({'error': 'timeout'})}\n\n"

    from flask import Response
    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


# ═══════════════════════════════════════════════════════════════════════════════
# VARIABLES SCHEMA — for the variables dropdown in the UI
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route('/<int:workflow_id>/variables-schema', methods=['GET'])
@login_required_api
def get_variables_schema(workflow_id):
    """
    Returns available variable paths for a workflow based on its trigger type.
    Used by the frontend variables dropdown.
    """
    workspace_id = session.get('workspace_id')

    workflow = WorkflowAutomation.query.filter_by(
        id=workflow_id, workspace_id=workspace_id
    ).first()
    if not workflow:
        return jsonify({'error': 'Workflow not found'}), 404

    trigger_type = workflow.trigger_type or ''

    contact_vars = [
        {'path': 'contact.id', 'label': 'ID', 'type': 'number'},
        {'path': 'contact.first_name', 'label': 'Ad', 'type': 'string'},
        {'path': 'contact.last_name', 'label': 'Soyad', 'type': 'string'},
        {'path': 'contact.email', 'label': 'E-posta', 'type': 'string'},
        {'path': 'contact.phone', 'label': 'Telefon', 'type': 'string'},
        {'path': 'contact.lead_score', 'label': 'Lead Skoru', 'type': 'number'},
        {'path': 'contact.labels', 'label': 'Etiketler', 'type': 'string'},
        {'path': 'contact.assigned_to', 'label': 'Atanan', 'type': 'number'},
        {'path': 'contact.created_at', 'label': 'Oluşturulma', 'type': 'datetime'},
    ]

    deal_vars = [
        {'path': 'deal.id', 'label': 'ID', 'type': 'number'},
        {'path': 'deal.name', 'label': 'Anlaşma Adı', 'type': 'string'},
        {'path': 'deal.deal_value', 'label': 'Değer', 'type': 'number'},
        {'path': 'deal.stage_id', 'label': 'Aşama ID', 'type': 'number'},
        {'path': 'deal.assigned_to', 'label': 'Atanan', 'type': 'number'},
        {'path': 'deal.close_date', 'label': 'Kapanış Tarihi', 'type': 'datetime'},
        {'path': 'deal.created_at', 'label': 'Oluşturulma', 'type': 'datetime'},
    ]

    task_vars = [
        {'path': 'task.id', 'label': 'ID', 'type': 'number'},
        {'path': 'task.title', 'label': 'Başlık', 'type': 'string'},
        {'path': 'task.status', 'label': 'Durum', 'type': 'string'},
        {'path': 'task.priority', 'label': 'Öncelik', 'type': 'string'},
        {'path': 'task.due_date', 'label': 'Bitiş Tarihi', 'type': 'datetime'},
    ]

    system_vars = [
        {'path': 'trigger.type', 'label': 'Tetikleyici Tipi', 'type': 'string'},
        {'path': 'workspace_id', 'label': 'Çalışma Alanı ID', 'type': 'number'},
        {'path': 'entity_type', 'label': 'Varlık Tipi', 'type': 'string'},
        {'path': 'entity_id', 'label': 'Varlık ID', 'type': 'number'},
    ]

    # Determine which groups to include based on trigger
    groups = [{'group': 'Sistem', 'vars': system_vars}]

    if any(k in trigger_type for k in ('contact', 'manual', 'schedule', 'webhook')):
        groups.insert(0, {'group': 'Kişi', 'vars': contact_vars})
        groups.insert(1, {'group': 'Anlaşma', 'vars': deal_vars})
    elif 'deal' in trigger_type:
        groups.insert(0, {'group': 'Anlaşma', 'vars': deal_vars})
        groups.insert(1, {'group': 'Kişi', 'vars': contact_vars})
    elif 'task' in trigger_type:
        groups.insert(0, {'group': 'Görev', 'vars': task_vars})
    else:
        groups = [
            {'group': 'Kişi', 'vars': contact_vars},
            {'group': 'Anlaşma', 'vars': deal_vars},
            {'group': 'Görev', 'vars': task_vars},
            {'group': 'Sistem', 'vars': system_vars},
        ]

    return jsonify({'groups': groups, 'trigger_type': trigger_type}), 200


# Helper for datetime
from datetime import timedelta
