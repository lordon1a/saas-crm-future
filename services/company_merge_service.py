"""
Company Merge Service
Business logic for duplicate detection and company merge flows.
"""
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from models import db
from models_crm import (
    Activity,
    CalendarSync,
    Company,
    CompanyMergeHistory,
    Contact,
    CustomField,
    CustomFieldValue,
    CustomerUser,
    Deal,
    Document,
    EmailSync,
    Milestone,
    OutboundEmail,
    QuickBooksInvoice,
    Task,
)

logger = logging.getLogger(__name__)


class CompanyMergeService:
    """Service for detecting and merging duplicate companies."""

    @staticmethod
    def find_duplicates(
        workspace_id: int,
        company_id: Optional[int] = None,
        current_user=None,
    ) -> List[Dict[str, Any]]:
        """Find potential duplicate companies by normalized name, website, or phone."""
        base_query = Company.query.filter_by(workspace_id=workspace_id, is_deleted=False)
        if current_user is not None:
            from utils.permissions import get_accessible_entities_query

            base_query = get_accessible_entities_query(
                current_user,
                Company,
                base_query=base_query,
            )
            base_query = base_query.filter(Company.is_deleted == False)
        companies = base_query.all()

        if company_id is not None:
            source = base_query.filter_by(id=company_id).first()
            if not source:
                raise LookupError("Company not found")

            source_name = _normalize_name(source.name)
            source_site = _normalize_website(source.website)
            source_phone = _normalize_phone(source.phone)

            matches = []
            for candidate in companies:
                if candidate.id == source.id:
                    continue
                if source_name and _normalize_name(candidate.name) == source_name:
                    matches.append(candidate)
                    continue
                if source_site and _normalize_website(candidate.website) == source_site:
                    matches.append(candidate)
                    continue
                if source_phone and _normalize_phone(candidate.phone) == source_phone:
                    matches.append(candidate)

            return [{
                'source': _company_to_dict(source),
                'duplicates': [_company_to_dict(item) for item in matches],
            }] if matches else []

        grouped: List[Dict[str, Any]] = []

        for field_name, normalizer in (
            ('name', _normalize_name),
            ('website', _normalize_website),
            ('phone', _normalize_phone),
        ):
            buckets: Dict[str, List[Company]] = {}
            for company in companies:
                raw = getattr(company, field_name)
                key = normalizer(raw)
                if not key:
                    continue
                buckets.setdefault(key, []).append(company)

            for key, items in buckets.items():
                if len(items) < 2:
                    continue
                grouped.append({
                    'match_field': field_name,
                    'match_value': key,
                    'companies': [_company_to_dict(item) for item in items],
                })

        return grouped

    @staticmethod
    def merge_companies(
        workspace_id: int,
        primary_id: int,
        secondary_id: int,
        user_id: int,
        field_overrides: Optional[Dict[str, Any]] = None
    ) -> Company:
        """Merge secondary company into primary company."""
        primary = Company.query.filter_by(
            id=primary_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        if not primary:
            raise LookupError("Primary company not found")

        secondary = Company.query.filter_by(
            id=secondary_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        if not secondary:
            raise LookupError("Secondary company not found")

        if primary_id == secondary_id:
            raise ValueError("Cannot merge a company with itself")

        snapshot = _company_to_dict(secondary)
        overrides = field_overrides or {}

        mergeable_fields = [
            'industry',
            'size',
            'website',
            'phone',
            'address',
            'assigned_to',
            'parent_company_id',
        ]
        for field in mergeable_fields:
            if field in overrides:
                setattr(primary, field, overrides[field])
            elif not getattr(primary, field) and getattr(secondary, field):
                setattr(primary, field, getattr(secondary, field))

        if primary.parent_company_id == secondary.id:
            primary.parent_company_id = None

        if secondary.display_order < primary.display_order:
            primary.display_order = secondary.display_order

        if secondary.created_at and (not primary.created_at or secondary.created_at < primary.created_at):
            primary.created_at = secondary.created_at

        primary.updated_at = datetime.utcnow()

        # Re-link all known company references to primary
        Contact.query.filter_by(workspace_id=workspace_id, company_id=secondary_id).update(
            {'company_id': primary_id}, synchronize_session=False
        )
        Deal.query.filter_by(workspace_id=workspace_id, company_id=secondary_id).update(
            {'company_id': primary_id}, synchronize_session=False
        )
        Task.query.filter_by(workspace_id=workspace_id, company_id=secondary_id).update(
            {'company_id': primary_id}, synchronize_session=False
        )
        Milestone.query.filter_by(workspace_id=workspace_id, company_id=secondary_id).update(
            {'company_id': primary_id}, synchronize_session=False
        )
        Activity.query.filter_by(workspace_id=workspace_id, company_id=secondary_id).update(
            {'company_id': primary_id}, synchronize_session=False
        )
        Document.query.filter_by(workspace_id=workspace_id, company_id=secondary_id).update(
            {'company_id': primary_id}, synchronize_session=False
        )
        QuickBooksInvoice.query.filter_by(workspace_id=workspace_id, company_id=secondary_id).update(
            {'company_id': primary_id}, synchronize_session=False
        )
        EmailSync.query.filter_by(workspace_id=workspace_id, company_id=secondary_id).update(
            {'company_id': primary_id}, synchronize_session=False
        )
        OutboundEmail.query.filter_by(workspace_id=workspace_id, company_id=secondary_id).update(
            {'company_id': primary_id}, synchronize_session=False
        )
        CalendarSync.query.filter_by(workspace_id=workspace_id, company_id=secondary_id).update(
            {'company_id': primary_id}, synchronize_session=False
        )
        CustomerUser.query.filter_by(workspace_id=workspace_id, company_id=secondary_id).update(
            {'company_id': primary_id}, synchronize_session=False
        )
        Company.query.filter_by(workspace_id=workspace_id, parent_company_id=secondary_id).update(
            {'parent_company_id': primary_id}, synchronize_session=False
        )

        # Merge company custom fields without violating unique(custom_field_id, entity_id)
        company_field_ids = {
            item.id
            for item in CustomField.query.filter_by(workspace_id=workspace_id, entity_type='company').all()
        }
        if company_field_ids:
            primary_cfv_ids = {
                row.custom_field_id
                for row in CustomFieldValue.query.filter(
                    CustomFieldValue.entity_id == primary_id,
                    CustomFieldValue.custom_field_id.in_(company_field_ids)
                ).all()
            }
            secondary_cfvs = CustomFieldValue.query.filter(
                CustomFieldValue.entity_id == secondary_id,
                CustomFieldValue.custom_field_id.in_(company_field_ids)
            ).all()
            for row in secondary_cfvs:
                if row.custom_field_id in primary_cfv_ids:
                    db.session.delete(row)
                else:
                    row.entity_id = primary_id

        secondary.is_deleted = True
        secondary.deleted_at = datetime.utcnow()
        secondary.updated_at = datetime.utcnow()

        db.session.add(CompanyMergeHistory(
            workspace_id=workspace_id,
            primary_company_id=primary_id,
            merged_company_id=secondary_id,
            merged_data_json=json.dumps(snapshot, default=str),
            merged_by=user_id,
        ))

        db.session.add(Activity(
            workspace_id=workspace_id,
            activity_type='system',
            company_id=primary_id,
            user_id=user_id,
            subject='Company merged',
            body=f'Company merged: {snapshot.get("name", "")} -> {primary.name}',
            extra_data=json.dumps({
                'merged_company_id': secondary_id,
                'merged_company_name': snapshot.get('name'),
            }),
        ))

        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.error("Failed to merge company %s into %s: %s", secondary_id, primary_id, exc)
            raise

        logger.info("Merged company %s into %s in workspace %s", secondary_id, primary_id, workspace_id)
        return primary


def _normalize_name(value: Optional[str]) -> str:
    if not value:
        return ''
    compact = re.sub(r'[^a-zA-Z0-9]+', '', value.lower().strip())
    return compact


def _normalize_website(value: Optional[str]) -> str:
    if not value:
        return ''
    site = value.strip().lower()
    site = re.sub(r'^https?://', '', site)
    site = re.sub(r'^www\.', '', site)
    return site.rstrip('/')


def _normalize_phone(value: Optional[str]) -> str:
    if not value:
        return ''
    return ''.join(ch for ch in value if ch.isdigit())


def _company_to_dict(company: Company) -> Dict[str, Any]:
    return {
        'id': company.id,
        'name': company.name,
        'industry': company.industry,
        'size': company.size,
        'website': company.website,
        'phone': company.phone,
        'address': company.address,
        'parent_company_id': company.parent_company_id,
        'assigned_to': company.assigned_to,
        'created_at': company.created_at.isoformat() if company.created_at else None,
        'updated_at': company.updated_at.isoformat() if company.updated_at else None,
        'contact_count': len(company.contacts) if company.contacts is not None else 0,
        'deal_count': len(company.deals) if company.deals is not None else 0,
    }
