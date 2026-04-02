"""
Contact Merge Service
Business logic for merging duplicate contacts
"""
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from models import db
from models_crm import Contact, ContactMergeHistory, ContactTag, Activity

logger = logging.getLogger(__name__)


class ContactMergeService:
    """Service for detecting and merging duplicate contacts"""

    @staticmethod
    def find_duplicates(
        workspace_id: int,
        contact_id: Optional[int] = None,
        current_user=None,
    ) -> List[Dict[str, Any]]:
        """
        Find potential duplicate contacts in a workspace.
        Groups contacts by matching email or phone.
        
        If contact_id is provided, finds duplicates for that specific contact.
        """
        from sqlalchemy import or_, and_, func

        base_query = Contact.query.filter_by(workspace_id=workspace_id, is_deleted=False)
        if current_user is not None:
            from utils.permissions import get_accessible_entities_query

            base_query = get_accessible_entities_query(
                current_user,
                Contact,
                base_query=base_query,
            )
            base_query = base_query.filter(Contact.is_deleted == False)

        if contact_id:
            contact = base_query.filter_by(id=contact_id).first()
            if not contact:
                raise LookupError("Contact not found")

            conditions = []
            if contact.email:
                conditions.append(Contact.email == contact.email)
            if contact.phone:
                conditions.append(Contact.phone == contact.phone)
            if contact.whatsapp_phone:
                conditions.append(Contact.whatsapp_phone == contact.whatsapp_phone)

            if not conditions:
                return []

            duplicates = base_query.filter(
                and_(
                    Contact.id != contact_id,
                    or_(*conditions)
                )
            ).all()

            return [{
                'source': _contact_to_dict(contact),
                'duplicates': [_contact_to_dict(d) for d in duplicates]
            }] if duplicates else []

        # Find all duplicate groups by email
        duplicate_groups = []
        seen_ids = set()

        # Email duplicates
        email_dupes = db.session.query(
            Contact.email, func.count(Contact.id)
        ).filter(
            Contact.workspace_id == workspace_id,
            Contact.is_deleted == False,
            Contact.email.isnot(None),
            Contact.email != ''
        ).group_by(Contact.email).having(func.count(Contact.id) > 1).all()

        for email, count in email_dupes:
            contacts = base_query.filter_by(email=email).all()
            group_ids = {c.id for c in contacts}
            if not group_ids.issubset(seen_ids):
                duplicate_groups.append({
                    'match_field': 'email',
                    'match_value': email,
                    'contacts': [_contact_to_dict(c) for c in contacts]
                })
                seen_ids.update(group_ids)

        # Phone duplicates
        phone_dupes = db.session.query(
            Contact.phone, func.count(Contact.id)
        ).filter(
            Contact.workspace_id == workspace_id,
            Contact.is_deleted == False,
            Contact.phone.isnot(None),
            Contact.phone != ''
        ).group_by(Contact.phone).having(func.count(Contact.id) > 1).all()

        for phone, count in phone_dupes:
            contacts = base_query.filter_by(phone=phone).all()
            group_ids = {c.id for c in contacts}
            if not group_ids.issubset(seen_ids):
                duplicate_groups.append({
                    'match_field': 'phone',
                    'match_value': phone,
                    'contacts': [_contact_to_dict(c) for c in contacts]
                })
                seen_ids.update(group_ids)

        return duplicate_groups

    @staticmethod
    def merge_contacts(workspace_id: int, primary_id: int, secondary_id: int,
                       user_id: int, field_overrides: Optional[Dict[str, Any]] = None) -> Contact:
        """
        Merge secondary contact into primary contact.
        
        - Primary contact is kept, secondary is soft-deleted.
        - Empty fields on primary are filled from secondary.
        - Activities, notes, tags from secondary are transferred to primary.
        - field_overrides lets user pick which values to keep.
        - A MergeHistory record is created for audit.
        """
        primary = Contact.query.filter_by(
            id=primary_id, workspace_id=workspace_id, is_deleted=False
        ).first()
        if not primary:
            raise LookupError("Primary contact not found")

        secondary = Contact.query.filter_by(
            id=secondary_id, workspace_id=workspace_id, is_deleted=False
        ).first()
        if not secondary:
            raise LookupError("Secondary contact not found")

        if primary_id == secondary_id:
            raise ValueError("Cannot merge a contact with itself")

        # Snapshot secondary before merge
        snapshot = _contact_to_dict(secondary)

        # Apply field overrides or fill empty fields from secondary
        mergeable_fields = [
            'last_name', 'email', 'phone', 'whatsapp_phone', 'telegram_chat_id',
            'role', 'job_title', 'lead_source', 'company_id'
        ]

        overrides = field_overrides or {}
        for field in mergeable_fields:
            if field in overrides:
                setattr(primary, field, overrides[field])
            elif not getattr(primary, field) and getattr(secondary, field):
                setattr(primary, field, getattr(secondary, field))

        # Keep higher lead score
        if secondary.lead_score > primary.lead_score:
            primary.lead_score = secondary.lead_score

        # Keep earlier created_at
        if secondary.created_at and (not primary.created_at or secondary.created_at < primary.created_at):
            primary.created_at = secondary.created_at

        # Transfer activities
        Activity.query.filter_by(contact_id=secondary_id).update(
            {'contact_id': primary_id}, synchronize_session=False
        )

        # Transfer contact notes
        try:
            from models_contact_timeline import ContactNote, ContactActivityLog
            ContactNote.query.filter_by(contact_id=secondary_id).update(
                {'contact_id': primary_id}, synchronize_session=False
            )
            ContactActivityLog.query.filter_by(contact_id=secondary_id).update(
                {'contact_id': primary_id}, synchronize_session=False
            )
        except Exception:
            pass  # Tables may not exist yet

        # Transfer tags (avoid duplicates)
        secondary_tags = ContactTag.query.filter_by(contact_id=secondary_id).all()
        primary_tag_ids = {ct.tag_id for ct in ContactTag.query.filter_by(contact_id=primary_id).all()}
        for ct in secondary_tags:
            if ct.tag_id not in primary_tag_ids:
                db.session.add(ContactTag(contact_id=primary_id, tag_id=ct.tag_id))
        ContactTag.query.filter_by(contact_id=secondary_id).delete()

        # Transfer custom field values (keep primary's if both exist)
        from models_crm import CustomFieldValue, CustomField
        secondary_cf_values = CustomFieldValue.query.filter_by(entity_id=secondary_id).all()
        primary_cf_ids = {
            cfv.custom_field_id
            for cfv in CustomFieldValue.query.filter_by(entity_id=primary_id).all()
        }
        for cfv in secondary_cf_values:
            if cfv.custom_field_id not in primary_cf_ids:
                cfv.entity_id = primary_id
            else:
                db.session.delete(cfv)

        # Soft-delete secondary
        secondary.is_deleted = True
        secondary.deleted_at = datetime.utcnow()

        # Update primary timestamps
        primary.updated_at = datetime.utcnow()
        if secondary.last_activity_at:
            if not primary.last_activity_at or secondary.last_activity_at > primary.last_activity_at:
                primary.last_activity_at = secondary.last_activity_at

        # Create merge history record
        merge_record = ContactMergeHistory(
            workspace_id=workspace_id,
            primary_contact_id=primary_id,
            merged_contact_id=secondary_id,
            merged_data_json=json.dumps(snapshot, default=str),
            merged_by=user_id
        )
        db.session.add(merge_record)

        # Create activity log
        try:
            from models_contact_timeline import ContactActivityLog
            activity = ContactActivityLog(
                workspace_id=workspace_id,
                contact_id=primary_id,
                user_id=user_id,
                action_type='contact_merged',
                description=f'Kişi birleştirildi: {snapshot.get("full_name", "")} bu kişiyle birleştirildi',
                metadata_json=json.dumps({'merged_contact_id': secondary_id, 'merged_name': snapshot.get('full_name', '')})
            )
            db.session.add(activity)
        except Exception:
            pass

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

        logger.info(f"Merged contact {secondary_id} into {primary_id} in workspace {workspace_id}")
        return primary


def _contact_to_dict(contact: Contact) -> Dict[str, Any]:
    """Convert contact to dict for API response and snapshots."""
    return {
        'id': contact.id,
        'first_name': contact.first_name,
        'last_name': contact.last_name,
        'full_name': contact.full_name,
        'email': contact.email,
        'phone': contact.phone,
        'whatsapp_phone': contact.whatsapp_phone,
        'role': contact.role,
        'job_title': contact.job_title,
        'lead_score': contact.lead_score,
        'lead_source': contact.lead_source,
        'lifecycle_stage': contact.lifecycle_stage,
        'company_id': contact.company_id,
        'company_name': contact.company.name if contact.company else None,
        'is_starred': contact.is_starred,
        'last_activity_at': contact.last_activity_at.isoformat() if contact.last_activity_at else None,
        'created_at': contact.created_at.isoformat() if contact.created_at else None,
        'updated_at': contact.updated_at.isoformat() if contact.updated_at else None,
    }
