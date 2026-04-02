"""
Task Management Routes
API endpoints for tasks, milestones, dependencies, comments, and attachments
"""
from flask import Blueprint, request, jsonify, send_file, session, redirect, url_for
from functools import wraps
from services.task_service import TaskService
from services.collaboration_service import CollaborationService
from models import db, User
from datetime import datetime, timezone
import os
import logging
from werkzeug.utils import secure_filename

UTC = timezone.utc
logger = logging.getLogger(__name__)
tasks_bp = Blueprint('tasks', __name__)

# File upload configuration
UPLOAD_FOLDER = 'uploads/tasks'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def login_required(f):
    """Session-based login required decorator"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        user = User.query.get(user_id)
        if not user or not user.workspace_id:
            return jsonify({'error': 'Workspace context missing'}), 401
        return f(*args, **kwargs)
    return decorated


def write_access_required(f):
    """Block mutation endpoints for read-only roles."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401

        role = (session.get('user_role') or '').lower()
        if role in {'read-only', 'readonly', 'viewer'}:
            return jsonify({'error': 'Write permission required'}), 403

        return f(*args, **kwargs)

    return decorated

def get_current_user():
    """Get current user from session"""
    user_id = session.get('user_id')
    if user_id:
        return User.query.get(user_id)
    return None

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============================================================================
# TASK CRUD
# ============================================================================

@tasks_bp.route('/api/v1/tasks', methods=['POST'])
@login_required
@write_access_required
def create_task():
    """
    Create a new task
    
    Request body:
    {
        "title": "Task title",
        "description": "Task description",
        "assignee_id": 1,
        "company_id": 1,
        "deal_id": 1,
        "milestone_id": 1,
        "contact_id": 1,
        "status": "not_started",
        "priority": "medium",
        "due_date": "2024-12-31T23:59:59",
        "start_time": "2024-12-31T10:00:00",
        "end_time": "2024-12-31T11:00:00",
        "timezone": "Europe/Istanbul",
        "task_type": "call",
        "is_customer_facing": false
    }
    """
    current_user = get_current_user()
    data = request.get_json()
    
    if not data or 'title' not in data:
        return jsonify({'error': 'Title is required'}), 400
    
    try:
        # Parse due_date if provided
        due_date = None
        if 'due_date' in data and data['due_date']:
            due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
        
        # Parse start_time if provided
        start_time = None
        if 'start_time' in data and data['start_time']:
            dt_str = data['start_time'].replace('Z', '+00:00')
            start_time = datetime.fromisoformat(dt_str)
            # Convert to UTC for storage if timezone-aware
            if start_time.tzinfo is not None:
                start_time = start_time.astimezone(UTC).replace(tzinfo=None)
        
        # Parse end_time if provided
        end_time = None
        if 'end_time' in data and data['end_time']:
            dt_str = data['end_time'].replace('Z', '+00:00')
            end_time = datetime.fromisoformat(dt_str)
            # Convert to UTC for storage if timezone-aware
            if end_time.tzinfo is not None:
                end_time = end_time.astimezone(UTC).replace(tzinfo=None)
        
        # Validate time range
        if start_time and end_time and start_time >= end_time:
            return jsonify({'error': 'Bitiş zamanı başlangıç zamanından sonra olmalıdır'}), 400
        
        task = TaskService.create_task(
            workspace_id=get_current_user().workspace_id,
            title=data['title'],
            description=data.get('description'),
            assignee_id=data.get('assignee_id'),
            company_id=data.get('company_id'),
            deal_id=data.get('deal_id'),
            milestone_id=data.get('milestone_id'),
            contact_id=data.get('contact_id'),
            status=data.get('status', 'not_started'),
            priority=data.get('priority', 'medium'),
            due_date=due_date,
            start_time=start_time,
            end_time=end_time,
            timezone=data.get('timezone', 'UTC'),
            task_type=data.get('task_type', 'task'),
            is_customer_facing=data.get('is_customer_facing', False),
            user_id=current_user.id
        )

        if task and task.assignee_id:
            CollaborationService.create_task_assignment_notification(
                workspace_id=current_user.workspace_id,
                task_id=task.id,
                assignee_id=task.assignee_id,
                actor_user_id=current_user.id,
            )

        # Trigger workflow automation for task_created
        try:
            from services.workflow_service import WorkflowService
            WorkflowService.trigger_event(
                workspace_id=current_user.workspace_id,
                trigger_type='task_created',
                entity_type='task',
                entity_id=task.id
            )
        except Exception as e:
            logger.error(f"Workflow trigger error for task_created: {e}")

        return jsonify({
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'assignee_id': task.assignee_id,
            'company_id': task.company_id,
            'deal_id': task.deal_id,
            'milestone_id': task.milestone_id,
            'contact_id': task.contact_id,
            'status': task.status,
            'priority': task.priority,
            'due_date': task.due_date.isoformat() if task.due_date else None,
            'start_time': task.start_time.isoformat() if task.start_time else None,
            'end_time': task.end_time.isoformat() if task.end_time else None,
            'timezone': task.timezone,
            'task_type': task.task_type,
            'is_customer_facing': task.is_customer_facing,
            'created_at': task.created_at.isoformat()
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating task: {str(e)}")
        return jsonify({'error': 'Görev oluşturulurken hata oluştu'}), 500


@tasks_bp.route('/api/v1/tasks', methods=['GET'])
@login_required
def list_tasks():
    """
    List tasks with optional filters
    
    Query params:
        - assignee_id: Filter by assignee
        - company_id: Filter by company
        - deal_id: Filter by deal
        - milestone_id: Filter by milestone
        - status: Filter by status
        - priority: Filter by priority
        - is_customer_facing: Filter by customer visibility (true/false)
        - page: Page number (default 1)
        - per_page: Items per page (default 50)
    
    SECURITY: Automatically filters tasks based on user role and assignments
    """
    from utils.permissions import get_accessible_entities_query
    from models_crm import Task
    
    current_user = get_current_user()
    
    # Build filters from query params
    filters = {}
    
    if request.args.get('assignee_id'):
        filters['assignee_id'] = int(request.args.get('assignee_id'))
    if request.args.get('company_id'):
        filters['company_id'] = int(request.args.get('company_id'))
    if request.args.get('deal_id'):
        filters['deal_id'] = int(request.args.get('deal_id'))
    if request.args.get('milestone_id'):
        filters['milestone_id'] = int(request.args.get('milestone_id'))
    if request.args.get('status'):
        filters['status'] = request.args.get('status')
    if request.args.get('priority'):
        filters['priority'] = request.args.get('priority')
    if request.args.get('is_customer_facing'):
        filters['is_customer_facing'] = request.args.get('is_customer_facing').lower() == 'true'
    
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    
    # SECURITY: Get base query with access control filtering (IDOR protection)
    base_query = get_accessible_entities_query(current_user, Task)
    
    # Apply additional filters
    for key, value in filters.items():
        base_query = base_query.filter(getattr(Task, key) == value)
    
    # Paginate
    pagination = base_query.order_by(Task.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    tasks = [{
        'id': task.id,
        'title': task.title,
        'description': task.description,
        'assignee_id': task.assignee_id,
        'company_id': task.company_id,
        'deal_id': task.deal_id,
        'milestone_id': task.milestone_id,
        'status': task.status,
        'priority': task.priority,
        'due_date': task.due_date.isoformat() if task.due_date else None,
        'is_customer_facing': task.is_customer_facing,
        'created_at': task.created_at.isoformat(),
        'completed_at': task.completed_at.isoformat() if task.completed_at else None
    } for task in pagination.items]
    
    return jsonify({
        'tasks': tasks,
        'total': pagination.total,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'pages': pagination.pages
    })


@tasks_bp.route('/api/v1/tasks/<int:task_id>', methods=['GET'])
@login_required
def get_task(task_id):
    """Get task details"""
    from utils.permissions import check_entity_access
    
    current_user = get_current_user()
    task = TaskService.get_task(task_id, current_user.workspace_id)
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    # SECURITY: Check entity access (IDOR protection)
    if not check_entity_access(current_user, task, 'read'):
        logger.warning(f"Access denied: user {current_user.id} attempted to read task {task_id}")
        return jsonify({'error': 'Access denied to this task'}), 403
    
    # Get dependencies
    dependencies = TaskService.get_task_dependencies(task_id, get_current_user().workspace_id)
    blocked_tasks = TaskService.get_blocked_tasks(task_id, get_current_user().workspace_id)
    can_start, incomplete_deps = TaskService.can_start_task(task_id, get_current_user().workspace_id)
    
    return jsonify({
        'id': task.id,
        'title': task.title,
        'description': task.description,
        'assignee_id': task.assignee_id,
        'company_id': task.company_id,
        'deal_id': task.deal_id,
        'milestone_id': task.milestone_id,
        'status': task.status,
        'priority': task.priority,
        'due_date': task.due_date.isoformat() if task.due_date else None,
        'is_customer_facing': task.is_customer_facing,
        'created_at': task.created_at.isoformat(),
        'completed_at': task.completed_at.isoformat() if task.completed_at else None,
        'dependencies': [{'id': d.id, 'title': d.title, 'status': d.status} for d in dependencies],
        'blocked_tasks': [{'id': t.id, 'title': t.title} for t in blocked_tasks],
        'can_start': can_start
    })


@tasks_bp.route('/api/v1/tasks/<int:task_id>', methods=['PATCH'])
@login_required
@write_access_required
def update_task(task_id):
    """
    Update task fields
    
    Request body can include any of:
    {
        "title": "New title",
        "description": "New description",
        "assignee_id": 2,
        "contact_id": 1,
        "status": "in_progress",
        "priority": "high",
        "due_date": "2024-12-31T23:59:59",
        "start_time": "2024-12-31T10:00:00",
        "end_time": "2024-12-31T11:00:00",
        "timezone": "Europe/Istanbul",
        "task_type": "meeting",
        "is_customer_facing": true
    }
    """
    from utils.permissions import check_entity_access
    
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        current_user = get_current_user()
        
        # Get task first to check access
        existing_task = TaskService.get_task(task_id, current_user.workspace_id)
        
        if not existing_task:
            return jsonify({'error': 'Task not found'}), 404
        
        # SECURITY: Check entity access (IDOR protection)
        if not check_entity_access(current_user, existing_task, 'write'):
            logger.warning(f"Access denied: user {current_user.id} attempted to update task {task_id}")
            return jsonify({'error': 'Access denied to this task'}), 403
        
        old_assignee_id = existing_task.assignee_id
        
        # Parse due_date if provided
        if 'due_date' in data and data['due_date']:
            data['due_date'] = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
        
        # Parse start_time if provided
        if 'start_time' in data and data['start_time']:
            dt_str = data['start_time'].replace('Z', '+00:00')
            dt = datetime.fromisoformat(dt_str)
            # Convert to UTC for storage if timezone-aware
            if dt.tzinfo is not None:
                dt = dt.astimezone(UTC).replace(tzinfo=None)
            data['start_time'] = dt
        
        # Parse end_time if provided
        if 'end_time' in data and data['end_time']:
            dt_str = data['end_time'].replace('Z', '+00:00')
            dt = datetime.fromisoformat(dt_str)
            # Convert to UTC for storage if timezone-aware
            if dt.tzinfo is not None:
                dt = dt.astimezone(UTC).replace(tzinfo=None)
            data['end_time'] = dt
        
        # Validate time range if both provided
        if 'start_time' in data and 'end_time' in data:
            if data['start_time'] and data['end_time'] and data['start_time'] >= data['end_time']:
                return jsonify({'error': 'Bitiş zamanı başlangıç zamanından sonra olmalıdır'}), 400
        
        # Update task
        task = TaskService.update_task(
            task_id, 
            current_user.workspace_id, 
            user_id=current_user.id,
            **data
        )
        
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        # Send notification if assignee changed
        if task.assignee_id and task.assignee_id != old_assignee_id:
            CollaborationService.create_task_assignment_notification(
                workspace_id=current_user.workspace_id,
                task_id=task.id,
                assignee_id=task.assignee_id,
                actor_user_id=current_user.id,
            )
        
        return jsonify({
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'assignee_id': task.assignee_id,
            'contact_id': task.contact_id,
            'status': task.status,
            'priority': task.priority,
            'due_date': task.due_date.isoformat() if task.due_date else None,
            'start_time': task.start_time.isoformat() if task.start_time else None,
            'end_time': task.end_time.isoformat() if task.end_time else None,
            'timezone': task.timezone,
            'task_type': task.task_type,
            'is_customer_facing': task.is_customer_facing,
            'updated_at': task.updated_at.isoformat(),
            'completed_at': task.completed_at.isoformat() if task.completed_at else None
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating task: {str(e)}")
        return jsonify({'error': 'Görev güncellenirken hata oluştu'}), 500


@tasks_bp.route('/api/v1/tasks/<int:task_id>', methods=['DELETE'])
@login_required
@write_access_required
def delete_task(task_id):
    """Delete a task"""
    from utils.permissions import check_entity_access
    
    current_user = get_current_user()
    
    # Get task first to check access
    task = TaskService.get_task(task_id, current_user.workspace_id)
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    # SECURITY: Check entity access (IDOR protection)
    if not check_entity_access(current_user, task, 'delete'):
        logger.warning(f"Access denied: user {current_user.id} attempted to delete task {task_id}")
        return jsonify({'error': 'Access denied to this task'}), 403
    
    # Proceed with deletion
    success = TaskService.delete_task(task_id, current_user.workspace_id)
    
    if not success:
        return jsonify({'error': 'Task not found'}), 404
    
    return jsonify({'message': 'Task deleted successfully'})


@tasks_bp.route('/api/v1/tasks/<int:task_id>/complete', methods=['POST'])
@login_required
@write_access_required
def complete_task(task_id):
    """
    Mark a task as completed
    
    This is a convenience endpoint for completing tasks.
    It updates the task status to 'completed' and sets completed_at timestamp.
    """
    from utils.permissions import check_entity_access
    
    try:
        current_user = get_current_user()
        
        # Get the task first to verify it exists
        task = TaskService.get_task(task_id, current_user.workspace_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # SECURITY: Check entity access (IDOR protection)
        if not check_entity_access(current_user, task, 'write'):
            logger.warning(f"Access denied: user {current_user.id} attempted to complete task {task_id}")
            return jsonify({'error': 'Access denied to this task'}), 403
        
        # Update task to completed status
        task = TaskService.update_task(
            task_id,
            current_user.workspace_id,
            user_id=current_user.id,
            status='completed'
        )
        
        # Trigger workflow automation for task_completed
        try:
            from services.workflow_service import WorkflowService
            WorkflowService.trigger_event(
                workspace_id=current_user.workspace_id,
                trigger_type='task_completed',
                entity_type='task',
                entity_id=task.id
            )
        except Exception as e:
            logger.error(f"Workflow trigger error for task_completed: {e}")
        
        return jsonify({
            'id': task.id,
            'title': task.title,
            'status': task.status,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'updated_at': task.updated_at.isoformat()
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error completing task: {str(e)}")
        return jsonify({'error': 'Görev tamamlanırken hata oluştu'}), 500


# ============================================================================
# TASK DEPENDENCIES
# ============================================================================

@tasks_bp.route('/api/v1/tasks/<int:task_id>/dependencies', methods=['POST'])
@login_required
@write_access_required
def add_dependency(task_id):
    """
    Add a task dependency
    
    Request body:
    {
        "depends_on_task_id": 5
    }
    """
    data = request.get_json()
    
    if not data or 'depends_on_task_id' not in data:
        return jsonify({'error': 'depends_on_task_id is required'}), 400
    
    dependency = TaskService.add_dependency(
        task_id=task_id,
        depends_on_task_id=data['depends_on_task_id'],
        workspace_id=get_current_user().workspace_id
    )
    
    if not dependency:
        return jsonify({'error': 'Failed to add dependency. Check for circular dependencies or invalid task IDs.'}), 400
    
    return jsonify({
        'id': dependency.id,
        'task_id': dependency.task_id,
        'depends_on_task_id': dependency.depends_on_task_id,
        'created_at': dependency.created_at.isoformat()
    }), 201


@tasks_bp.route('/api/v1/tasks/<int:task_id>/dependencies/<int:depends_on_task_id>', methods=['DELETE'])
@login_required
@write_access_required
def remove_dependency(task_id, depends_on_task_id):
    """Remove a task dependency"""
    success = TaskService.remove_dependency(task_id, depends_on_task_id, get_current_user().workspace_id)
    
    if not success:
        return jsonify({'error': 'Dependency not found'}), 404
    
    return jsonify({'message': 'Dependency removed successfully'})


# ============================================================================
# MILESTONES
# ============================================================================

@tasks_bp.route('/api/v1/milestones', methods=['POST'])
@login_required
@write_access_required
def create_milestone():
    """
    Create a new milestone
    
    Request body:
    {
        "name": "Milestone name",
        "company_id": 1,
        "due_date": "2024-12-31T23:59:59"
    }
    """
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Name is required'}), 400
    
    # Parse due_date if provided
    due_date = None
    if 'due_date' in data and data['due_date']:
        try:
            due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Invalid due_date format'}), 400
    
    try:
        milestone = TaskService.create_milestone(
            workspace_id=get_current_user().workspace_id,
            name=data['name'],
            company_id=data.get('company_id'),
            due_date=due_date
        )
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    
    return jsonify({
        'id': milestone.id,
        'name': milestone.name,
        'company_id': milestone.company_id,
        'due_date': milestone.due_date.isoformat() if milestone.due_date else None,
        'status': milestone.status,
        'created_at': milestone.created_at.isoformat()
    }), 201


@tasks_bp.route('/api/v1/milestones', methods=['GET'])
@login_required
def list_milestones():
    """
    List milestones
    
    Query params:
        - company_id: Filter by company
        - page: Page number (default 1)
        - per_page: Items per page (default 50)
    """
    company_id = request.args.get('company_id', type=int)
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    
    pagination = TaskService.list_milestones(
        workspace_id=get_current_user().workspace_id,
        company_id=company_id,
        page=page,
        per_page=per_page
    )
    
    milestones = []
    for milestone in pagination.items:
        progress = TaskService.calculate_milestone_progress(milestone.id, get_current_user().workspace_id)
        milestones.append({
            'id': milestone.id,
            'name': milestone.name,
            'company_id': milestone.company_id,
            'due_date': milestone.due_date.isoformat() if milestone.due_date else None,
            'status': milestone.status,
            'created_at': milestone.created_at.isoformat(),
            'progress': progress
        })
    
    return jsonify({
        'milestones': milestones,
        'total': pagination.total,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'pages': pagination.pages
    })


@tasks_bp.route('/api/v1/milestones/<int:milestone_id>', methods=['GET'])
@login_required
def get_milestone(milestone_id):
    """Get milestone details with progress"""
    milestone = TaskService.get_milestone(milestone_id, get_current_user().workspace_id)
    
    if not milestone:
        return jsonify({'error': 'Milestone not found'}), 404
    
    progress = TaskService.calculate_milestone_progress(milestone_id, get_current_user().workspace_id)
    
    return jsonify({
        'id': milestone.id,
        'name': milestone.name,
        'company_id': milestone.company_id,
        'due_date': milestone.due_date.isoformat() if milestone.due_date else None,
        'status': milestone.status,
        'created_at': milestone.created_at.isoformat(),
        'progress': progress
    })


@tasks_bp.route('/api/v1/milestones/<int:milestone_id>', methods=['PATCH'])
@login_required
@write_access_required
def update_milestone(milestone_id):
    """Update milestone fields"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Parse due_date if provided
    if 'due_date' in data and data['due_date']:
        try:
            data['due_date'] = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Invalid due_date format'}), 400
    
    try:
        milestone = TaskService.update_milestone(milestone_id, get_current_user().workspace_id, **data)
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    
    if not milestone:
        return jsonify({'error': 'Milestone not found'}), 404
    
    return jsonify({
        'id': milestone.id,
        'name': milestone.name,
        'company_id': milestone.company_id,
        'due_date': milestone.due_date.isoformat() if milestone.due_date else None,
        'status': milestone.status
    })


# ============================================================================
# TASK COMMENTS
# ============================================================================
# TASK COMMENTS (using TaskCommentService)
# ============================================================================


# ============================================================================
# TASK ATTACHMENTS
# ============================================================================

@tasks_bp.route('/api/v1/tasks/<int:task_id>/attachments', methods=['POST'])
@login_required
@write_access_required
def upload_attachment(task_id):
    """
    Upload a file attachment to a task
    
    Form data:
        - file: File to upload
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        return jsonify({'error': f'File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB'}), 400
    
    # Create upload directory
    workspace_upload_dir = os.path.join(UPLOAD_FOLDER, f'workspace_{get_current_user().workspace_id}')
    os.makedirs(workspace_upload_dir, exist_ok=True)
    
    # Save file
    filename = secure_filename(file.filename)
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    unique_filename = f'{timestamp}_{filename}'
    file_path = os.path.join(workspace_upload_dir, unique_filename)
    
    file.save(file_path)
    
    # Create attachment record
    attachment = TaskService.add_attachment(
        task_id=task_id,
        file_name=filename,
        file_path=file_path,
        file_size=file_size,
        uploaded_by=get_current_user().id,
        workspace_id=get_current_user().workspace_id
    )
    
    if not attachment:
        # Clean up file if task not found
        os.remove(file_path)
        return jsonify({'error': 'Task not found'}), 404
    
    return jsonify({
        'id': attachment.id,
        'task_id': attachment.task_id,
        'file_name': attachment.file_name,
        'file_size': attachment.file_size,
        'uploaded_by': attachment.uploaded_by,
        'created_at': attachment.created_at.isoformat()
    }), 201


@tasks_bp.route('/api/v1/tasks/<int:task_id>/attachments', methods=['GET'])
@login_required
def get_attachments(task_id):
    """Get all attachments for a task"""
    attachments = TaskService.get_task_attachments(task_id, get_current_user().workspace_id)
    
    return jsonify({
        'attachments': [{
            'id': a.id,
            'task_id': a.task_id,
            'file_name': a.file_name,
            'file_size': a.file_size,
            'uploaded_by': a.uploaded_by,
            'created_at': a.created_at.isoformat()
        } for a in attachments]
    })


@tasks_bp.route('/api/v1/tasks/<int:task_id>/attachments/<int:attachment_id>/download', methods=['GET'])
@login_required
def download_attachment(task_id, attachment_id):
    """Download a task attachment"""
    attachments = TaskService.get_task_attachments(task_id, get_current_user().workspace_id)
    attachment = next((a for a in attachments if a.id == attachment_id), None)
    
    if not attachment:
        return jsonify({'error': 'Attachment not found'}), 404
    
    upload_root = os.path.abspath(UPLOAD_FOLDER)
    file_path = os.path.abspath(attachment.file_path)

    if os.path.commonpath([upload_root, file_path]) != upload_root:
        return jsonify({'error': 'Invalid attachment path'}), 403

    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found on server'}), 404

    return send_file(file_path, as_attachment=True, download_name=attachment.file_name)


# ============================================================================
# TASK TEMPLATES
# ============================================================================

@tasks_bp.route('/api/v1/tasks/from-template', methods=['POST'])
@login_required
@write_access_required
def create_from_template():
    """
    Create tasks from a template
    
    Request body:
    {
        "template_tasks": [
            {
                "title": "Task 1",
                "description": "Description",
                "priority": "high",
                "days_offset": 0,
                "assignee_id": 1,
                "depends_on_index": null
            },
            {
                "title": "Task 2",
                "description": "Description",
                "priority": "medium",
                "days_offset": 7,
                "assignee_id": 1,
                "depends_on_index": 0
            }
        ],
        "company_id": 1,
        "deal_id": 1,
        "milestone_id": 1
    }
    """
    data = request.get_json()
    
    if not data or 'template_tasks' not in data:
        return jsonify({'error': 'template_tasks is required'}), 400
    
    try:
        tasks = TaskService.create_from_template(
            workspace_id=get_current_user().workspace_id,
            template_tasks=data['template_tasks'],
            company_id=data.get('company_id'),
            deal_id=data.get('deal_id'),
            milestone_id=data.get('milestone_id')
        )
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    
    return jsonify({
        'tasks': [{
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'status': task.status,
            'priority': task.priority,
            'due_date': task.due_date.isoformat() if task.due_date else None,
            'created_at': task.created_at.isoformat()
        } for task in tasks]
    }), 201


# ============================================================================
# TASK COMMENTS (using TaskCommentService)
# ============================================================================

@tasks_bp.route('/api/v1/tasks/<int:task_id>/comments', methods=['POST'])
@login_required
@write_access_required
def create_task_comment(task_id):
    """Create a comment on a task"""
    from services.task_comment_service import TaskCommentService
    
    data = request.get_json()
    
    if not data or not data.get('content'):
        return jsonify({'error': 'content is required'}), 400
    
    try:
        comment = TaskCommentService.create_comment(
            task_id=task_id,
            user_id=get_current_user().id,
            content=data['content']
        )
        
        return jsonify({
            'id': comment.id,
            'task_id': comment.task_id,
            'user_id': comment.user_id,
            'content': comment.content,
            'created_at': comment.created_at.isoformat()
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/api/v1/tasks/<int:task_id>/comments', methods=['GET'])
@login_required
def get_task_comments(task_id):
    """Get all comments for a task"""
    from services.task_comment_service import TaskCommentService
    
    comments = TaskCommentService.get_task_comments(task_id)
    
    return jsonify({
        'comments': [{
            'id': c.id,
            'task_id': c.task_id,
            'user_id': c.user_id,
            'content': c.content,
            'created_at': c.created_at.isoformat()
        } for c in comments]
    })


@tasks_bp.route('/api/v1/tasks/comments/<int:comment_id>', methods=['DELETE'])
@login_required
@write_access_required
def delete_task_comment(comment_id):
    """Delete a comment"""
    from services.task_comment_service import TaskCommentService
    
    try:
        TaskCommentService.delete_comment(comment_id, get_current_user().id)
        return jsonify({'message': 'Comment deleted'}), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ============================================================================
# TASK ATTACHMENTS
# ============================================================================

@tasks_bp.route('/api/v1/tasks/<int:task_id>/attachments', methods=['POST'])
@login_required
@write_access_required
def create_task_attachment(task_id):
    """Upload an attachment to a task"""
    from services.task_comment_service import TaskCommentService
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        return jsonify({'error': 'File too large (max 10MB)'}), 400
    
    try:
        attachment = TaskCommentService.create_attachment(
            task_id=task_id,
            user_id=get_current_user().id,
            file=file,
            upload_folder=UPLOAD_FOLDER
        )
        
        return jsonify({
            'id': attachment.id,
            'task_id': attachment.task_id,
            'file_name': attachment.file_name,
            'file_size': attachment.file_size,
            'uploaded_by': attachment.uploaded_by,
            'created_at': attachment.created_at.isoformat()
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/api/v1/tasks/<int:task_id>/attachments', methods=['GET'])
@login_required
def get_task_attachments(task_id):
    """Get all attachments for a task"""
    from services.task_comment_service import TaskCommentService
    
    attachments = TaskCommentService.get_task_attachments(task_id)
    
    return jsonify({
        'attachments': [{
            'id': a.id,
            'task_id': a.task_id,
            'file_name': a.file_name,
            'file_size': a.file_size,
            'uploaded_by': a.uploaded_by,
            'created_at': a.created_at.isoformat()
        } for a in attachments]
    })


@tasks_bp.route('/api/v1/tasks/attachments/<int:attachment_id>', methods=['DELETE'])
@login_required
@write_access_required
def delete_task_attachment(attachment_id):
    """Delete an attachment"""
    from services.task_comment_service import TaskCommentService
    
    try:
        TaskCommentService.delete_attachment(attachment_id, get_current_user().id)
        return jsonify({'message': 'Attachment deleted'}), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/api/v1/tasks/attachments/<int:attachment_id>/download', methods=['GET'])
@login_required
def download_task_attachment(attachment_id):
    """Download an attachment file"""
    from models_crm import TaskAttachment
    
    attachment = TaskAttachment.query.get(attachment_id)
    
    if not attachment:
        return jsonify({'error': 'Attachment not found'}), 404
    
    # Verify user has access to this task's workspace
    from models_crm import Task
    task = Task.query.get(attachment.task_id)
    if not task or task.workspace_id != get_current_user().workspace_id:
        return jsonify({'error': 'Access denied'}), 403
    
    if not os.path.exists(attachment.file_path):
        return jsonify({'error': 'File not found on disk'}), 404
    
    return send_file(
        attachment.file_path,
        as_attachment=True,
        download_name=attachment.file_name
    )
