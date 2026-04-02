"""
Pipeline Advanced Service
Week-3 features for CPQ, taxonomy, hygiene and duplicate merge.
"""
import json
import logging
from difflib import SequenceMatcher
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Set

from models import db
from models_crm import (
    Activity,
    Deal,
    DealLineItem,
    DealMergeHistory,
    Product,
    Quote,
    QuoteLineItem,
    Task,
    WinLossReason,
)

logger = logging.getLogger(__name__)

DEFAULT_WIN_LOSS_REASONS = {
    'win': [
        ('budget_approved', 'Bütçe Onaylandı'),
        ('best_value', 'En İyi Fiyat/Değer'),
        ('strong_relationship', 'Güçlü İlişki / Güven'),
        ('better_timeline', 'Daha Hızlı Termin'),
        ('feature_fit', 'Ürün Uyumlu (Feature Fit)'),
    ],
    'loss': [
        ('price_too_high', 'Fiyat Yüksek'),
        ('lost_to_competitor', 'Rakibe Kaybedildi'),
        ('no_budget', 'Bütçe Yok'),
        ('no_decision', 'Karar Çıkmadı'),
        ('timing_not_right', 'Zamanlama Uygun Değil'),
    ],
}


class PipelineAdvancedService:
    """Advanced business logic for pipeline module."""

    @staticmethod
    def _normalize_accessible_deal_ids(accessible_deal_ids: Optional[Iterable[int]]) -> Optional[Set[int]]:
        """Normalize access scope values into a set of integer deal IDs."""
        if accessible_deal_ids is None:
            return None
        normalized: Set[int] = set()
        for deal_id in accessible_deal_ids:
            try:
                normalized.add(int(deal_id))
            except (TypeError, ValueError):
                continue
        return normalized

    @staticmethod
    def list_products(workspace_id: int, search: Optional[str] = None, active_only: bool = True) -> List[Product]:
        query = Product.query.filter_by(workspace_id=workspace_id)
        if active_only:
            query = query.filter_by(is_active=True)
        if search:
            like = f"%{search.strip()}%"
            query = query.filter(Product.name.ilike(like))
        return query.order_by(Product.name.asc()).all()

    @staticmethod
    def create_product(workspace_id: int, payload: Dict[str, Any]) -> Product:
        if not payload.get('name'):
            raise ValueError('name is required')
        product = Product(
            workspace_id=workspace_id,
            sku=(payload.get('sku') or None),
            name=payload['name'].strip(),
            description=payload.get('description'),
            currency=(payload.get('currency') or 'TRY').upper(),
            unit_price=payload.get('unit_price', 0),
            is_active=bool(payload.get('is_active', True)),
        )
        try:
            db.session.add(product)
            db.session.commit()
            return product
        except Exception:
            db.session.rollback()
            logger.exception("Failed to create product")
            raise

    @staticmethod
    def add_deal_line_item(workspace_id: int, deal_id: int, payload: Dict[str, Any]) -> DealLineItem:
        deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id, is_deleted=False).first()
        if not deal:
            raise LookupError('Deal not found')

        product_id = payload.get('product_id')
        product = None
        if product_id is not None:
            product = Product.query.filter_by(id=product_id, workspace_id=workspace_id).first()
            if not product:
                raise LookupError('Product not found')

        item_name = payload.get('item_name') or (product.name if product else None)
        if not item_name:
            raise ValueError('item_name is required')

        quantity = float(payload.get('quantity', 1) or 1)
        unit_price = float(payload.get('unit_price', product.unit_price if product else 0) or 0)
        discount_pct = float(payload.get('discount_pct', 0) or 0)
        tax_pct = float(payload.get('tax_pct', 0) or 0)
        subtotal = quantity * unit_price
        discount_total = subtotal * (discount_pct / 100.0)
        taxable = subtotal - discount_total
        tax_total = taxable * (tax_pct / 100.0)
        total_amount = taxable + tax_total

        line = DealLineItem(
            workspace_id=workspace_id,
            deal_id=deal_id,
            product_id=product_id,
            item_name=item_name,
            quantity=quantity,
            unit_price=unit_price,
            discount_pct=discount_pct,
            tax_pct=tax_pct,
            total_amount=round(total_amount, 2),
        )
        try:
            db.session.add(line)
            db.session.flush()
            PipelineAdvancedService._refresh_deal_amounts(workspace_id, deal_id)
            db.session.commit()
            return line
        except Exception:
            db.session.rollback()
            logger.exception("Failed to add deal line item")
            raise

    @staticmethod
    def list_deal_line_items(workspace_id: int, deal_id: int) -> List[DealLineItem]:
        return DealLineItem.query.filter_by(workspace_id=workspace_id, deal_id=deal_id).order_by(DealLineItem.created_at.asc()).all()

    @staticmethod
    def remove_deal_line_item(workspace_id: int, deal_id: int, line_item_id: int) -> None:
        line = DealLineItem.query.filter_by(
            id=line_item_id,
            workspace_id=workspace_id,
            deal_id=deal_id,
        ).first()
        if not line:
            raise LookupError('Line item not found')
        try:
            db.session.delete(line)
            db.session.flush()
            PipelineAdvancedService._refresh_deal_amounts(workspace_id, deal_id)
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception("Failed to delete deal line item")
            raise

    @staticmethod
    def create_quote_from_deal(workspace_id: int, deal_id: int, user_id: int, payload: Dict[str, Any]) -> Quote:
        deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id, is_deleted=False).first()
        if not deal:
            raise LookupError('Deal not found')

        line_items = PipelineAdvancedService.list_deal_line_items(workspace_id, deal_id)
        if not line_items:
            raise ValueError('Deal has no line items')

        sequence = Quote.query.filter_by(workspace_id=workspace_id).count() + 1
        quote_number = payload.get('quote_number') or f"Q-{datetime.utcnow().strftime('%Y%m%d')}-{sequence:04d}"
        valid_until = payload.get('valid_until')
        if valid_until is None:
            valid_until = (datetime.utcnow() + timedelta(days=14)).date()

        quote = Quote(
            workspace_id=workspace_id,
            deal_id=deal_id,
            quote_number=quote_number,
            status=payload.get('status', 'draft'),
            valid_until=valid_until,
            currency=payload.get('currency', 'TRY'),
            notes=payload.get('notes'),
            created_by=user_id,
        )

        subtotal = 0.0
        discount_total = 0.0
        tax_total = 0.0

        try:
            db.session.add(quote)
            db.session.flush()

            for line in line_items:
                line_subtotal = float(line.quantity) * float(line.unit_price)
                line_discount = line_subtotal * (float(line.discount_pct) / 100.0)
                line_taxable = line_subtotal - line_discount
                line_tax = line_taxable * (float(line.tax_pct) / 100.0)
                total_amount = line_taxable + line_tax
                subtotal += line_subtotal
                discount_total += line_discount
                tax_total += line_tax

                db.session.add(QuoteLineItem(
                    workspace_id=workspace_id,
                    quote_id=quote.id,
                    product_id=line.product_id,
                    item_name=line.item_name,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    discount_pct=line.discount_pct,
                    tax_pct=line.tax_pct,
                    total_amount=round(total_amount, 2),
                ))

            quote.subtotal = round(subtotal, 2)
            quote.discount_total = round(discount_total, 2)
            quote.tax_total = round(tax_total, 2)
            quote.grand_total = round(subtotal - discount_total + tax_total, 2)
            db.session.commit()
            return quote
        except Exception:
            db.session.rollback()
            logger.exception("Failed to create quote from deal")
            raise

    @staticmethod
    def list_quotes(workspace_id: int, deal_id: Optional[int] = None) -> List[Quote]:
        query = Quote.query.filter_by(workspace_id=workspace_id)
        if deal_id:
            query = query.filter_by(deal_id=deal_id)
        return query.order_by(Quote.created_at.desc()).all()

    @staticmethod
    def list_win_loss_reasons(workspace_id: int, category: Optional[str] = None) -> List[WinLossReason]:
        PipelineAdvancedService.ensure_default_win_loss_reasons(workspace_id)
        query = WinLossReason.query.filter_by(workspace_id=workspace_id, is_active=True)
        if category:
            query = query.filter_by(category=category)
        return query.order_by(WinLossReason.category.asc(), WinLossReason.label.asc()).all()

    @staticmethod
    def ensure_default_win_loss_reasons(workspace_id: int) -> int:
        existing = WinLossReason.query.filter_by(workspace_id=workspace_id).all()
        existing_keys = {(r.category, (r.code or '').strip().lower()) for r in existing}

        to_create: List[WinLossReason] = []
        for reason_category, reason_items in DEFAULT_WIN_LOSS_REASONS.items():
            for reason_code, reason_label in reason_items:
                reason_key = (reason_category, reason_code)
                if reason_key in existing_keys:
                    continue
                to_create.append(WinLossReason(
                    workspace_id=workspace_id,
                    category=reason_category,
                    code=reason_code,
                    label=reason_label,
                    is_active=True,
                ))

        if not to_create:
            return 0

        try:
            db.session.add_all(to_create)
            db.session.commit()
            return len(to_create)
        except Exception:
            db.session.rollback()
            logger.exception("Failed to seed default win/loss reasons")
            raise

    @staticmethod
    def create_win_loss_reason(workspace_id: int, payload: Dict[str, Any]) -> WinLossReason:
        category = (payload.get('category') or '').strip().lower()
        code = (payload.get('code') or '').strip().lower()
        label = (payload.get('label') or '').strip()
        if category not in {'win', 'loss'}:
            raise ValueError('category must be win or loss')
        if not code or not label:
            raise ValueError('code and label are required')
        reason = WinLossReason(
            workspace_id=workspace_id,
            category=category,
            code=code,
            label=label,
            is_active=bool(payload.get('is_active', True)),
        )
        try:
            db.session.add(reason)
            db.session.commit()
            return reason
        except Exception:
            db.session.rollback()
            logger.exception("Failed to create win/loss reason")
            raise

    @staticmethod
    def find_deal_duplicates(
        workspace_id: int,
        accessible_deal_ids: Optional[Iterable[int]] = None,
    ) -> List[Dict[str, Any]]:
        allowed_ids = PipelineAdvancedService._normalize_accessible_deal_ids(accessible_deal_ids)
        if allowed_ids is not None and not allowed_ids:
            return []

        query = Deal.query.filter_by(workspace_id=workspace_id, is_deleted=False)
        if allowed_ids is not None:
            query = query.filter(Deal.id.in_(allowed_ids))

        deals = query.all()
        by_company: Dict[int, List[Deal]] = {}
        for deal in deals:
            by_company.setdefault(deal.company_id, []).append(deal)

        duplicate_groups: List[Dict[str, Any]] = []
        for company_id, company_deals in by_company.items():
            if len(company_deals) < 2:
                continue

            pairs: List[Dict[str, Any]] = []
            for idx, left in enumerate(company_deals):
                left_name = (left.name or '').strip().lower()
                if not left_name:
                    continue
                for right in company_deals[idx + 1:]:
                    right_name = (right.name or '').strip().lower()
                    if not right_name:
                        continue

                    title_similarity = SequenceMatcher(None, left_name, right_name).ratio()

                    close_days_diff = None
                    if left.expected_close_date and right.expected_close_date:
                        close_days_diff = abs((left.expected_close_date - right.expected_close_date).days)
                    else:
                        close_days_diff = abs((left.created_at - right.created_at).days)

                    is_duplicate_like = (
                        title_similarity >= 0.80 and close_days_diff <= 45
                    ) or (
                        title_similarity >= 0.92
                    )

                    if is_duplicate_like:
                        pairs.append({
                            'left': _deal_to_dict(left),
                            'right': _deal_to_dict(right),
                            'title_similarity': round(title_similarity, 3),
                            'date_distance_days': int(close_days_diff),
                        })

            if pairs:
                duplicate_groups.append({
                    'company_id': company_id,
                    'candidate_pairs': pairs,
                })
        return duplicate_groups

    @staticmethod
    def merge_deals(
        workspace_id: int,
        primary_id: int,
        secondary_id: int,
        user_id: int,
        accessible_deal_ids: Optional[Iterable[int]] = None,
    ) -> Deal:
        allowed_ids = PipelineAdvancedService._normalize_accessible_deal_ids(accessible_deal_ids)
        if allowed_ids is not None and (
            int(primary_id) not in allowed_ids or int(secondary_id) not in allowed_ids
        ):
            raise PermissionError('Access denied to one or more deals')

        primary = Deal.query.filter_by(id=primary_id, workspace_id=workspace_id, is_deleted=False).first()
        secondary = Deal.query.filter_by(id=secondary_id, workspace_id=workspace_id, is_deleted=False).first()
        if not primary or not secondary:
            raise LookupError('Deal not found')
        if primary_id == secondary_id:
            raise ValueError('Cannot merge same deal')

        snapshot = _deal_to_dict(secondary)
        try:
            Task.query.filter_by(workspace_id=workspace_id, deal_id=secondary_id).update({'deal_id': primary_id}, synchronize_session=False)
            Activity.query.filter_by(workspace_id=workspace_id, deal_id=secondary_id).update({'deal_id': primary_id}, synchronize_session=False)
            DealLineItem.query.filter_by(workspace_id=workspace_id, deal_id=secondary_id).update({'deal_id': primary_id}, synchronize_session=False)
            Quote.query.filter_by(workspace_id=workspace_id, deal_id=secondary_id).update({'deal_id': primary_id}, synchronize_session=False)
            secondary.is_deleted = True
            secondary.deleted_at = datetime.utcnow()
            secondary.updated_at = datetime.utcnow()

            db.session.add(DealMergeHistory(
                workspace_id=workspace_id,
                primary_deal_id=primary_id,
                merged_deal_id=secondary_id,
                merged_data_json=json.dumps(snapshot, default=str),
                merged_by=user_id,
            ))
            db.session.commit()
            return primary
        except Exception:
            db.session.rollback()
            logger.exception("Failed to merge deals")
            raise

    @staticmethod
    def get_hygiene_report(workspace_id: int, stale_days: int = 7) -> Dict[str, Any]:
        now = datetime.utcnow()
        threshold = now - timedelta(days=max(1, stale_days))
        open_deals = Deal.query.filter_by(workspace_id=workspace_id, status='open', is_deleted=False).all()

        missing_next_step = []
        stale_last_activity = []
        overdue_next_step = []

        for deal in open_deals:
            if not deal.next_step:
                missing_next_step.append(_deal_to_dict(deal))
            if not deal.last_activity_at or deal.last_activity_at < threshold:
                stale_last_activity.append(_deal_to_dict(deal))
            if deal.next_step_due_at and deal.next_step_due_at < now:
                overdue_next_step.append(_deal_to_dict(deal))

        return {
            'open_deal_count': len(open_deals),
            'missing_next_step': missing_next_step,
            'stale_last_activity': stale_last_activity,
            'overdue_next_step': overdue_next_step,
        }

    @staticmethod
    def _refresh_deal_amounts(workspace_id: int, deal_id: int) -> None:
        deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id, is_deleted=False).first()
        if not deal:
            return
        items = DealLineItem.query.filter_by(workspace_id=workspace_id, deal_id=deal_id).all()
        total = round(sum(float(item.total_amount) for item in items), 2)
        deal.value = total
        deal.updated_at = datetime.utcnow()


def _deal_to_dict(deal: Deal) -> Dict[str, Any]:
    return {
        'id': deal.id,
        'name': deal.name,
        'company_id': deal.company_id,
        'status': deal.status,
        'value': float(deal.value or 0),
        'expected_close_date': deal.expected_close_date.isoformat() if deal.expected_close_date else None,
        'forecast_category': deal.forecast_category,
        'next_step': deal.next_step,
        'next_step_due_at': deal.next_step_due_at.isoformat() if deal.next_step_due_at else None,
        'last_activity_at': deal.last_activity_at.isoformat() if deal.last_activity_at else None,
    }
