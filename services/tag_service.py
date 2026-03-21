"""
Tag Service
Business logic for tag management on contacts
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from models import db
from models_crm import Tag, ContactTag, Contact

logger = logging.getLogger(__name__)


class TagService:
    """Service for managing tags and contact-tag associations"""

    @staticmethod
    def get_tags(workspace_id: int) -> List[Tag]:
        """Get all tags for a workspace"""
        return Tag.query.filter_by(workspace_id=workspace_id).order_by(Tag.name).all()

    @staticmethod
    def create_tag(workspace_id: int, name: str, color: str = '#6366f1') -> Tag:
        """Create a new tag. Raises ValueError if duplicate."""
        name = (name or '').strip()
        if not name:
            raise ValueError("Tag name is required")

        existing = Tag.query.filter_by(workspace_id=workspace_id, name=name).first()
        if existing:
            raise ValueError(f"Tag '{name}' already exists")

        tag = Tag(workspace_id=workspace_id, name=name, color=color or '#6366f1')
        db.session.add(tag)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
        logger.info(f"Created tag {tag.id}: {tag.name}")
        return tag

    @staticmethod
    def update_tag(workspace_id: int, tag_id: int, data: Dict[str, Any]) -> Tag:
        """Update a tag's name or color."""
        tag = Tag.query.filter_by(id=tag_id, workspace_id=workspace_id).first()
        if not tag:
            raise LookupError("Tag not found")

        if 'name' in data:
            new_name = (data['name'] or '').strip()
            if not new_name:
                raise ValueError("Tag name is required")
            if new_name != tag.name:
                dup = Tag.query.filter_by(workspace_id=workspace_id, name=new_name).first()
                if dup:
                    raise ValueError(f"Tag '{new_name}' already exists")
                tag.name = new_name

        if 'color' in data:
            tag.color = data['color'] or '#6366f1'

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
        return tag

    @staticmethod
    def delete_tag(workspace_id: int, tag_id: int) -> None:
        """Delete a tag and all its associations."""
        tag = Tag.query.filter_by(id=tag_id, workspace_id=workspace_id).first()
        if not tag:
            raise LookupError("Tag not found")

        ContactTag.query.filter_by(tag_id=tag_id).delete()
        db.session.delete(tag)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
        logger.info(f"Deleted tag {tag_id}")

    @staticmethod
    def add_tags_to_contact(workspace_id: int, contact_id: int, tag_ids: List[int]) -> List[Tag]:
        """Add multiple tags to a contact. Returns the contact's current tags."""
        contact = Contact.query.filter_by(
            id=contact_id, workspace_id=workspace_id, is_deleted=False
        ).first()
        if not contact:
            raise LookupError("Contact not found")

        tags = Tag.query.filter(Tag.id.in_(tag_ids), Tag.workspace_id == workspace_id).all()
        if len(tags) != len(tag_ids):
            raise ValueError("One or more tags not found")

        for tag in tags:
            existing = ContactTag.query.filter_by(contact_id=contact_id, tag_id=tag.id).first()
            if not existing:
                db.session.add(ContactTag(contact_id=contact_id, tag_id=tag.id))

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

        return TagService.get_contact_tags(contact_id)

    @staticmethod
    def remove_tag_from_contact(contact_id: int, tag_id: int) -> None:
        """Remove a tag from a contact."""
        ct = ContactTag.query.filter_by(contact_id=contact_id, tag_id=tag_id).first()
        if ct:
            db.session.delete(ct)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                raise e

    @staticmethod
    def set_contact_tags(workspace_id: int, contact_id: int, tag_ids: List[int]) -> List[Tag]:
        """Replace all tags on a contact with the given set."""
        contact = Contact.query.filter_by(
            id=contact_id, workspace_id=workspace_id, is_deleted=False
        ).first()
        if not contact:
            raise LookupError("Contact not found")

        # Remove existing
        ContactTag.query.filter_by(contact_id=contact_id).delete()

        # Add new
        if tag_ids:
            tags = Tag.query.filter(Tag.id.in_(tag_ids), Tag.workspace_id == workspace_id).all()
            for tag in tags:
                db.session.add(ContactTag(contact_id=contact_id, tag_id=tag.id))

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

        return TagService.get_contact_tags(contact_id)

    @staticmethod
    def get_contact_tags(contact_id: int) -> List[Tag]:
        """Get all tags for a contact."""
        return Tag.query.join(ContactTag).filter(ContactTag.contact_id == contact_id).all()

    @staticmethod
    def get_or_create_tag(workspace_id: int, name: str, color: str = '#6366f1') -> Tag:
        """Get existing tag by name or create new one."""
        name = (name or '').strip()
        if not name:
            raise ValueError("Tag name is required")

        tag = Tag.query.filter_by(workspace_id=workspace_id, name=name).first()
        if tag:
            return tag

        return TagService.create_tag(workspace_id, name, color)
