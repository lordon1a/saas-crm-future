"""
Task Service - Business logic for task and project management
Handles task CRUD, dependencies, milestones, and templates
"""
from models import db
from models_crm import Task, TaskDependency, Milestone, TaskComment, TaskAttachment
from datetime import datetime
from sqlalchemy import and_, or_


class TaskService:
    """Service for managing tasks and projects"""
    
    @staticmethod
    def create_task(workspace_id, title, description=None, assignee_id=None, 
                   company_id=None, deal_id=None, milestone_id=None,
                   status='not_started', priority='medium', due_date=None,
                   is_customer_facing=False):
        """
        Create a new task
        
        Args:
            workspace_id: Workspace ID for multi-tenant isolation
            title: Task title
            description: Task description
            assignee_id: User ID of assignee
            company_id: Associated company ID
            deal_id: Associated deal ID
            milestone_id: Associated milestone ID
            status: Task status (not_started, in_progress, blocked, completed, cancelled)
            priority: Task priority (low, medium, high, urgent)
            due_date: Due date (datetime)
            is_customer_facing: Whether visible in customer portal
            
        Returns:
            Task object
        """
        task = Task(
            workspace_id=workspace_id,
            title=title,
            description=description,
            assignee_id=assignee_id,
            company_id=company_id,
            deal_id=deal_id,
            milestone_id=milestone_id,
            status=status,
            priority=priority,
            due_date=due_date,
            is_customer_facing=is_customer_facing
        )
        
        db.session.add(task)
        db.session.commit()
        
        return task
    
    @staticmethod
    def get_task(task_id, workspace_id):
        """Get task by ID with workspace isolation"""
        return Task.query.filter_by(id=task_id, workspace_id=workspace_id).first()
    
    @staticmethod
    def list_tasks(workspace_id, filters=None, page=1, per_page=50):
        """
        List tasks with optional filters
        
        Args:
            workspace_id: Workspace ID
            filters: Dict with optional keys:
                - assignee_id: Filter by assignee
                - company_id: Filter by company
                - deal_id: Filter by deal
                - milestone_id: Filter by milestone
                - status: Filter by status
                - priority: Filter by priority
                - is_customer_facing: Filter by customer visibility
            page: Page number
            per_page: Items per page
            
        Returns:
            Paginated query result
        """
        query = Task.query.filter_by(workspace_id=workspace_id)
        
        if filters:
            if 'assignee_id' in filters:
                query = query.filter_by(assignee_id=filters['assignee_id'])
            if 'company_id' in filters:
                query = query.filter_by(company_id=filters['company_id'])
            if 'deal_id' in filters:
                query = query.filter_by(deal_id=filters['deal_id'])
            if 'milestone_id' in filters:
                query = query.filter_by(milestone_id=filters['milestone_id'])
            if 'status' in filters:
                query = query.filter_by(status=filters['status'])
            if 'priority' in filters:
                query = query.filter_by(priority=filters['priority'])
            if 'is_customer_facing' in filters:
                query = query.filter_by(is_customer_facing=filters['is_customer_facing'])
        
        return query.order_by(Task.due_date.asc().nullslast(), Task.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
    
    @staticmethod
    def update_task(task_id, workspace_id, **kwargs):
        """
        Update task fields
        
        Args:
            task_id: Task ID
            workspace_id: Workspace ID
            **kwargs: Fields to update
            
        Returns:
            Updated task or None if not found
        """
        task = TaskService.get_task(task_id, workspace_id)
        if not task:
            return None

        previous_status = task.status
        
        # Update allowed fields
        allowed_fields = ['title', 'description', 'assignee_id', 'company_id', 
                         'deal_id', 'milestone_id', 'status', 'priority', 
                         'due_date', 'is_customer_facing']
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(task, field, value)
        
        # Set completed_at when status changes to completed
        if 'status' in kwargs and kwargs['status'] == 'completed':
            task.completed_at = datetime.utcnow()
        
        db.session.commit()

        if previous_status != 'completed' and task.status == 'completed':
            try:
                from services.webhook_service import WebhookService
                WebhookService.dispatch_event(workspace_id, 'task.completed', {
                    'task_id': task.id,
                    'title': task.title,
                    'company_id': task.company_id,
                    'deal_id': task.deal_id,
                    'milestone_id': task.milestone_id,
                    'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                    'updated_at': task.updated_at.isoformat() if task.updated_at else None,
                })
            except Exception:
                pass

        return task
    
    @staticmethod
    def delete_task(task_id, workspace_id):
        """Delete task"""
        task = TaskService.get_task(task_id, workspace_id)
        if not task:
            return False
        
        db.session.delete(task)
        db.session.commit()
        return True
    
    # ========================================================================
    # TASK DEPENDENCIES
    # ========================================================================
    
    @staticmethod
    def add_dependency(task_id, depends_on_task_id, workspace_id):
        """
        Add a task dependency
        
        Args:
            task_id: Task that depends on another
            depends_on_task_id: Task that must be completed first
            workspace_id: Workspace ID
            
        Returns:
            TaskDependency object or None if validation fails
        """
        # Validate both tasks exist and belong to same workspace
        task = TaskService.get_task(task_id, workspace_id)
        depends_on_task = TaskService.get_task(depends_on_task_id, workspace_id)
        
        if not task or not depends_on_task:
            return None
        
        # Prevent self-dependency
        if task_id == depends_on_task_id:
            return None
        
        # Check for circular dependencies
        if TaskService._has_circular_dependency(task_id, depends_on_task_id):
            return None
        
        # Check if dependency already exists
        existing = TaskDependency.query.filter_by(
            task_id=task_id,
            depends_on_task_id=depends_on_task_id
        ).first()
        
        if existing:
            return existing
        
        dependency = TaskDependency(
            task_id=task_id,
            depends_on_task_id=depends_on_task_id
        )
        
        db.session.add(dependency)
        db.session.commit()
        
        return dependency
    
    @staticmethod
    def remove_dependency(task_id, depends_on_task_id, workspace_id):
        """Remove a task dependency"""
        # Validate task belongs to workspace
        task = TaskService.get_task(task_id, workspace_id)
        if not task:
            return False
        
        dependency = TaskDependency.query.filter_by(
            task_id=task_id,
            depends_on_task_id=depends_on_task_id
        ).first()
        
        if not dependency:
            return False
        
        db.session.delete(dependency)
        db.session.commit()
        return True
    
    @staticmethod
    def get_task_dependencies(task_id, workspace_id):
        """Get all tasks that this task depends on"""
        task = TaskService.get_task(task_id, workspace_id)
        if not task:
            return []
        
        dependencies = TaskDependency.query.filter_by(task_id=task_id).all()
        depends_on_ids = [d.depends_on_task_id for d in dependencies]
        
        return Task.query.filter(
            Task.id.in_(depends_on_ids),
            Task.workspace_id == workspace_id
        ).all()
    
    @staticmethod
    def get_blocked_tasks(task_id, workspace_id):
        """Get all tasks that are blocked by this task"""
        task = TaskService.get_task(task_id, workspace_id)
        if not task:
            return []
        
        dependencies = TaskDependency.query.filter_by(depends_on_task_id=task_id).all()
        blocked_ids = [d.task_id for d in dependencies]
        
        return Task.query.filter(
            Task.id.in_(blocked_ids),
            Task.workspace_id == workspace_id
        ).all()
    
    @staticmethod
    def _has_circular_dependency(task_id, depends_on_task_id):
        """
        Check if adding this dependency would create a circular dependency
        Uses depth-first search to detect cycles
        """
        visited = set()
        
        def dfs(current_id):
            if current_id == task_id:
                return True
            if current_id in visited:
                return False
            
            visited.add(current_id)
            
            # Get all tasks that current_id depends on
            dependencies = TaskDependency.query.filter_by(task_id=current_id).all()
            for dep in dependencies:
                if dfs(dep.depends_on_task_id):
                    return True
            
            return False
        
        return dfs(depends_on_task_id)
    
    @staticmethod
    def can_start_task(task_id, workspace_id):
        """
        Check if a task can be started (all dependencies completed)
        
        Returns:
            (bool, list): (can_start, list of incomplete dependencies)
        """
        dependencies = TaskService.get_task_dependencies(task_id, workspace_id)
        
        incomplete = [d for d in dependencies if d.status != 'completed']
        
        return len(incomplete) == 0, incomplete
    
    # ========================================================================
    # MILESTONES
    # ========================================================================
    
    @staticmethod
    def create_milestone(workspace_id, name, company_id=None, due_date=None):
        """Create a new milestone"""
        milestone = Milestone(
            workspace_id=workspace_id,
            name=name,
            company_id=company_id,
            due_date=due_date,
            status='active'
        )
        
        db.session.add(milestone)
        db.session.commit()
        
        return milestone
    
    @staticmethod
    def get_milestone(milestone_id, workspace_id):
        """Get milestone by ID"""
        return Milestone.query.filter_by(id=milestone_id, workspace_id=workspace_id).first()
    
    @staticmethod
    def list_milestones(workspace_id, company_id=None, page=1, per_page=50):
        """List milestones with optional company filter"""
        query = Milestone.query.filter_by(workspace_id=workspace_id)
        
        if company_id:
            query = query.filter_by(company_id=company_id)
        
        return query.order_by(Milestone.due_date.asc().nullslast()).paginate(
            page=page, per_page=per_page, error_out=False
        )
    
    @staticmethod
    def calculate_milestone_progress(milestone_id, workspace_id):
        """
        Calculate milestone completion percentage
        
        Returns:
            dict with:
                - total_tasks: Total number of tasks
                - completed_tasks: Number of completed tasks
                - progress_percentage: Completion percentage (0-100)
        """
        milestone = TaskService.get_milestone(milestone_id, workspace_id)
        if not milestone:
            return None
        
        tasks = Task.query.filter_by(
            milestone_id=milestone_id,
            workspace_id=workspace_id
        ).all()
        
        total = len(tasks)
        completed = len([t for t in tasks if t.status == 'completed'])
        
        progress = (completed / total * 100) if total > 0 else 0
        
        return {
            'total_tasks': total,
            'completed_tasks': completed,
            'progress_percentage': round(progress, 2)
        }
    
    @staticmethod
    def update_milestone(milestone_id, workspace_id, **kwargs):
        """Update milestone fields"""
        milestone = TaskService.get_milestone(milestone_id, workspace_id)
        if not milestone:
            return None
        
        allowed_fields = ['name', 'company_id', 'due_date', 'status']
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(milestone, field, value)
        
        db.session.commit()
        return milestone
    
    # ========================================================================
    # TASK COMMENTS
    # ========================================================================
    
    @staticmethod
    def add_comment(task_id, user_id, content, workspace_id):
        """Add a comment to a task"""
        task = TaskService.get_task(task_id, workspace_id)
        if not task:
            return None
        
        comment = TaskComment(
            task_id=task_id,
            user_id=user_id,
            content=content
        )
        
        db.session.add(comment)
        db.session.commit()
        
        return comment
    
    @staticmethod
    def get_task_comments(task_id, workspace_id):
        """Get all comments for a task"""
        task = TaskService.get_task(task_id, workspace_id)
        if not task:
            return []
        
        return TaskComment.query.filter_by(task_id=task_id).order_by(
            TaskComment.created_at.asc()
        ).all()
    
    # ========================================================================
    # TASK ATTACHMENTS
    # ========================================================================
    
    @staticmethod
    def add_attachment(task_id, file_name, file_path, file_size, uploaded_by, workspace_id):
        """Add a file attachment to a task"""
        task = TaskService.get_task(task_id, workspace_id)
        if not task:
            return None
        
        attachment = TaskAttachment(
            task_id=task_id,
            file_name=file_name,
            file_path=file_path,
            file_size=file_size,
            uploaded_by=uploaded_by
        )
        
        db.session.add(attachment)
        db.session.commit()
        
        return attachment
    
    @staticmethod
    def get_task_attachments(task_id, workspace_id):
        """Get all attachments for a task"""
        task = TaskService.get_task(task_id, workspace_id)
        if not task:
            return []
        
        return TaskAttachment.query.filter_by(task_id=task_id).order_by(
            TaskAttachment.created_at.desc()
        ).all()
    
    # ========================================================================
    # TASK TEMPLATES
    # ========================================================================
    
    @staticmethod
    def create_from_template(workspace_id, template_tasks, company_id=None, 
                            deal_id=None, milestone_id=None):
        """
        Create multiple tasks from a template
        
        Args:
            workspace_id: Workspace ID
            template_tasks: List of dicts with task data:
                [
                    {
                        'title': 'Task 1',
                        'description': 'Description',
                        'priority': 'high',
                        'days_offset': 0,  # Days from today for due_date
                        'assignee_id': 1,
                        'depends_on_index': None  # Index in template_tasks list
                    },
                    ...
                ]
            company_id: Company to associate tasks with
            deal_id: Deal to associate tasks with
            milestone_id: Milestone to group tasks under
            
        Returns:
            List of created Task objects
        """
        created_tasks = []
        
        for i, template in enumerate(template_tasks):
            # Calculate due date from offset
            due_date = None
            if 'days_offset' in template:
                from datetime import timedelta
                due_date = datetime.utcnow() + timedelta(days=template['days_offset'])
            
            task = TaskService.create_task(
                workspace_id=workspace_id,
                title=template['title'],
                description=template.get('description'),
                assignee_id=template.get('assignee_id'),
                company_id=company_id,
                deal_id=deal_id,
                milestone_id=milestone_id,
                priority=template.get('priority', 'medium'),
                due_date=due_date,
                is_customer_facing=template.get('is_customer_facing', False)
            )
            
            created_tasks.append(task)
        
        # Add dependencies after all tasks are created
        for i, template in enumerate(template_tasks):
            if 'depends_on_index' in template and template['depends_on_index'] is not None:
                depends_on_index = template['depends_on_index']
                if 0 <= depends_on_index < len(created_tasks):
                    TaskService.add_dependency(
                        created_tasks[i].id,
                        created_tasks[depends_on_index].id,
                        workspace_id
                    )
        
        return created_tasks
    
    # ========================================================================
    # CUSTOMER PORTAL QUERIES
    # ========================================================================
    
    @staticmethod
    def get_customer_facing_tasks(workspace_id, company_id):
        """
        Get all customer-facing tasks for a company
        Used by customer portal
        """
        return Task.query.filter_by(
            workspace_id=workspace_id,
            company_id=company_id,
            is_customer_facing=True
        ).order_by(Task.due_date.asc().nullslast(), Task.created_at.desc()).all()
