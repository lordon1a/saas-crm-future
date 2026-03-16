"""
Task Management Routes
API endpoints for tasks, milestones, dependencies, comments, and attachments
"""
from flask import Blueprint, request, jsonify, send_file, session, redirect, url_for
from functools import wraps
from services.task_service import TaskService
from models import db, User
from datetime import datetime
import os
from werkzeug.utils import secure_filename

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
        "status": "not_started",
        "priority": "medium",
        "due_date": "2024-12-31T23:59:59",
        "is_customer_facing": false
    }
    """
    current_user = get_current_user()
    data = request.get_json()
    
    if not data or 'title' not in data:
        return jsonify({'error': 'Title is required'}), 400
    
    # Parse due_date if provided
    due_date = None
    if 'due_date' in data and data['due_date']:
        try:
            due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Invalid due_date format'}), 400
    
    task = TaskService.create_task(
        workspace_id=get_current_user().workspace_id,
        title=data['title'],
        description=data.get('description'),
        assignee_id=data.get('assignee_id'),
        company_id=data.get('company_id'),
        deal_id=data.get('deal_id'),
        milestone_id=data.get('milestone_id'),
        status=data.get('status', 'not_started'),
        priority=data.get('priority', 'medium'),
        due_date=due_date,
        is_customer_facing=data.get('is_customer_facing', False)
    )
    
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
        'created_at': task.created_at.isoformat()
    }), 201


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
    """
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
    
    pagination = TaskService.list_tasks(
        workspace_id=get_current_user().workspace_id,
        filters=filters,
        page=page,
        per_page=per_page
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
    task = TaskService.get_task(task_id, get_current_user().workspace_id)
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
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
def update_task(task_id):
    """
    Update task fields
    
    Request body can include any of:
    {
        "title": "New title",
        "description": "New description",
        "assignee_id": 2,
        "status": "in_progress",
        "priority": "high",
        "due_date": "2024-12-31T23:59:59",
        "is_customer_facing": true
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Parse due_date if provided
    if 'due_date' in data and data['due_date']:
        try:
            data['due_date'] = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Invalid due_date format'}), 400
    
    task = TaskService.update_task(task_id, get_current_user().workspace_id, **data)
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    return jsonify({
        'id': task.id,
        'title': task.title,
        'description': task.description,
        'assignee_id': task.assignee_id,
        'status': task.status,
        'priority': task.priority,
        'due_date': task.due_date.isoformat() if task.due_date else None,
        'is_customer_facing': task.is_customer_facing,
        'updated_at': task.updated_at.isoformat(),
        'completed_at': task.completed_at.isoformat() if task.completed_at else None
    })


@tasks_bp.route('/api/v1/tasks/<int:task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    """Delete a task"""
    success = TaskService.delete_task(task_id, get_current_user().workspace_id)
    
    if not success:
        return jsonify({'error': 'Task not found'}), 404
    
    return jsonify({'message': 'Task deleted successfully'})


# ============================================================================
# TASK DEPENDENCIES
# ============================================================================

@tasks_bp.route('/api/v1/tasks/<int:task_id>/dependencies', methods=['POST'])
@login_required
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
    
    milestone = TaskService.create_milestone(
        workspace_id=get_current_user().workspace_id,
        name=data['name'],
        company_id=data.get('company_id'),
        due_date=due_date
    )
    
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
    
    milestone = TaskService.update_milestone(milestone_id, get_current_user().workspace_id, **data)
    
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

@tasks_bp.route('/api/v1/tasks/<int:task_id>/comments', methods=['POST'])
@login_required
def add_comment(task_id):
    """
    Add a comment to a task
    
    Request body:
    {
        "content": "Comment text"
    }
    """
    data = request.get_json()
    
    if not data or 'content' not in data:
        return jsonify({'error': 'Content is required'}), 400
    
    comment = TaskService.add_comment(
        task_id=task_id,
        user_id=get_current_user().id,
        content=data['content'],
        workspace_id=get_current_user().workspace_id
    )
    
    if not comment:
        return jsonify({'error': 'Task not found'}), 404
    
    return jsonify({
        'id': comment.id,
        'task_id': comment.task_id,
        'user_id': comment.user_id,
        'content': comment.content,
        'created_at': comment.created_at.isoformat()
    }), 201


@tasks_bp.route('/api/v1/tasks/<int:task_id>/comments', methods=['GET'])
@login_required
def get_comments(task_id):
    """Get all comments for a task"""
    comments = TaskService.get_task_comments(task_id, get_current_user().workspace_id)
    
    return jsonify({
        'comments': [{
            'id': c.id,
            'task_id': c.task_id,
            'user_id': c.user_id,
            'content': c.content,
            'created_at': c.created_at.isoformat()
        } for c in comments]
    })


# ============================================================================
# TASK ATTACHMENTS
# ============================================================================

@tasks_bp.route('/api/v1/tasks/<int:task_id>/attachments', methods=['POST'])
@login_required
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
    
    tasks = TaskService.create_from_template(
        workspace_id=get_current_user().workspace_id,
        template_tasks=data['template_tasks'],
        company_id=data.get('company_id'),
        deal_id=data.get('deal_id'),
        milestone_id=data.get('milestone_id')
    )
    
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
