"""
SegmentService - Dynamic Contact Segment Management

Handles:
- Creating and managing contact segments
- Syncing dynamic segments based on filter criteria
- Manual membership management
- Triggering workflows on segment join/leave
"""
from datetime import datetime
import logging
from sqlalchemy import text


logger = logging.getLogger(__name__)


class SegmentService:
    """Service for managing contact segments and memberships."""

    @staticmethod
    def create_segment(workspace_id, user_id, name, description=None, filter_json=None, is_dynamic=True):
        """
        Create a new contact segment.
        
        Args:
            workspace_id: Workspace ID
            user_id: User creating the segment
            name: Segment name
            description: Optional description
            filter_json: JSON string of filter criteria (for dynamic segments)
            is_dynamic: True for dynamic (auto-managed), False for manual
        
        Returns:
            ContactSegment model instance
        """
        from models_crm import ContactSegment
        from app import db
        
        segment = ContactSegment(
            workspace_id=workspace_id,
            created_by=user_id,
            name=name,
            description=description,
            is_dynamic=is_dynamic,
            filter_json=filter_json,
            member_count=0
        )
        try:
            db.session.add(segment)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        
        # If dynamic, run initial sync
        if is_dynamic and filter_json:
            SegmentService.sync_segment(segment.id)
        
        return segment

    @staticmethod
    def get_segment(segment_id, workspace_id=None):
        """
        Get a segment by ID.
        
        Args:
            segment_id: Segment ID
            workspace_id: Optional workspace ID for validation
        
        Returns:
            ContactSegment or None
        """
        from models_crm import ContactSegment
        
        query = ContactSegment.query.filter_by(id=segment_id)
        if workspace_id:
            query = query.filter_by(workspace_id=workspace_id)
        return query.first()

    @staticmethod
    def list_segments(workspace_id, include_counts=True):
        """
        List all segments in a workspace.
        
        Args:
            workspace_id: Workspace ID
            include_counts: Whether to include member counts
        
        Returns:
            List of ContactSegment dicts
        """
        from models_crm import ContactSegment
        
        segments = ContactSegment.query.filter_by(
            workspace_id=workspace_id
        ).order_by(ContactSegment.name).all()
        
        return [s.to_dict() for s in segments]

    @staticmethod
    def update_segment(segment_id, workspace_id, **kwargs):
        """
        Update a segment.
        
        Args:
            segment_id: Segment ID
            workspace_id: Workspace ID for validation
            **kwargs: Fields to update (name, description, filter_json, is_dynamic)
        
        Returns:
            Updated ContactSegment or None
        """
        from models_crm import ContactSegment
        from app import db
        
        segment = SegmentService.get_segment(segment_id, workspace_id)
        if not segment:
            return None
        
        allowed_fields = ['name', 'description', 'filter_json', 'is_dynamic']
        for field in allowed_fields:
            if field in kwargs:
                setattr(segment, field, kwargs[field])
        
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        
        # Re-sync if filter changed on dynamic segment
        if segment.is_dynamic and 'filter_json' in kwargs:
            SegmentService.sync_segment(segment_id)
        
        return segment

    @staticmethod
    def delete_segment(segment_id, workspace_id):
        """
        Delete a segment and its memberships.
        
        Args:
            segment_id: Segment ID
            workspace_id: Workspace ID for validation
        
        Returns:
            True if deleted, False if not found
        """
        from models_crm import ContactSegment
        from app import db
        
        segment = SegmentService.get_segment(segment_id, workspace_id)
        if not segment:
            return False
        
        try:
            db.session.delete(segment)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        return True

    @staticmethod
    def sync_segment(segment_id):
        """
        Sync a dynamic segment by applying the filter and updating memberships.
        
        - Finds contacts matching the filter
        - Adds new members
        - Marks departed members as not current
        - Updates member count
        
        Args:
            segment_id: Segment ID to sync
        """
        from models_crm import ContactSegment, SegmentMembership, Contact
        from app import db
        from services.filter_service import FilterService
        from services.workflow_service import WorkflowService
        
        segment = ContactSegment.query.get(segment_id)
        if not segment or not segment.is_dynamic:
            return
        
        # Apply filter to get matching contacts
        try:
            filter_data = segment.filter_json
            if filter_data:
                filter_data = json.loads(filter_data)
            
            if filter_data:
                # Use FilterService with correct signature
                # For segment sync, we get all results (page=1, per_page=999999)
                matching_contacts, _ = FilterService.apply_filters(
                    entity_type='contact',
                    workspace_id=segment.workspace_id,
                    user_id=segment.created_by or 0,
                    filters=filter_data,
                    page=1,
                    per_page=999999
                )
                matching_ids = {c.id for c in matching_contacts}
            else:
                matching_ids = set()
        except Exception as e:
            print(f"Error applying filter for segment {segment_id}: {e}")
            matching_ids = set()
        
        # Get current memberships
        current_members = SegmentMembership.query.filter_by(
            segment_id=segment_id,
            is_current=True
        ).all()
        current_member_ids = {m.contact_id for m in current_members}
        
        # Calculate delta
        new_members = matching_ids - current_member_ids
        departed_members = current_member_ids - matching_ids
        
        # Add new members
        for contact_id in new_members:
            membership = SegmentMembership(
                segment_id=segment_id,
                contact_id=contact_id,
                added_at=datetime.utcnow(),
                is_current=True
            )
            db.session.add(membership)
            
            # Trigger workflow: segment_joined
            try:
                WorkflowService.trigger_event(
                    workspace_id=segment.workspace_id,
                    trigger_type='segment_joined',
                    entity_type='contact',
                    entity_id=contact_id,
                    context={'segment_id': segment_id, 'segment_name': segment.name}
                )
            except Exception as e:
                logger.warning("Error triggering segment_joined for contact %s: %s", contact_id, e)
        
        # Mark departed members
        for membership in current_members:
            if membership.contact_id in departed_members:
                membership.removed_at = datetime.utcnow()
                membership.is_current = False
                
                # Trigger workflow: segment_left
                try:
                    WorkflowService.trigger_event(
                        workspace_id=segment.workspace_id,
                        trigger_type='segment_left',
                        entity_type='contact',
                        entity_id=membership.contact_id,
                        context={'segment_id': segment_id, 'segment_name': segment.name}
                    )
                except Exception as e:
                    logger.warning("Error triggering segment_left for contact %s: %s", membership.contact_id, e)
        
        # Update segment stats
        segment.member_count = len(matching_ids)
        segment.last_synced_at = datetime.utcnow()
        
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def sync_all_dynamic_segments(workspace_id):
        """
        Sync all dynamic segments in a workspace.
        
        Args:
            workspace_id: Workspace ID
        """
        from models_crm import ContactSegment
        
        segments = ContactSegment.query.filter_by(
            workspace_id=workspace_id,
            is_dynamic=True
        ).all()
        
        for segment in segments:
            try:
                SegmentService.sync_segment(segment.id)
            except Exception as e:
                logger.warning("Error syncing segment %s: %s", segment.id, e)

    @staticmethod
    def sync_all_dynamic_segments_globally():
        """
        Sync all dynamic segments across all workspaces.
        """
        from models_crm import ContactSegment

        workspace_ids = ContactSegment.query.filter_by(is_dynamic=True).with_entities(
            ContactSegment.workspace_id
        ).distinct().all()

        for (workspace_id,) in workspace_ids:
            try:
                SegmentService.sync_all_dynamic_segments(workspace_id)
            except Exception as e:
                logger.warning("Error syncing dynamic segments for workspace %s: %s", workspace_id, e)

    @staticmethod
    def add_contact_manually(segment_id, contact_id, workspace_id):
        """
        Manually add a contact to a segment.
        Only works for non-dynamic (manual) segments.
        
        Args:
            segment_id: Segment ID
            contact_id: Contact ID
            workspace_id: Workspace ID for validation
        
        Returns:
            SegmentMembership or None
        """
        from models_crm import ContactSegment, SegmentMembership
        from app import db
        from services.workflow_service import WorkflowService
        
        segment = SegmentService.get_segment(segment_id, workspace_id)
        if not segment:
            return None
        
        if segment.is_dynamic:
            raise ValueError("Cannot manually add contacts to dynamic segments")
        
        # Check if already a current member
        existing = SegmentMembership.query.filter_by(
            segment_id=segment_id,
            contact_id=contact_id,
            is_current=True
        ).first()
        
        if existing:
            return existing
        
        membership = SegmentMembership(
            segment_id=segment_id,
            contact_id=contact_id,
            added_at=datetime.utcnow(),
            is_current=True
        )
        db.session.add(membership)
        
        # Update segment count
        segment.member_count = SegmentMembership.query.filter_by(
            segment_id=segment_id,
            is_current=True
        ).count()
        
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        
        # Trigger workflow
        try:
            WorkflowService.trigger_event(
                workspace_id=segment.workspace_id,
                trigger_type='segment_joined',
                entity_type='contact',
                entity_id=contact_id,
                context={'segment_id': segment_id, 'segment_name': segment.name}
            )
        except Exception as e:
            logger.warning("Error triggering segment_joined: %s", e)
        
        return membership

    @staticmethod
    def remove_contact_manually(segment_id, contact_id, workspace_id):
        """
        Manually remove a contact from a segment.
        Only works for non-dynamic (manual) segments.
        
        Args:
            segment_id: Segment ID
            contact_id: Contact ID
            workspace_id: Workspace ID for validation
        
        Returns:
            True if removed, False if not found
        """
        from models_crm import ContactSegment, SegmentMembership
        from app import db
        from services.workflow_service import WorkflowService
        
        segment = SegmentService.get_segment(segment_id, workspace_id)
        if not segment:
            return False
        
        membership = SegmentMembership.query.filter_by(
            segment_id=segment_id,
            contact_id=contact_id,
            is_current=True
        ).first()
        
        if not membership:
            return False
        
        membership.removed_at = datetime.utcnow()
        membership.is_current = False
        
        # Update segment count
        segment.member_count = SegmentMembership.query.filter_by(
            segment_id=segment_id,
            is_current=True
        ).count()
        
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        
        # Trigger workflow
        try:
            WorkflowService.trigger_event(
                workspace_id=segment.workspace_id,
                trigger_type='segment_left',
                entity_type='contact',
                entity_id=contact_id,
                context={'segment_id': segment_id, 'segment_name': segment.name}
            )
        except Exception as e:
            logger.warning("Error triggering segment_left: %s", e)
        
        return True

    @staticmethod
    def get_segment_members(segment_id, workspace_id, page=1, per_page=20, include_removed=False):
        """
        Get members of a segment with pagination.
        
        Args:
            segment_id: Segment ID
            workspace_id: Workspace ID for validation
            page: Page number
            per_page: Items per page
            include_removed: Whether to include removed members
        
        Returns:
            Dict with items and pagination info
        """
        from models_crm import ContactSegment, SegmentMembership, Contact
        from app import db
        
        segment = SegmentService.get_segment(segment_id, workspace_id)
        if not segment:
            return {'items': [], 'total': 0, 'page': page, 'per_page': per_page}
        
        query = SegmentMembership.query.filter_by(segment_id=segment_id)
        
        if not include_removed:
            query = query.filter_by(is_current=True)
        
        total = query.count()
        memberships = query.order_by(SegmentMembership.added_at.desc())\
            .offset((page - 1) * per_page)\
            .limit(per_page)\
            .all()
        
        # Get contact details for each membership
        items = []
        for m in memberships:
            contact = Contact.query.get(m.contact_id)
            if contact:
                items.append({
                    'membership': m.to_dict(),
                    'contact': {
                        'id': contact.id,
                        'name': contact.name,
                        'email': contact.email,
                        'phone': contact.phone
                    }
                })
        
        return {
            'items': items,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page
        }

    @staticmethod
    def get_contact_segments(contact_id, workspace_id):
        """
        Get all segments a contact is currently a member of.
        
        Args:
            contact_id: Contact ID
            workspace_id: Workspace ID for validation
        
        Returns:
            List of segment dicts
        """
        from models_crm import ContactSegment, SegmentMembership
        
        memberships = SegmentMembership.query.filter_by(
            contact_id=contact_id,
            is_current=True
        ).all()
        
        segment_ids = [m.segment_id for m in memberships]
        
        if not segment_ids:
            return []
        
        segments = ContactSegment.query.filter(
            ContactSegment.id.in_(segment_ids),
            ContactSegment.workspace_id == workspace_id
        ).all()
        
        return [s.to_dict() for s in segments]


# Import json at module level for filter parsing
import json
