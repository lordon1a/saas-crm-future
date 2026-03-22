"""
Deal Contact Service
Business logic for managing deal stakeholders (buying committee).
"""
import logging
from datetime import datetime

from models import db
from models_crm import Contact, Deal, DealContact

logger = logging.getLogger(__name__)


class DealContactService:
    """Service layer for deal-contact stakeholder operations."""

    @staticmethod
    def list_stakeholders(workspace_id, deal_id):
        """Return all stakeholders for a deal ordered by primary first."""
        deal = Deal.query.filter_by(
            id=deal_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        if not deal:
            raise ValueError("Deal not found")

        links = DealContact.query.filter_by(
            workspace_id=workspace_id,
            deal_id=deal_id,
        ).order_by(DealContact.is_primary.desc(), DealContact.created_at.asc()).all()

        results = []
        for link in links:
            if not link.contact:
                continue
            results.append({
                'deal_id': deal_id,
                'contact_id': link.contact_id,
                'is_primary': bool(link.is_primary),
                'role': link.role,
                'created_at': link.created_at.isoformat() if link.created_at else None,
                'updated_at': link.updated_at.isoformat() if link.updated_at else None,
                'contact': {
                    'id': link.contact.id,
                    'full_name': link.contact.full_name,
                    'email': link.contact.email,
                    'phone': link.contact.phone,
                    'job_title': link.contact.job_title,
                    'company_id': link.contact.company_id,
                }
            })
        return results

    @staticmethod
    def add_stakeholder(workspace_id, deal_id, contact_id, user_id, role=None, is_primary=None):
        """Add or update a stakeholder link for a deal."""
        deal = Deal.query.filter_by(
            id=deal_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        if not deal:
            raise ValueError("Deal not found")

        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        if not contact:
            raise ValueError("Contact not found")
        if contact.company_id and contact.company_id != deal.company_id:
            raise ValueError(
                f"Contact {contact_id} belongs to company {contact.company_id}, not deal company {deal.company_id}"
            )

        link = DealContact.query.filter_by(
            workspace_id=workspace_id,
            deal_id=deal_id,
            contact_id=contact_id,
        ).first()

        try:
            if not link:
                link = DealContact(
                    workspace_id=workspace_id,
                    deal_id=deal_id,
                    contact_id=contact_id,
                    role=role,
                    is_primary=bool(is_primary) if is_primary is not None else False,
                    added_by=user_id,
                )
                db.session.add(link)
            else:
                if role is not None:
                    link.role = role
                if is_primary is not None:
                    link.is_primary = bool(is_primary)
                link.updated_at = datetime.utcnow()

            if is_primary is True:
                DealContact.query.filter(
                    DealContact.workspace_id == workspace_id,
                    DealContact.deal_id == deal_id,
                    DealContact.contact_id != contact_id,
                    DealContact.is_primary.is_(True),
                ).update({DealContact.is_primary: False}, synchronize_session=False)
                deal.contact_id = contact_id
                deal.updated_at = datetime.utcnow()
            elif deal.contact_id is None:
                # Keep legacy deal.contact_id populated when the first stakeholder is added.
                deal.contact_id = contact_id
                deal.updated_at = datetime.utcnow()

            db.session.commit()
            return link
        except Exception:
            db.session.rollback()
            logger.exception("Failed to add/update stakeholder for deal %s", deal_id)
            raise

    @staticmethod
    def update_stakeholder(workspace_id, deal_id, contact_id, role=None, is_primary=None):
        """Update stakeholder metadata (role/primary)."""
        link = DealContact.query.filter_by(
            workspace_id=workspace_id,
            deal_id=deal_id,
            contact_id=contact_id,
        ).first()
        if not link:
            raise ValueError("Stakeholder not found")

        deal = Deal.query.filter_by(
            id=deal_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        if not deal:
            raise ValueError("Deal not found")

        try:
            if role is not None:
                link.role = role

            if is_primary is not None:
                is_primary = bool(is_primary)
                link.is_primary = is_primary
                if is_primary:
                    DealContact.query.filter(
                        DealContact.workspace_id == workspace_id,
                        DealContact.deal_id == deal_id,
                        DealContact.contact_id != contact_id,
                        DealContact.is_primary.is_(True),
                    ).update({DealContact.is_primary: False}, synchronize_session=False)
                    deal.contact_id = contact_id
                elif deal.contact_id == contact_id:
                    replacement = DealContact.query.filter(
                        DealContact.workspace_id == workspace_id,
                        DealContact.deal_id == deal_id,
                        DealContact.contact_id != contact_id,
                    ).order_by(DealContact.is_primary.desc(), DealContact.created_at.asc()).first()
                    deal.contact_id = replacement.contact_id if replacement else None
                deal.updated_at = datetime.utcnow()

            link.updated_at = datetime.utcnow()
            db.session.commit()
            return link
        except Exception:
            db.session.rollback()
            logger.exception("Failed to update stakeholder for deal %s", deal_id)
            raise

    @staticmethod
    def remove_stakeholder(workspace_id, deal_id, contact_id):
        """Remove a stakeholder link and keep deal.primary contact consistent."""
        link = DealContact.query.filter_by(
            workspace_id=workspace_id,
            deal_id=deal_id,
            contact_id=contact_id,
        ).first()
        if not link:
            raise ValueError("Stakeholder not found")

        deal = Deal.query.filter_by(
            id=deal_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        if not deal:
            raise ValueError("Deal not found")

        try:
            db.session.delete(link)
            db.session.flush()

            if deal.contact_id == contact_id:
                replacement = DealContact.query.filter_by(
                    workspace_id=workspace_id,
                    deal_id=deal_id,
                ).order_by(DealContact.is_primary.desc(), DealContact.created_at.asc()).first()
                deal.contact_id = replacement.contact_id if replacement else None
                deal.updated_at = datetime.utcnow()

            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception("Failed to remove stakeholder for deal %s", deal_id)
            raise
