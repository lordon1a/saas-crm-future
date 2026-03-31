"""
Workflow API Routes
===================
REST API endpoints for workflow automation management.

Prefix: /api/v1/workflows
"""
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

bp = Blueprint('workflows', __name__, url_prefix='/api/v1/workflows')


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
    
    try:
        # Create workflow
        workflow = WorkflowAutomation(
            workspace_id=workspace_id,
            name=name,
            description=data.get('description', ''),
            is_active=data.get('is_active', True),
            trigger_type=trigger_type,
            trigger_config=json.dumps(data.get('trigger_config', {})),
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
        # Create workflow from template
        workflow = WorkflowAutomation(
            workspace_id=workspace_id,
            name=template['name'],
            description=template['description'],
            is_active=True,
            trigger_type=template['trigger'],
            trigger_config=json.dumps(template.get('trigger_config', {})),
            condition_logic='AND',
            created_by=user_id
        )
        db.session.add(workflow)
        db.session.flush()
        
        # Add default actions based on template
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
            'status': 'created_from_template',
            'template_id': template_id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


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


# Helper for datetime
from datetime import timedelta
