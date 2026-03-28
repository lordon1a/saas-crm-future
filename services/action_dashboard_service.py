"""
Action Dashboard Service

Business logic for the daily action dashboard bell feature.
Calculates, ranks, and manages prioritized action items for sales representatives.
"""

from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Set, Optional
from sqlalchemy import and_, or_, func
from models_crm import (
    db, Contact, Deal, Task, DismissedAction, 
    DashboardSettings, WidgetEngagement
)


@dataclass
class ActionItem:
    """
    Ephemeral action item (not persisted to database).
    Generated on-demand by priority engine.
    """
    id: str  # Format: "{type}:{entity_id}"
    action_type: str  # 'contact_followup', 'deal_update', 'task_overdue'
    priority: str  # 'urgent', 'high', 'medium'
    priority_score: int  # 0-100 for sorting
    entity_type: str  # 'contact', 'deal', 'task'
    entity_id: int
    entity_name: str
    recommended_action: str  # "Follow up with John Doe"
    context: dict  # Additional metadata
    last_activity_at: Optional[datetime]


class ActionDashboardService:
    """
    Business logic for daily action dashboard.
    Calculates, ranks, and manages action items.
    """
    
    @staticmethod
    def get_or_create_settings(workspace_id: int) -> DashboardSettings:
        """
        Get workspace settings or create with defaults.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            DashboardSettings instance
        """
        settings = DashboardSettings.query.filter_by(workspace_id=workspace_id).first()
        
        if not settings:
            settings = DashboardSettings(workspace_id=workspace_id)
            db.session.add(settings)
            db.session.commit()
        
        return settings
    
    @staticmethod
    def update_settings(workspace_id: int, data: dict) -> DashboardSettings:
        """
        Update workspace dashboard settings.
        
        Args:
            workspace_id: Workspace ID
            data: Dictionary with settings to update
            
        Returns:
            Updated DashboardSettings instance
        """
        settings = ActionDashboardService.get_or_create_settings(workspace_id)
        
        # Update fields if provided
        if 'high_score_threshold' in data:
            settings.high_score_threshold = data['high_score_threshold']
        if 'medium_score_threshold' in data:
            settings.medium_score_threshold = data['medium_score_threshold']
        if 'high_score_staleness_days' in data:
            settings.high_score_staleness_days = data['high_score_staleness_days']
        if 'medium_score_staleness_days' in data:
            settings.medium_score_staleness_days = data['medium_score_staleness_days']
        if 'deal_close_warning_days' in data:
            settings.deal_close_warning_days = data['deal_close_warning_days']
        if 'deal_stage_stale_days' in data:
            settings.deal_stage_stale_days = data['deal_stage_stale_days']
        if 'deal_negotiation_stale_days' in data:
            settings.deal_negotiation_stale_days = data['deal_negotiation_stale_days']
        
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        
        return settings
    
    @staticmethod
    def calculate_action_items(workspace_id: int, user_id: int, limit: int = 10) -> List[ActionItem]:
        """
        Calculate and return prioritized action items for a user.
        
        Algorithm:
        1. Get workspace settings (or defaults)
        2. Query stale high-score contacts
        3. Query deals needing attention
        4. Query overdue/due-today tasks
        5. Filter out dismissed actions
        6. Score and rank all candidates
        7. Return top N items
        
        Args:
            workspace_id: Workspace ID
            user_id: User ID
            limit: Maximum number of actions to return (default 10)
            
        Returns:
            List of ActionItem objects, sorted by priority_score desc
        """
        # Get settings
        settings = ActionDashboardService.get_or_create_settings(workspace_id)
        
        # Get dismissed action IDs
        dismissed_ids = ActionDashboardService._get_dismissed_action_ids(workspace_id, user_id)
        
        # Collect candidates from all sources
        candidates = []
        candidates.extend(ActionDashboardService.prioritize_stale_contacts(workspace_id, user_id, settings))
        candidates.extend(ActionDashboardService.prioritize_deals(workspace_id, user_id, settings))
        candidates.extend(ActionDashboardService.prioritize_overdue_tasks(workspace_id, user_id))
        
        # Rank and filter
        return ActionDashboardService.rank_and_merge(candidates, dismissed_ids, limit)
    
    @staticmethod
    def prioritize_stale_contacts(workspace_id: int, user_id: int, settings: DashboardSettings) -> List[ActionItem]:
        """
        Find contacts with high lead scores and no recent activity.
        
        Query:
        - lead_score >= high_score_threshold AND 
          last_activity_at < (now - high_score_staleness_days)
          → Priority: High, Score: 90
        
        - lead_score >= medium_score_threshold AND 
          last_activity_at < (now - medium_score_staleness_days)
          → Priority: Medium, Score: 70
        
        Args:
            workspace_id: Workspace ID
            user_id: User ID
            settings: DashboardSettings instance
            
        Returns:
            List of ActionItem objects
        """
        now = datetime.utcnow()
        high_stale_date = now - timedelta(days=settings.high_score_staleness_days)
        medium_stale_date = now - timedelta(days=settings.medium_score_staleness_days)
        
        actions = []
        
        # High priority: High score + very stale
        high_contacts = Contact.query.filter(
            Contact.workspace_id == workspace_id,
            Contact.is_deleted == False,
            Contact.lead_score >= settings.high_score_threshold,
            or_(
                Contact.last_activity_at < high_stale_date,
                Contact.last_activity_at == None
            )
        ).limit(25).all()
        
        for contact in high_contacts:
            days_since = (now - contact.last_activity_at).days if contact.last_activity_at else 999
            actions.append(ActionItem(
                id=f"contact:{contact.id}",
                action_type="contact_followup",
                priority="high",
                priority_score=90,
                entity_type="contact",
                entity_id=contact.id,
                entity_name=contact.full_name or contact.phone or "Unknown",
                recommended_action=f"Follow up with {contact.full_name or contact.phone}",
                context={
                    "lead_score": contact.lead_score,
                    "days_since_activity": days_since
                },
                last_activity_at=contact.last_activity_at
            ))
        
        # Medium priority: Medium score + stale
        medium_contacts = Contact.query.filter(
            Contact.workspace_id == workspace_id,
            Contact.is_deleted == False,
            Contact.lead_score >= settings.medium_score_threshold,
            Contact.lead_score < settings.high_score_threshold,
            or_(
                Contact.last_activity_at < medium_stale_date,
                Contact.last_activity_at == None
            )
        ).limit(25).all()
        
        for contact in medium_contacts:
            days_since = (now - contact.last_activity_at).days if contact.last_activity_at else 999
            actions.append(ActionItem(
                id=f"contact:{contact.id}",
                action_type="contact_followup",
                priority="medium",
                priority_score=70,
                entity_type="contact",
                entity_id=contact.id,
                entity_name=contact.full_name or contact.phone or "Unknown",
                recommended_action=f"Follow up with {contact.full_name or contact.phone}",
                context={
                    "lead_score": contact.lead_score,
                    "days_since_activity": days_since
                },
                last_activity_at=contact.last_activity_at
            ))
        
        return actions
    
    @staticmethod
    def prioritize_deals(workspace_id: int, user_id: int, settings: DashboardSettings) -> List[ActionItem]:
        """
        Find deals requiring attention based on close date, stage, activity.
        
        Query:
        - expected_close_date within deal_close_warning_days AND status = 'open'
          → Priority: High, Score: 95
        
        - stage_entered_at > deal_stage_stale_days
          → Priority: Medium, Score: 75
        
        - stage in ('Negotiation', 'Proposal') AND 
          last_activity_at < (now - deal_negotiation_stale_days)
          → Priority: High, Score: 85
        
        Args:
            workspace_id: Workspace ID
            user_id: User ID
            settings: DashboardSettings instance
            
        Returns:
            List of ActionItem objects
        """
        now = datetime.utcnow()
        close_warning_date = now + timedelta(days=settings.deal_close_warning_days)
        stage_stale_date = now - timedelta(days=settings.deal_stage_stale_days)
        negotiation_stale_date = now - timedelta(days=settings.deal_negotiation_stale_days)
        
        actions = []
        
        # High priority: Close date approaching
        closing_soon = Deal.query.filter(
            Deal.workspace_id == workspace_id,
            Deal.is_deleted == False,
            Deal.status == 'open',
            Deal.expected_close_date != None,
            Deal.expected_close_date <= close_warning_date
        ).limit(25).all()
        
        for deal in closing_soon:
            days_until_close = (deal.expected_close_date - now.date()).days if deal.expected_close_date else 0
            actions.append(ActionItem(
                id=f"deal:{deal.id}",
                action_type="deal_update",
                priority="high",
                priority_score=95,
                entity_type="deal",
                entity_id=deal.id,
                entity_name=deal.name or "Untitled Deal",
                recommended_action=f"Update deal: {deal.name} (closes in {days_until_close} days)",
                context={
                    "value": float(deal.value) if deal.value else 0,
                    "stage": deal.stage.name if deal.stage else "Unknown",
                    "days_until_close": days_until_close
                },
                last_activity_at=deal.last_activity_at
            ))
        
        # Medium priority: Stale stage
        stale_stage = Deal.query.filter(
            Deal.workspace_id == workspace_id,
            Deal.is_deleted == False,
            Deal.status == 'open',
            Deal.stage_entered_at != None,
            Deal.stage_entered_at < stage_stale_date
        ).limit(25).all()
        
        for deal in stale_stage:
            days_in_stage = (now - deal.stage_entered_at).days if deal.stage_entered_at else 0
            actions.append(ActionItem(
                id=f"deal:{deal.id}",
                action_type="deal_update",
                priority="medium",
                priority_score=75,
                entity_type="deal",
                entity_id=deal.id,
                entity_name=deal.name or "Untitled Deal",
                recommended_action=f"Update deal: {deal.name} (in stage {days_in_stage} days)",
                context={
                    "value": float(deal.value) if deal.value else 0,
                    "stage": deal.stage.name if deal.stage else "Unknown",
                    "days_in_stage": days_in_stage
                },
                last_activity_at=deal.last_activity_at
            ))
        
        return actions
    
    @staticmethod
    def prioritize_overdue_tasks(workspace_id: int, user_id: int) -> List[ActionItem]:
        """
        Find overdue and due-today tasks.
        
        Query:
        - due_date < today AND status != 'completed'
          → Priority: Urgent, Score: 100
        
        - due_date = today AND status != 'completed'
          → Priority: High, Score: 90
        
        Args:
            workspace_id: Workspace ID
            user_id: User ID
            
        Returns:
            List of ActionItem objects
        """
        now = datetime.utcnow()
        today = now.date()
        actions = []
        
        # Urgent: Overdue tasks
        overdue = Task.query.filter(
            Task.workspace_id == workspace_id,
            Task.status != 'completed',
            Task.due_date != None,
            Task.due_date < now
        ).limit(25).all()
        
        for task in overdue:
            # Convert due_date to date for comparison if it's datetime
            task_date = task.due_date.date() if isinstance(task.due_date, datetime) else task.due_date
            days_overdue = (today - task_date).days if task_date else 0
            actions.append(ActionItem(
                id=f"task:{task.id}",
                action_type="task_overdue",
                priority="urgent",
                priority_score=100,
                entity_type="task",
                entity_id=task.id,
                entity_name=task.title or "Untitled Task",
                recommended_action=f"Complete overdue task: {task.title}",
                context={
                    "days_overdue": days_overdue,
                    "assigned_to": task.assignee_id
                },
                last_activity_at=None
            ))
        
        # High: Due today
        # For datetime fields, check if date part equals today
        due_today = Task.query.filter(
            Task.workspace_id == workspace_id,
            Task.status != 'completed',
            Task.due_date != None
        ).all()
        
        # Filter in Python to handle datetime comparison
        due_today_filtered = [
            task for task in due_today 
            if (task.due_date.date() if isinstance(task.due_date, datetime) else task.due_date) == today
        ]
        
        for task in due_today_filtered[:25]:  # Limit to 25
            actions.append(ActionItem(
                id=f"task:{task.id}",
                action_type="task_overdue",
                priority="high",
                priority_score=90,
                entity_type="task",
                entity_id=task.id,
                entity_name=task.title or "Untitled Task",
                recommended_action=f"Complete task due today: {task.title}",
                context={
                    "due_today": True,
                    "assigned_to": task.assignee_id
                },
                last_activity_at=None
            ))
        
        return actions
    
    @staticmethod
    def rank_and_merge(candidates: List[ActionItem], dismissed_ids: Set[str], limit: int = 10) -> List[ActionItem]:
        """
        Filter dismissed items, sort by priority_score, return top N.
        
        Args:
            candidates: List of ActionItem objects
            dismissed_ids: Set of dismissed action IDs
            limit: Maximum number to return
            
        Returns:
            Filtered and sorted list of ActionItem objects
        """
        # Filter out dismissed
        filtered = [a for a in candidates if a.id not in dismissed_ids]
        
        # Sort by priority_score descending
        sorted_actions = sorted(filtered, key=lambda x: x.priority_score, reverse=True)
        
        # Return top N
        return sorted_actions[:limit]
    
    @staticmethod
    def dismiss_action(workspace_id: int, user_id: int, action_id: str) -> bool:
        """
        Mark action as dismissed for 24 hours.
        Creates DismissedAction record with expires_at = now + 24h.
        
        Args:
            workspace_id: Workspace ID
            user_id: User ID
            action_id: Action ID (format: "type:id")
            
        Returns:
            True if successful
        """
        try:
            dismissed_at = datetime.utcnow()
            expires_at = dismissed_at + timedelta(hours=24)
            
            dismissed = DismissedAction(
                workspace_id=workspace_id,
                user_id=user_id,
                action_id=action_id,
                dismissed_at=dismissed_at,
                expires_at=expires_at
            )
            
            db.session.add(dismissed)
            db.session.commit()
            
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Error dismissing action: {e}")
            return False
    
    @staticmethod
    def complete_action(workspace_id: int, user_id: int, action_id: str) -> bool:
        """
        Complete the underlying task if action_type is 'task_overdue'.
        For other types, just dismiss the action.
        
        Args:
            workspace_id: Workspace ID
            user_id: User ID
            action_id: Action ID (format: "type:id")
            
        Returns:
            True if successful
        """
        try:
            # Parse action_id
            parts = action_id.split(':')
            if len(parts) != 2:
                return False
            
            action_type, entity_id = parts
            
            # If it's a task, mark as completed
            if action_type == 'task':
                task = Task.query.filter_by(
                    id=int(entity_id),
                    workspace_id=workspace_id
                ).first()
                
                if task:
                    task.status = 'completed'
                    db.session.commit()
            
            # Dismiss the action
            return ActionDashboardService.dismiss_action(workspace_id, user_id, action_id)
            
        except Exception as e:
            db.session.rollback()
            print(f"Error completing action: {e}")
            return False
    
    @staticmethod
    def track_engagement(workspace_id: int, user_id: int, event_type: str, 
                        action_id: str = None, action_type: str = None, 
                        priority: str = None):
        """
        Log widget engagement event for analytics.
        
        Args:
            workspace_id: Workspace ID
            user_id: User ID
            event_type: Event type (widget_viewed, action_clicked, etc.)
            action_id: Optional action ID
            action_type: Optional action type
            priority: Optional priority level
        """
        try:
            engagement = WidgetEngagement(
                workspace_id=workspace_id,
                user_id=user_id,
                event_type=event_type,
                action_id=action_id,
                action_type=action_type,
                priority=priority
            )
            
            db.session.add(engagement)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error tracking engagement: {e}")
    
    @staticmethod
    def _get_dismissed_action_ids(workspace_id: int, user_id: int) -> Set[str]:
        """
        Get set of currently dismissed action IDs for a user.
        Only returns non-expired dismissals.
        
        Args:
            workspace_id: Workspace ID
            user_id: User ID
            
        Returns:
            Set of action IDs
        """
        now = datetime.utcnow()
        
        dismissed = DismissedAction.query.filter(
            DismissedAction.workspace_id == workspace_id,
            DismissedAction.user_id == user_id,
            DismissedAction.expires_at > now
        ).all()
        
        return {d.action_id for d in dismissed}
