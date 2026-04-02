"""
Task Service - Business logic for task and project management
Handles task CRUD, dependencies, milestones, and templates
"""
from models import db, User
from models_crm import (
    Activity,
    Company,
    Contact,
    Deal,
    Milestone,
    NotificationPreference,
    Task,
    TaskAttachment,
    TaskComment,
    TaskDependency,
    TaskNotification,
)
from datetime import UTC, datetime, timedelta
from sqlalchemy import and_, or_
import json
import logging

logger = logging.getLogger(__name__)


class TaskService:
    """Service for managing tasks and projects"""

    @staticmethod
    def _get_workspace_user(workspace_id, user_id):
        return User.query.filter_by(
            id=user_id,
            workspace_id=workspace_id,
            is_active=True,
        ).first()

    @staticmethod
    def _get_workspace_company(workspace_id, company_id):
        return Company.query.filter_by(
            id=company_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()

    @staticmethod
    def _get_workspace_deal(workspace_id, deal_id):
        return Deal.query.filter_by(
            id=deal_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()

    @staticmethod
    def _get_workspace_contact(workspace_id, contact_id):
        return Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()

    @staticmethod
    def _validate_task_relations(
        workspace_id,
        assignee_id=None,
        company_id=None,
        deal_id=None,
        milestone_id=None,
        contact_id=None,
    ):
        """Validate task-linked entities within a workspace boundary."""
        assignee = None
        company = None
        deal = None
        milestone = None
        contact = None

        if assignee_id is not None:
            assignee = TaskService._get_workspace_user(workspace_id, assignee_id)
            if not assignee:
                raise ValueError("Assignee not found")

        if company_id is not None:
            company = TaskService._get_workspace_company(workspace_id, company_id)
            if not company:
                raise ValueError("Company not found")

        if deal_id is not None:
            deal = TaskService._get_workspace_deal(workspace_id, deal_id)
            if not deal:
                raise ValueError("Deal not found")

        if milestone_id is not None:
            milestone = TaskService.get_milestone(milestone_id, workspace_id)
            if not milestone:
                raise ValueError("Milestone not found")

        if contact_id is not None:
            contact = TaskService._get_workspace_contact(workspace_id, contact_id)
            if not contact:
                raise ValueError("Contact not found")

        if company and deal and deal.company_id and deal.company_id != company.id:
            raise ValueError("Deal does not belong to selected company")

        if company and milestone and milestone.company_id and milestone.company_id != company.id:
            raise ValueError("Milestone does not belong to selected company")

        if company and contact and contact.company_id and contact.company_id != company.id:
            raise ValueError("Contact does not belong to selected company")

        return {
            'assignee': assignee,
            'company': company,
            'deal': deal,
            'milestone': milestone,
            'contact': contact,
        }
    
    @staticmethod
    def create_task(workspace_id, title, description=None, assignee_id=None, 
                   company_id=None, deal_id=None, milestone_id=None,
                   status='not_started', priority='medium', due_date=None,
                   is_customer_facing=False, start_time=None, end_time=None,
                   timezone='UTC', task_type='task', contact_id=None, user_id=None):
        """
        Create a new task with calendar/notification support
        
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
            start_time: Start time for scheduled tasks
            end_time: End time for scheduled tasks
            timezone: Timezone (e.g., 'Europe/Istanbul', 'UTC')
            task_type: Task type (call, meeting, email, todo, follow_up, other)
            contact_id: Associated contact ID
            user_id: User creating the task (for activity log)
            
        Returns:
            Task object
        """
        # Validasyon
        if not title:
            raise ValueError("Görev başlığı zorunludur")
        
        if start_time and end_time:
            if start_time >= end_time:
                raise ValueError("Bitiş zamanı başlangıç zamanından sonra olmalıdır")

        TaskService._validate_task_relations(
            workspace_id=workspace_id,
            assignee_id=assignee_id,
            company_id=company_id,
            deal_id=deal_id,
            milestone_id=milestone_id,
            contact_id=contact_id,
        )
        
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
            is_customer_facing=is_customer_facing,
            start_time=start_time,
            end_time=end_time,
            timezone=timezone,
            task_type=task_type,
            contact_id=contact_id
        )
        
        db.session.add(task)
        db.session.flush()  # ID almak için
        
        # Bildirim oluştur
        if task.start_time and task.assignee_id:
            TaskService._create_task_notifications(task)
        
        # Activity log
        if user_id:
            TaskService._create_activity_log(
                workspace_id=workspace_id,
                user_id=user_id,
                task_id=task.id,
                action='task_created',
                details=f"Görev oluşturuldu: {task.title}"
            )
        
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
    def update_task(task_id, workspace_id, user_id=None, **kwargs):
        """
        Update task fields with notification refresh support
        
        Args:
            task_id: Task ID
            workspace_id: Workspace ID
            user_id: User updating the task (for activity log)
            **kwargs: Fields to update
            
        Returns:
            Updated task or None if not found
        """
        task = TaskService.get_task(task_id, workspace_id)
        if not task:
            return None

        previous_status = task.status

        relation_fields = {'assignee_id', 'company_id', 'deal_id', 'milestone_id', 'contact_id'}
        if relation_fields.intersection(kwargs.keys()):
            final_assignee_id = kwargs.get('assignee_id', task.assignee_id)
            final_company_id = kwargs.get('company_id', task.company_id)
            final_deal_id = kwargs.get('deal_id', task.deal_id)
            final_milestone_id = kwargs.get('milestone_id', task.milestone_id)
            final_contact_id = kwargs.get('contact_id', task.contact_id)

            TaskService._validate_task_relations(
                workspace_id=workspace_id,
                assignee_id=final_assignee_id,
                company_id=final_company_id,
                deal_id=final_deal_id,
                milestone_id=final_milestone_id,
                contact_id=final_contact_id,
            )
        
        # Zaman değişikliği kontrolü
        time_changed = False
        if 'start_time' in kwargs and kwargs['start_time'] != task.start_time:
            time_changed = True
            task.start_time = kwargs['start_time']
        
        if 'end_time' in kwargs and kwargs['end_time'] != task.end_time:
            time_changed = True
            task.end_time = kwargs['end_time']
        
        # Update allowed fields
        allowed_fields = ['title', 'description', 'assignee_id', 'company_id', 
                         'deal_id', 'milestone_id', 'status', 'priority', 
                         'due_date', 'is_customer_facing', 'timezone', 'task_type', 'contact_id']
        
        for field, value in kwargs.items():
            if field in allowed_fields and field not in ['start_time', 'end_time']:
                setattr(task, field, value)
        
        # Set completed_at when status changes to completed
        if 'status' in kwargs and kwargs['status'] == 'completed':
            task.completed_at = datetime.utcnow()
        elif 'status' in kwargs and kwargs['status'] != 'completed':
            task.completed_at = None
        
        # Zaman değişti ise bildirimleri yeniden oluştur
        if time_changed and task.assignee_id:
            # Eski bildirimleri sil (henüz gönderilmemişleri)
            TaskNotification.query.filter_by(
                task_id=task.id,
                is_sent=False
            ).delete()
            
            # Yeni bildirimler oluştur
            if task.start_time:
                TaskService._create_task_notifications(task)
        
        # Activity log
        if user_id:
            TaskService._create_activity_log(
                workspace_id=workspace_id,
                user_id=user_id,
                task_id=task.id,
                action='task_updated',
                details=f"Görev güncellendi: {task.title}"
            )
        
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
        if company_id is not None and not TaskService._get_workspace_company(workspace_id, company_id):
            raise ValueError("Company not found")

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

        if 'company_id' in kwargs and kwargs['company_id'] is not None:
            if not TaskService._get_workspace_company(workspace_id, kwargs['company_id']):
                raise ValueError("Company not found")
        
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
    # CALENDAR & NOTIFICATION SUPPORT
    # ========================================================================
    
    @staticmethod
    def _create_task_notifications(task):
        """
        Görev için bildirim kayıtları oluştur.
        
        Args:
            task: Task instance
        """
        # Kullanıcı tercihlerini al
        pref = NotificationPreference.query.filter_by(
            workspace_id=task.workspace_id,
            user_id=task.assignee_id
        ).first()
        
        if not pref:
            # Varsayılan tercihler
            pref = NotificationPreference(
                workspace_id=task.workspace_id,
                user_id=task.assignee_id,
                reminder_minutes_before=15
            )
            db.session.add(pref)
            db.session.flush()
        
        # Hatırlatma bildirimi
        if pref.task_reminder_enabled and task.start_time:
            notify_at = task.start_time - timedelta(minutes=pref.reminder_minutes_before)
            
            # Geçmiş zaman kontrolü
            if notify_at > datetime.utcnow():
                notification = TaskNotification(
                    workspace_id=task.workspace_id,
                    task_id=task.id,
                    user_id=task.assignee_id,
                    notify_at=notify_at,
                    message=f"Hatırlatma: '{task.title}' görevi {pref.reminder_minutes_before} dakika içinde başlayacak",
                    notification_type='task_reminder'
                )
                db.session.add(notification)
    
    @staticmethod
    def get_tasks_for_calendar(workspace_id, user_id, start_date, end_date, filters=None):
        """
        Takvim görünümü için görevleri getir.
        
        Args:
            workspace_id: Workspace ID
            user_id: Kullanıcı ID
            start_date: Başlangıç tarihi
            end_date: Bitiş tarihi
            filters: Opsiyonel filtreler (task_type, assignee_id, status)
        
        Returns:
            List[dict]: Takvim event formatında görevler
        """
        query = Task.query.filter(
            Task.workspace_id == workspace_id,
            Task.start_time.isnot(None),
            Task.start_time >= start_date,
            Task.start_time <= end_date
        )
        
        # Filtreler
        if filters:
            if filters.get('task_type'):
                query = query.filter(Task.task_type == filters['task_type'])
            
            if filters.get('assignee_id'):
                if filters['assignee_id'] == 'me':
                    query = query.filter(Task.assignee_id == user_id)
                else:
                    query = query.filter(Task.assignee_id == filters['assignee_id'])
            
            if filters.get('status'):
                query = query.filter(Task.status == filters['status'])
        
        tasks = query.order_by(Task.start_time.asc()).all()
        
        return [task.to_calendar_event() for task in tasks]
    
    @staticmethod
    def mark_overdue_tasks(workspace_id):
        """
        Süresi geçmiş görevleri 'overdue' olarak işaretle.
        Background job tarafından çağrılır.
        
        Args:
            workspace_id: Workspace ID
        """
        now = datetime.now(UTC).replace(tzinfo=None)

        # Include legacy 'pending' for backward compatibility with older rows.
        overdue_eligible_statuses = ['not_started', 'in_progress', 'blocked', 'pending']
        
        overdue_tasks = Task.query.filter(
            Task.workspace_id == workspace_id,
            Task.status.in_(overdue_eligible_statuses),
            Task.end_time.isnot(None),
            Task.end_time < now
        ).all()
        
        for task in overdue_tasks:
            task.status = 'overdue'
            
            # Overdue bildirimi oluştur
            if task.assignee_id:
                pref = NotificationPreference.query.filter_by(
                    workspace_id=task.workspace_id,
                    user_id=task.assignee_id
                ).first()
                
                if pref and pref.task_overdue_enabled:
                    notification = TaskNotification(
                        workspace_id=task.workspace_id,
                        task_id=task.id,
                        user_id=task.assignee_id,
                        notify_at=now,
                        message=f"Görev süresi geçti: '{task.title}'",
                        notification_type='task_overdue'
                    )
                    db.session.add(notification)
        
        db.session.commit()
    
    @staticmethod
    def _create_activity_log(workspace_id, user_id, task_id, action, details):
        """
        Activity log oluştur
        
        Args:
            workspace_id: Workspace ID
            user_id: User ID
            task_id: Task ID
            action: Action type (task_created, task_updated, etc.)
            details: Details text
        """
        activity = Activity(
            workspace_id=workspace_id,
            user_id=user_id,
            activity_type='task',
            subject=action,
            body=details,
            extra_data=json.dumps({'task_id': task_id})
        )
        db.session.add(activity)
    
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
