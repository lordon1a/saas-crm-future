"""
Assignment Service
Business logic for assigning CRM entities to team members
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy import and_
from models import db, User, Conversation
from models_crm import Contact, Company, Deal, Task, Activity

logger = logging.getLogger(__name__)


class AssignmentService:
    """Service for managing entity assignments to team members"""
    
    # Supported entity types for assignment
    SUPPORTED_ENTITY_TYPES = ['contact', 'company', 'deal', 'task', 'conversation']
    
    # Entity type to model mapping
    ENTITY_MODEL_MAP = {
        'contact': Contact,
        'company': Company,
        'deal': Deal,
        'task': Task,
        'conversation': Conversation
    }

    # Entity type to assignment field mapping
    ENTITY_ASSIGNMENT_FIELD_MAP = {
        'contact': 'assigned_to',
        'company': 'assigned_to',
        'deal': 'owner_id',
        'task': 'assignee_id',
        'conversation': 'assigned_to',
    }
    
    # ============================================================================
    # ASSIGNMENT OPERATIONS
    # ============================================================================
    
    @staticmethod
    def assign_entity(workspace_id: int, entity_type: str, entity_id: int, 
                     assignee_id: int, assigned_by_id: int) -> Dict[str, Any]:
        """
        Assign a CRM entity to a team member.
        
        Args:
            workspace_id: Workspace ID
            entity_type: Type of entity (contact, company, deal, task, conversation)
            entity_id: ID of the entity to assign
            assignee_id: User ID to assign the entity to
            assigned_by_id: User ID performing the assignment
        
        Returns:
            Dict with 'entity' and 'activity' keys
        
        Raises:
            ValueError: If validation fails
        """
        # Validate entity type
        if entity_type not in AssignmentService.SUPPORTED_ENTITY_TYPES:
            raise ValueError(f"Unsupported entity type: {entity_type}")
        
        # Get entity model
        model = AssignmentService.ENTITY_MODEL_MAP[entity_type]
        
        # Get entity
        entity = model.query.filter_by(
            id=entity_id,
            workspace_id=workspace_id
        ).first()
        
        if not entity:
            raise ValueError(f"{entity_type.capitalize()} not found")
        
        # Validate assignee belongs to workspace and is active
        assignee = User.query.filter_by(
            id=assignee_id,
            workspace_id=workspace_id,
            is_active=True
        ).first()
        
        if not assignee:
            raise ValueError("Assignee not found or inactive in workspace")
        
        assignment_field = AssignmentService.ENTITY_ASSIGNMENT_FIELD_MAP[entity_type]

        # Get old assignee for activity log
        old_assignee_id = getattr(entity, assignment_field, None)
        old_assignee_name = None
        if old_assignee_id:
            old_assignee = User.query.get(old_assignee_id)
            if old_assignee:
                old_assignee_name = old_assignee.name
        
        # Update entity assignment
        setattr(entity, assignment_field, assignee_id)
        
        # Create activity record
        activity = AssignmentService._create_assignment_activity(
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            entity=entity,
            assignee_name=assignee.name,
            old_assignee_name=old_assignee_name,
            assigned_by_id=assigned_by_id
        )
        
        try:
            db.session.commit()
            logger.info(f"Assigned {entity_type} {entity_id} to user {assignee_id} by user {assigned_by_id}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to assign entity: {str(e)}")
            raise e
        
        return {
            'entity': entity,
            'activity': activity
        }
    
    @staticmethod
    def unassign_entity(workspace_id: int, entity_type: str, entity_id: int, 
                       unassigned_by_id: int) -> Dict[str, Any]:
        """
        Remove assignment from a CRM entity.
        
        Args:
            workspace_id: Workspace ID
            entity_type: Type of entity (contact, company, deal, task, conversation)
            entity_id: ID of the entity to unassign
            unassigned_by_id: User ID performing the unassignment
        
        Returns:
            Dict with 'entity' and 'activity' keys
        
        Raises:
            ValueError: If validation fails
        """
        # Validate entity type
        if entity_type not in AssignmentService.SUPPORTED_ENTITY_TYPES:
            raise ValueError(f"Unsupported entity type: {entity_type}")
        
        # Get entity model
        model = AssignmentService.ENTITY_MODEL_MAP[entity_type]
        
        # Get entity
        entity = model.query.filter_by(
            id=entity_id,
            workspace_id=workspace_id
        ).first()
        
        if not entity:
            raise ValueError(f"{entity_type.capitalize()} not found")
        
        assignment_field = AssignmentService.ENTITY_ASSIGNMENT_FIELD_MAP[entity_type]

        # Get old assignee for activity log
        old_assignee_id = getattr(entity, assignment_field, None)
        old_assignee_name = None
        if old_assignee_id:
            old_assignee = User.query.get(old_assignee_id)
            if old_assignee:
                old_assignee_name = old_assignee.name
        
        # Remove assignment
        # Deal owner_id is non-nullable; skip unassign for deals.
        if entity_type == 'deal':
            raise ValueError("Deal entities cannot be unassigned. Please choose an owner.")
        setattr(entity, assignment_field, None)
        
        # Create activity record
        activity = AssignmentService._create_assignment_activity(
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            entity=entity,
            assignee_name=None,
            old_assignee_name=old_assignee_name,
            assigned_by_id=unassigned_by_id
        )
        
        try:
            db.session.commit()
            logger.info(f"Unassigned {entity_type} {entity_id} by user {unassigned_by_id}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to unassign entity: {str(e)}")
            raise e
        
        return {
            'entity': entity,
            'activity': activity
        }
    
    @staticmethod
    def get_assignable_members(workspace_id: int) -> List[Dict[str, Any]]:
        """
        Get list of active team members who can be assigned to entities.
        
        Args:
            workspace_id: Workspace ID
        
        Returns:
            List of dicts with user info (id, name, email, role)
        """
        users = User.query.filter_by(
            workspace_id=workspace_id,
            is_active=True
        ).order_by(User.name).all()
        
        return [
            {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'role': user.role
            }
            for user in users
        ]
    
    @staticmethod
    def get_entity_assignments(workspace_id: int, entity_type: str, 
                              assignee_id: Optional[int] = None) -> List[Any]:
        """
        Get entities assigned to a specific user or all assignments.
        
        Args:
            workspace_id: Workspace ID
            entity_type: Type of entity (contact, company, deal, task, conversation)
            assignee_id: Optional user ID to filter by assignee
        
        Returns:
            List of entity instances
        
        Raises:
            ValueError: If entity type is invalid
        """
        # Validate entity type
        if entity_type not in AssignmentService.SUPPORTED_ENTITY_TYPES:
            raise ValueError(f"Unsupported entity type: {entity_type}")
        
        # Get entity model
        model = AssignmentService.ENTITY_MODEL_MAP[entity_type]
        
        # Build query
        query = model.query.filter_by(workspace_id=workspace_id)
        
        if assignee_id is not None:
            assignment_field = AssignmentService.ENTITY_ASSIGNMENT_FIELD_MAP[entity_type]
            query = query.filter(getattr(model, assignment_field) == assignee_id)
        
        # Apply entity-specific filters (exclude deleted items)
        if hasattr(model, 'is_deleted'):
            query = query.filter_by(is_deleted=False)
        
        return query.all()
    
    @staticmethod
    def bulk_reassign(workspace_id: int, entity_type: str, entity_ids: List[int], 
                     new_assignee_id: int, assigned_by_id: int) -> Dict[str, Any]:
        """
        Reassign multiple entities to a new team member.
        
        Args:
            workspace_id: Workspace ID
            entity_type: Type of entity (contact, company, deal, task, conversation)
            entity_ids: List of entity IDs to reassign
            new_assignee_id: User ID to assign entities to
            assigned_by_id: User ID performing the reassignment
        
        Returns:
            Dict with 'success_count', 'failed_count', and 'errors' keys
        
        Raises:
            ValueError: If validation fails
        """
        # Validate entity type
        if entity_type not in AssignmentService.SUPPORTED_ENTITY_TYPES:
            raise ValueError(f"Unsupported entity type: {entity_type}")
        
        # Validate assignee
        assignee = User.query.filter_by(
            id=new_assignee_id,
            workspace_id=workspace_id,
            is_active=True
        ).first()
        
        if not assignee:
            raise ValueError("Assignee not found or inactive in workspace")
        
        success_count = 0
        failed_count = 0
        errors = []
        
        for entity_id in entity_ids:
            try:
                AssignmentService.assign_entity(
                    workspace_id=workspace_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    assignee_id=new_assignee_id,
                    assigned_by_id=assigned_by_id
                )
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append({
                    'entity_id': entity_id,
                    'error': str(e)
                })
                logger.error(f"Failed to reassign {entity_type} {entity_id}: {str(e)}")
        
        return {
            'success_count': success_count,
            'failed_count': failed_count,
            'errors': errors
        }
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    @staticmethod
    def _create_assignment_activity(workspace_id: int, entity_type: str, 
                                   entity_id: int, entity: Any, 
                                   assignee_name: Optional[str], 
                                   old_assignee_name: Optional[str],
                                   assigned_by_id: int) -> Activity:
        """
        Create an activity record for assignment change.
        
        Args:
            workspace_id: Workspace ID
            entity_type: Type of entity
            entity_id: Entity ID
            entity: Entity instance
            assignee_name: New assignee name (None for unassignment)
            old_assignee_name: Previous assignee name (None if was unassigned)
            assigned_by_id: User ID who made the change
        
        Returns:
            Activity: Created activity instance
        """
        # Build activity subject and body
        if assignee_name and old_assignee_name:
            subject = f"Reassigned from {old_assignee_name} to {assignee_name}"
            body = f"Assignment changed from {old_assignee_name} to {assignee_name}"
        elif assignee_name:
            subject = f"Assigned to {assignee_name}"
            body = f"Assigned to {assignee_name}"
        else:
            subject = f"Unassigned from {old_assignee_name}"
            body = f"Removed assignment from {old_assignee_name}"
        
        # Create activity with appropriate entity links
        activity_data = {
            'workspace_id': workspace_id,
            'activity_type': 'system',
            'subject': subject,
            'body': body,
            'user_id': assigned_by_id,
            'created_at': datetime.utcnow()
        }
        
        # Link to appropriate entity
        if entity_type == 'contact':
            activity_data['contact_id'] = entity_id
            if hasattr(entity, 'company_id') and entity.company_id:
                activity_data['company_id'] = entity.company_id
        elif entity_type == 'company':
            activity_data['company_id'] = entity_id
        elif entity_type == 'deal':
            activity_data['deal_id'] = entity_id
            if hasattr(entity, 'company_id') and entity.company_id:
                activity_data['company_id'] = entity.company_id
        elif entity_type == 'task':
            # Tasks can be linked to deals and companies
            if hasattr(entity, 'deal_id') and entity.deal_id:
                activity_data['deal_id'] = entity.deal_id
            if hasattr(entity, 'company_id') and entity.company_id:
                activity_data['company_id'] = entity.company_id
        elif entity_type == 'conversation':
            # Conversations are linked via customer, not directly in activity
            # We'll just create a system activity without entity links
            pass
        
        activity = Activity(**activity_data)
        db.session.add(activity)
        
        return activity
    
    @staticmethod
    def get_user_workload(workspace_id: int, user_id: int) -> Dict[str, int]:
        """
        Get count of entities assigned to a user.
        
        Args:
            workspace_id: Workspace ID
            user_id: User ID
        
        Returns:
            Dict with counts for each entity type
        """
        workload = {}
        
        for entity_type in AssignmentService.SUPPORTED_ENTITY_TYPES:
            model = AssignmentService.ENTITY_MODEL_MAP[entity_type]
            assignment_field = AssignmentService.ENTITY_ASSIGNMENT_FIELD_MAP[entity_type]
            
            query = model.query.filter(
                model.workspace_id == workspace_id,
                getattr(model, assignment_field) == user_id
            )
            
            # Exclude deleted items
            if hasattr(model, 'is_deleted'):
                query = query.filter_by(is_deleted=False)
            
            # For deals, only count open deals
            if entity_type == 'deal':
                query = query.filter_by(status='open')
            
            # For tasks, only count incomplete tasks
            if entity_type == 'task':
                query = query.filter(Task.status.notin_(['completed', 'cancelled']))
            
            # For conversations, only count open conversations
            if entity_type == 'conversation':
                query = query.filter_by(status='open')
            
            workload[entity_type] = query.count()
        
        return workload
