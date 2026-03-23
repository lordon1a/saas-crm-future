"""
Pipeline Service
Business logic for pipeline and deal management
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy import and_, or_
from models import db
from models_crm import Pipeline, DealStage, Deal, Activity, Contact, DealContact, WinLossReason

logger = logging.getLogger(__name__)


class PipelineService:
    """Service for managing pipelines and deals"""

    VALID_FORECAST_CATEGORIES = {'pipeline', 'best_case', 'commit'}
    VALID_REVENUE_TYPES = {'one_time', 'recurring'}
    VALID_CHURN_RISKS = {'low', 'medium', 'high'}

    @staticmethod
    def _emit_webhook_event(workspace_id: int, event_type: str, payload: Dict[str, Any]):
        try:
            from services.webhook_service import WebhookService
            WebhookService.dispatch_event(workspace_id, event_type, payload)
        except Exception as exc:
            logger.warning('Webhook dispatch failed for %s: %s', event_type, exc)
    
    @staticmethod
    def create_deal(workspace_id: int, data: Dict[str, Any]) -> Deal:
        """
        Create a new deal and assign it to the first stage of the pipeline.
        
        Args:
            workspace_id: Workspace ID
            data: Deal data (name, company_id, pipeline_id, value, expected_close_date, owner_id, contact_id)
        
        Returns:
            Deal: Created deal instance
        
        Raises:
            ValueError: If required fields are missing or pipeline not found
        """
        # Validate required fields
        required_fields = ['name', 'company_id', 'pipeline_id', 'owner_id']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        next_step = str(data.get('next_step') or '').strip()
        if not next_step:
            raise ValueError("next_step is required for open deals")

        revenue_type = str(data.get('revenue_type') or 'one_time').strip().lower()
        if revenue_type not in PipelineService.VALID_REVENUE_TYPES:
            raise ValueError("revenue_type must be one_time or recurring")

        forecast_category = str(data.get('forecast_category') or 'pipeline').strip().lower()
        if forecast_category not in PipelineService.VALID_FORECAST_CATEGORIES:
            raise ValueError("forecast_category must be pipeline, best_case, or commit")

        churn_risk = str(data.get('churn_risk') or 'low').strip().lower()
        if churn_risk not in PipelineService.VALID_CHURN_RISKS:
            raise ValueError("churn_risk must be low, medium, or high")
        
        # Validate company exists and belongs to workspace
        from models_crm import Company
        company = Company.query.filter_by(
            id=data['company_id'],
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        
        if not company:
            raise ValueError(f"Company {data['company_id']} not found in workspace")
        
        # Validate contact (optional)
        contact_id = data.get('contact_id')
        if contact_id is not None:
            contact = Contact.query.filter_by(
                id=contact_id,
                workspace_id=workspace_id,
                is_deleted=False,
            ).first()
            if not contact:
                raise ValueError(f"Contact {contact_id} not found in workspace")
            if contact.company_id and contact.company_id != data['company_id']:
                raise ValueError(
                    f"Contact {contact_id} belongs to company {contact.company_id}, "
                    f"not company {data['company_id']}"
                )

        # Get pipeline
        pipeline = Pipeline.query.filter_by(
            id=data['pipeline_id'],
            workspace_id=workspace_id
        ).first()
        
        if not pipeline:
            raise ValueError(f"Pipeline {data['pipeline_id']} not found")
        
        # Determine stage_id: use provided stage_id or default to first stage
        stage_id = data.get('stage_id')
        
        if stage_id:
            # Validate provided stage belongs to the pipeline
            stage = DealStage.query.filter_by(
                id=stage_id,
                pipeline_id=pipeline.id,
                is_active=True
            ).first()
            
            if not stage:
                raise ValueError(f"Stage {stage_id} not found in pipeline {pipeline.id}")
        else:
            # Get first stage (lowest order number)
            stage = DealStage.query.filter_by(
                pipeline_id=pipeline.id,
                is_active=True
            ).order_by(DealStage.order.asc()).first()
            
            if not stage:
                raise ValueError(f"Pipeline {pipeline.id} has no active stages")
            
            stage_id = stage.id
        
        try:
            # Create deal
            deal = Deal(
                workspace_id=workspace_id,
                name=data['name'],
                company_id=data['company_id'],
                contact_id=contact_id,
                pipeline_id=data['pipeline_id'],
                stage_id=stage_id,
                value=data.get('value', 0),
                revenue_type=revenue_type,
                mrr=data.get('mrr', 0),
                arr=data.get('arr', 0),
                renewal_date=data.get('renewal_date'),
                churn_risk=churn_risk,
                expected_close_date=data.get('expected_close_date'),
                owner_id=data['owner_id'],
                next_step=next_step,
                next_step_due_at=data.get('next_step_due_at'),
                last_activity_at=datetime.utcnow(),
                forecast_category=forecast_category,
                status='open'
            )
            
            db.session.add(deal)
            db.session.flush()  # Get deal.id

            # Keep deal_contacts synchronized with primary deal contact
            if contact_id is not None:
                stakeholder = DealContact.query.filter_by(
                    workspace_id=workspace_id,
                    deal_id=deal.id,
                    contact_id=contact_id,
                ).first()
                if not stakeholder:
                    stakeholder = DealContact(
                        workspace_id=workspace_id,
                        deal_id=deal.id,
                        contact_id=contact_id,
                        is_primary=True,
                        added_by=data['owner_id'],
                    )
                    db.session.add(stakeholder)
                DealContact.query.filter(
                    DealContact.workspace_id == workspace_id,
                    DealContact.deal_id == deal.id,
                    DealContact.contact_id != contact_id,
                    DealContact.is_primary.is_(True),
                ).update({DealContact.is_primary: False}, synchronize_session=False)
            
            # Create activity
            PipelineService._create_activity(
                workspace_id=workspace_id,
                deal_id=deal.id,
                user_id=data['owner_id'],
                activity_type='system',
                subject=f'Deal created: {deal.name}',
                body=f'Deal created in stage "{stage.name}" with value ${deal.value}'
            )
            
            db.session.commit()
            logger.info(f"Created deal {deal.id}: {deal.name}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create deal: {e}")
            raise

        # Webhook event AFTER commit (asenkron, DB lock'u uzatmaz)
        try:
            PipelineService._emit_webhook_event(workspace_id, 'deal.created', {
                'deal_id': deal.id,
                'name': deal.name,
                'company_id': deal.company_id,
                'contact_id': deal.contact_id,
                'pipeline_id': deal.pipeline_id,
                'stage_id': deal.stage_id,
                'value': float(deal.value),
                'status': deal.status,
                'updated_at': deal.updated_at.isoformat() if deal.updated_at else None,
            })
        except Exception as webhook_error:
            logger.warning(f"Webhook dispatch failed (non-blocking): {webhook_error}")
        
        return deal
    
    @staticmethod
    def update_deal(workspace_id: int, deal_id: int, data: Dict[str, Any], user_id: int) -> Deal:
        """
        Update a deal.
        
        Args:
            workspace_id: Workspace ID
            deal_id: Deal ID
            data: Updated fields
            user_id: User making the update
        
        Returns:
            Deal: Updated deal instance
        
        Raises:
            ValueError: If deal not found
        """
        deal = Deal.query.filter_by(
            id=deal_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        
        if not deal:
            raise ValueError(f"Deal {deal_id} not found")

        if 'revenue_type' in data:
            revenue_type = str(data.get('revenue_type') or '').strip().lower()
            if revenue_type not in PipelineService.VALID_REVENUE_TYPES:
                raise ValueError("revenue_type must be one_time or recurring")
            data['revenue_type'] = revenue_type

        if 'forecast_category' in data:
            forecast_category = str(data.get('forecast_category') or '').strip().lower()
            if forecast_category not in PipelineService.VALID_FORECAST_CATEGORIES:
                raise ValueError("forecast_category must be pipeline, best_case, or commit")
            data['forecast_category'] = forecast_category

        if 'churn_risk' in data:
            churn_risk = str(data.get('churn_risk') or '').strip().lower()
            if churn_risk not in PipelineService.VALID_CHURN_RISKS:
                raise ValueError("churn_risk must be low, medium, or high")
            data['churn_risk'] = churn_risk

        if 'next_step' in data and deal.status == 'open':
            next_step = str(data.get('next_step') or '').strip()
            if not next_step:
                raise ValueError("next_step cannot be empty for open deals")
            data['next_step'] = next_step
        
        # Track changes for activity log
        changes = {}
        
        # Update fields
        if 'contact_id' in data:
            new_contact_id = data.get('contact_id')
            if new_contact_id is not None:
                contact = Contact.query.filter_by(
                    id=new_contact_id,
                    workspace_id=workspace_id,
                    is_deleted=False,
                ).first()
                if not contact:
                    raise ValueError(f"Contact {new_contact_id} not found in workspace")
                if contact.company_id and contact.company_id != deal.company_id:
                    raise ValueError(
                        f"Contact {new_contact_id} belongs to company {contact.company_id}, "
                        f"not deal company {deal.company_id}"
                    )

        for field in [
            'name', 'value', 'expected_close_date', 'owner_id', 'contact_id',
            'revenue_type', 'mrr', 'arr', 'renewal_date', 'churn_risk',
            'next_step', 'next_step_due_at', 'forecast_category'
        ]:
            if field in data and getattr(deal, field) != data[field]:
                old_value = getattr(deal, field)
                setattr(deal, field, data[field])
                changes[field] = {'old': old_value, 'new': data[field]}
        
        if changes:
            try:
                deal.updated_at = datetime.utcnow()
                
                # Create activity
                change_desc = ', '.join([f"{k}: {v['old']} → {v['new']}" for k, v in changes.items()])
                PipelineService._create_activity(
                    workspace_id=workspace_id,
                    deal_id=deal.id,
                    user_id=user_id,
                    activity_type='system',
                    subject=f'Deal updated: {deal.name}',
                    body=f'Changes: {change_desc}'
                )

                if 'contact_id' in changes:
                    new_contact_id = data.get('contact_id')
                    if new_contact_id is None:
                        DealContact.query.filter(
                            DealContact.workspace_id == workspace_id,
                            DealContact.deal_id == deal.id,
                            DealContact.is_primary.is_(True),
                        ).update({DealContact.is_primary: False}, synchronize_session=False)
                    else:
                        stakeholder = DealContact.query.filter_by(
                            workspace_id=workspace_id,
                            deal_id=deal.id,
                            contact_id=new_contact_id,
                        ).first()
                        if not stakeholder:
                            stakeholder = DealContact(
                                workspace_id=workspace_id,
                                deal_id=deal.id,
                                contact_id=new_contact_id,
                                is_primary=True,
                                added_by=user_id,
                            )
                            db.session.add(stakeholder)
                        else:
                            stakeholder.is_primary = True
                        DealContact.query.filter(
                            DealContact.workspace_id == workspace_id,
                            DealContact.deal_id == deal.id,
                            DealContact.contact_id != new_contact_id,
                            DealContact.is_primary.is_(True),
                        ).update({DealContact.is_primary: False}, synchronize_session=False)
                
                db.session.commit()
                logger.info(f"Updated deal {deal.id}: {changes}")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Failed to update deal: {e}")
                raise

            # Webhook event AFTER commit (asenkron, DB lock'u uzatmaz)
            try:
                PipelineService._emit_webhook_event(workspace_id, 'deal.updated', {
                    'deal_id': deal.id,
                    'name': deal.name,
                    'company_id': deal.company_id,
                    'contact_id': deal.contact_id,
                    'pipeline_id': deal.pipeline_id,
                    'stage_id': deal.stage_id,
                    'value': float(deal.value),
                    'status': deal.status,
                    'changes': changes,
                    'updated_at': deal.updated_at.isoformat() if deal.updated_at else None,
                })
            except Exception as webhook_error:
                logger.warning(f"Webhook dispatch failed (non-blocking): {webhook_error}")
        
        return deal
    
    @staticmethod
    def move_deal_to_stage(workspace_id: int, deal_id: int, stage_id: int, user_id: int) -> Deal:
        """
        Move a deal to a different stage.
        
        Args:
            workspace_id: Workspace ID
            deal_id: Deal ID
            stage_id: Target stage ID
            user_id: User making the change
        
        Returns:
            Deal: Updated deal instance
        
        Raises:
            ValueError: If deal or stage not found, or stage not in same pipeline
        """
        deal = Deal.query.filter_by(
            id=deal_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        
        if not deal:
            raise ValueError(f"Deal {deal_id} not found")
        
        new_stage = DealStage.query.filter_by(id=stage_id).first()
        
        if not new_stage:
            raise ValueError(f"Stage {stage_id} not found")
        
        if new_stage.pipeline_id != deal.pipeline_id:
            raise ValueError(f"Stage {stage_id} is not in pipeline {deal.pipeline_id}")
        
        old_stage = deal.stage
        old_stage_id = old_stage.id
        old_stage_name = old_stage.name
        new_stage_name = new_stage.name
        old_version = deal.version
        now = datetime.utcnow()

        try:
            # Atomic optimistic lock: update only if version is unchanged.
            # This prevents false conflicts and correctly detects concurrent writes.
            rows_updated = Deal.query.filter_by(
                id=deal.id,
                workspace_id=workspace_id,
                is_deleted=False,
                version=old_version
            ).update({
                Deal.stage_id: stage_id,
                Deal.stage_entered_at: now,
                Deal.updated_at: now,
                Deal.version: old_version + 1,
            }, synchronize_session=False)

            if rows_updated == 0:
                db.session.rollback()
                raise ValueError('Deal was modified by another user. Please refresh and try again.')
            
            # Create activity (non-blocking)
            try:
                PipelineService._create_activity(
                    workspace_id=workspace_id,
                    deal_id=deal.id,
                    user_id=user_id,
                    activity_type='system',
                    subject=f'Deal moved: {deal.name}',
                    body=f'Stage changed from "{old_stage_name}" to "{new_stage_name}"'
                )
            except Exception as activity_error:
                logger.warning(f"Activity creation failed (non-blocking): {activity_error}")
            
            db.session.commit()
            db.session.refresh(deal)
            logger.info(f"Moved deal {deal.id} from stage {old_stage_id} to {stage_id}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to move deal: {e}")
            raise

        # Webhook event AFTER commit (asenkron, spawn edilir - response'u bloklamaz)
        try:
            import gevent
            gevent.spawn(
                PipelineService._emit_webhook_event,
                workspace_id,
                'deal.updated',
                {
                    'deal_id': deal.id,
                    'name': deal.name,
                    'company_id': deal.company_id,
                    'contact_id': deal.contact_id,
                    'pipeline_id': deal.pipeline_id,
                    'stage_id': deal.stage_id,
                    'status': deal.status,
                    'change_type': 'stage_move',
                    'previous_stage_id': old_stage_id,
                    'new_stage_id': stage_id,
                    'updated_at': deal.updated_at.isoformat() if deal.updated_at else None,
                }
            )
        except Exception as webhook_error:
            logger.warning(f"Webhook spawn failed (non-blocking): {webhook_error}")
        
        return deal
    
    @staticmethod
    def close_deal(workspace_id: int, deal_id: int, status: str, win_loss_reason: str, user_id: int, win_loss_reason_id: Optional[int] = None) -> Deal:
        """
        Close a deal as won or lost.
        
        Args:
            workspace_id: Workspace ID
            deal_id: Deal ID
            status: 'won' or 'lost'
            win_loss_reason: Reason for win/loss (required)
            user_id: User closing the deal
        
        Returns:
            Deal: Updated deal instance
        
        Raises:
            ValueError: If deal not found, invalid status, or missing reason
        """
        status = str(status or '').strip().lower()
        if status not in ['won', 'lost']:
            raise ValueError(f"Invalid status: {status}. Must be 'won' or 'lost'")
        
        if not win_loss_reason_id:
            raise ValueError("win_loss_reason_id is required when closing a deal")
        
        deal = Deal.query.filter_by(
            id=deal_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        
        if not deal:
            raise ValueError(f"Deal {deal_id} not found")

        reason_obj = WinLossReason.query.filter_by(
            id=win_loss_reason_id,
            workspace_id=workspace_id,
            is_active=True
        ).first()
        if not reason_obj:
            raise ValueError("Invalid win_loss_reason_id")
        expected_reason_category = 'win' if status == 'won' else 'loss'
        if reason_obj.category != expected_reason_category:
            raise ValueError("win_loss_reason_id category must match deal close status")
        if not win_loss_reason or not win_loss_reason.strip():
            win_loss_reason = reason_obj.label
        
        try:
            deal.status = status
            deal.win_loss_reason = win_loss_reason
            deal.win_loss_reason_id = reason_obj.id if reason_obj else None
            deal.closed_at = datetime.utcnow()
            deal.updated_at = datetime.utcnow()
            
            # Create activity
            PipelineService._create_activity(
                workspace_id=workspace_id,
                deal_id=deal.id,
                user_id=user_id,
                activity_type='system',
                subject=f'Deal closed: {deal.name}',
                body=f'Status: {status.upper()}\nReason: {win_loss_reason}'
            )
            
            db.session.commit()
            logger.info(f"Closed deal {deal.id} as {status}: {win_loss_reason}")
            
            # Trigger automation for won deals (DocGen)
            if status == 'won':
                try:
                    from services.automation_engine import AutomationEngine
                    from models_automation import AutomationRule
                    
                    # Find automation rules for deal won event
                    automation_rules = AutomationRule.query.filter_by(
                        workspace_id=workspace_id,
                        trigger_type='deal_won',
                        is_active=True
                    ).all()
                    
                    context = {
                        'deal_id': deal.id,
                        'deal_name': deal.name,
                        'deal_value': deal.value,
                        'company_id': deal.company_id,
                        'contact_id': deal.contact_id
                    }
                    
                    for rule in automation_rules:
                        try:
                            AutomationEngine.execute_rule(rule, context=context)
                        except Exception as rule_error:
                            logger.warning(f"Automation rule {rule.id} failed (non-blocking): {rule_error}")
                            
                except Exception as automation_error:
                    logger.warning(f"Automation trigger failed (non-blocking): {automation_error}")
                    
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to close deal: {e}")
            raise

        # Webhook event AFTER commit (asenkron, DB lock'u uzatmaz)
        try:
            PipelineService._emit_webhook_event(workspace_id, 'deal.updated', {
                'deal_id': deal.id,
                'name': deal.name,
                'company_id': deal.company_id,
                'contact_id': deal.contact_id,
                'pipeline_id': deal.pipeline_id,
                'stage_id': deal.stage_id,
                'status': deal.status,
                'forecast_category': deal.forecast_category,
                'win_loss_reason': deal.win_loss_reason,
                'win_loss_reason_id': deal.win_loss_reason_id,
                'closed_at': deal.closed_at.isoformat() if deal.closed_at else None,
                'updated_at': deal.updated_at.isoformat() if deal.updated_at else None,
            })
        except Exception as webhook_error:
            logger.warning(f"Webhook dispatch failed (non-blocking): {webhook_error}")
        
        return deal

    @staticmethod
    def reopen_deal(workspace_id: int, deal_id: int, user_id: int) -> Deal:
        """
        Reopen a won/lost deal back to open state.
        """
        deal = Deal.query.filter_by(
            id=deal_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        if not deal:
            raise ValueError(f"Deal {deal_id} not found")
        if deal.status == 'open':
            return deal

        previous_status = deal.status
        previous_reason = deal.win_loss_reason
        try:
            deal.status = 'open'
            deal.closed_at = None
            deal.win_loss_reason = None
            deal.win_loss_reason_id = None
            deal.updated_at = datetime.utcnow()
            if not deal.last_activity_at:
                deal.last_activity_at = datetime.utcnow()

            PipelineService._create_activity(
                workspace_id=workspace_id,
                deal_id=deal.id,
                user_id=user_id,
                activity_type='system',
                subject=f'Deal reopened: {deal.name}',
                body=f'Previous status: {str(previous_status).upper()}'
                     + (f'\nPrevious reason: {previous_reason}' if previous_reason else '')
            )

            db.session.commit()
            logger.info("Reopened deal %s from %s", deal.id, previous_status)
        except Exception as e:
            db.session.rollback()
            logger.error("Failed to reopen deal: %s", e)
            raise

        try:
            PipelineService._emit_webhook_event(workspace_id, 'deal.updated', {
                'deal_id': deal.id,
                'name': deal.name,
                'status': deal.status,
                'closed_at': None,
                'win_loss_reason': None,
                'win_loss_reason_id': None,
                'updated_at': deal.updated_at.isoformat() if deal.updated_at else None,
            })
        except Exception as webhook_error:
            logger.warning("Webhook dispatch failed (non-blocking): %s", webhook_error)

        return deal

    @staticmethod
    def soft_delete_deal(workspace_id: int, deal_id: int, user_id: int) -> Deal:
        deal = Deal.query.filter_by(
            id=deal_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        if not deal:
            raise ValueError(f"Deal {deal_id} not found")

        try:
            deal.is_deleted = True
            deal.deleted_at = datetime.utcnow()
            deal.updated_at = datetime.utcnow()

            PipelineService._create_activity(
                workspace_id=workspace_id,
                deal_id=deal.id,
                user_id=user_id,
                activity_type='system',
                subject=f'Deal deleted: {deal.name}',
                body='Deal moved to recycle bin'
            )

            db.session.commit()
            logger.info("Soft deleted deal %s", deal.id)
            return deal
        except Exception as e:
            db.session.rollback()
            logger.error("Failed to soft delete deal: %s", e)
            raise

    @staticmethod
    def restore_deleted_deal(workspace_id: int, deal_id: int, user_id: int) -> Deal:
        deal = Deal.query.filter_by(
            id=deal_id,
            workspace_id=workspace_id,
            is_deleted=True,
        ).first()
        if not deal:
            raise ValueError(f"Deleted deal {deal_id} not found")

        try:
            deal.is_deleted = False
            deal.deleted_at = None
            deal.updated_at = datetime.utcnow()
            if not deal.last_activity_at:
                deal.last_activity_at = datetime.utcnow()

            PipelineService._create_activity(
                workspace_id=workspace_id,
                deal_id=deal.id,
                user_id=user_id,
                activity_type='system',
                subject=f'Deal restored: {deal.name}',
                body='Deal restored from recycle bin'
            )

            db.session.commit()
            logger.info("Restored deal %s from recycle bin", deal.id)
            return deal
        except Exception as e:
            db.session.rollback()
            logger.error("Failed to restore deal: %s", e)
            raise

    @staticmethod
    def list_deleted_deals(workspace_id: int, limit: int = 100) -> List[Deal]:
        safe_limit = max(1, min(int(limit or 100), 500))
        return Deal.query.filter_by(
            workspace_id=workspace_id,
            is_deleted=True
        ).order_by(
            Deal.deleted_at.desc(),
            Deal.updated_at.desc()
        ).limit(safe_limit).all()
    
    @staticmethod
    def get_deals(workspace_id: int, filters: Optional[Dict[str, Any]] = None) -> List[Deal]:
        """
        Get deals with optional filters.
        
        Args:
            workspace_id: Workspace ID
            filters: Optional filters (stage_id, owner_id, status, company_id, contact_id)
        
        Returns:
            List[Deal]: List of deals
        """
        query = Deal.query.filter_by(workspace_id=workspace_id, is_deleted=False)
        
        if filters:
            if 'stage_id' in filters:
                query = query.filter_by(stage_id=filters['stage_id'])
            if 'owner_id' in filters:
                query = query.filter_by(owner_id=filters['owner_id'])
            if 'status' in filters:
                query = query.filter_by(status=filters['status'])
            if 'company_id' in filters:
                query = query.filter_by(company_id=filters['company_id'])
            if 'contact_id' in filters:
                query = query.filter_by(contact_id=filters['contact_id'])
            if 'pipeline_id' in filters:
                query = query.filter_by(pipeline_id=filters['pipeline_id'])
            if 'forecast_category' in filters:
                query = query.filter_by(forecast_category=filters['forecast_category'])
            if 'revenue_type' in filters:
                query = query.filter_by(revenue_type=filters['revenue_type'])
            if 'churn_risk' in filters:
                query = query.filter_by(churn_risk=filters['churn_risk'])
        
        return query.order_by(Deal.created_at.desc()).all()
    
    @staticmethod
    def calculate_forecast(workspace_id: int, pipeline_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Calculate sales forecast based on weighted pipeline values.
        Formula: weighted_value = deal.value × stage.probability
        
        Args:
            workspace_id: Workspace ID
            pipeline_id: Optional pipeline ID to filter by
        
        Returns:
            Dict with forecast data:
            {
                'total_forecast': float,
                'total_deals': int,
                'by_stage': [{stage_name, deal_count, total_value, weighted_value}]
            }
        """
        query = Deal.query.filter_by(
            workspace_id=workspace_id,
            status='open',
            is_deleted=False,
        )
        
        if pipeline_id:
            query = query.filter_by(pipeline_id=pipeline_id)
        
        deals = query.all()
        
        # Calculate totals
        total_forecast = sum(deal.get_weighted_value() for deal in deals)
        
        # Group by stage
        stage_data = {}
        for deal in deals:
            stage_name = deal.stage.name
            if stage_name not in stage_data:
                stage_data[stage_name] = {
                    'stage_name': stage_name,
                    'stage_order': deal.stage.order,
                    'deal_count': 0,
                    'total_value': 0,
                    'weighted_value': 0
                }
            
            stage_data[stage_name]['deal_count'] += 1
            stage_data[stage_name]['total_value'] += float(deal.value)
            stage_data[stage_name]['weighted_value'] += deal.get_weighted_value()
        
        # Sort by stage order
        by_stage = sorted(stage_data.values(), key=lambda x: x['stage_order'])
        
        return {
            'total_forecast': total_forecast,
            'total_deals': len(deals),
            'by_stage': by_stage,
            'by_category': {
                'pipeline': round(sum(float(d.value) for d in deals if d.forecast_category == 'pipeline'), 2),
                'best_case': round(sum(float(d.value) for d in deals if d.forecast_category == 'best_case'), 2),
                'commit': round(sum(float(d.value) for d in deals if d.forecast_category == 'commit'), 2),
            }
        }
    
    @staticmethod
    def get_pipeline_with_stages(workspace_id: int, pipeline_id: int) -> Optional[Pipeline]:
        """
        Get a pipeline with its stages.
        
        Args:
            workspace_id: Workspace ID
            pipeline_id: Pipeline ID
        
        Returns:
            Pipeline: Pipeline instance with stages loaded
        """
        return Pipeline.query.filter_by(
            id=pipeline_id,
            workspace_id=workspace_id
        ).first()
    
    @staticmethod
    def _create_activity(workspace_id: int, deal_id: int, user_id: int, 
                        activity_type: str, subject: str, body: str) -> Activity:
        """
        Create an activity record.
        
        Args:
            workspace_id: Workspace ID
            deal_id: Deal ID
            user_id: User ID
            activity_type: Activity type
            subject: Activity subject
            body: Activity body
        
        Returns:
            Activity: Created activity instance
        """
        activity = Activity(
            workspace_id=workspace_id,
            deal_id=deal_id,
            user_id=user_id,
            activity_type=activity_type,
            subject=subject,
            body=body
        )
        db.session.add(activity)
        deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id, is_deleted=False).first()
        if deal:
            deal.last_activity_at = datetime.utcnow()
            deal.updated_at = datetime.utcnow()
        return activity
    
    @staticmethod
    def _emit_webhook_event(workspace_id: int, event_type: str, payload: dict):
        """
        Emit webhook event for external integrations with HMAC signing.
        """
        try:
            import json
            import hmac
            import hashlib
            from models import Workspace
            
            # Get workspace webhook configuration
            workspace = Workspace.query.get(workspace_id)
            if not workspace or not hasattr(workspace, 'webhook_url') or not workspace.webhook_url:
                return  # No webhook configured
            
            # Create signed payload
            payload_json = json.dumps(payload, sort_keys=True)
            
            # Get or generate webhook secret
            webhook_secret = getattr(workspace, 'webhook_secret', None)
            if not webhook_secret:
                return  # No secret configured
            
            # Generate HMAC signature
            signature = hmac.new(
                webhook_secret.encode('utf-8'),
                payload_json.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # TODO: Implement actual HTTP POST to webhook_url with signature
            # headers = {
            #     'Content-Type': 'application/json',
            #     'X-Webhook-Signature': signature,
            #     'X-Event-Type': event_type
            # }
            # requests.post(workspace.webhook_url, data=payload_json, headers=headers, timeout=5)
            
        except Exception as e:
            logger.warning(f"Webhook dispatch failed (non-blocking): {e}")
    
    @staticmethod
    def get_rotting_deals(workspace_id: int, pipeline_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get deals that have been in their current stage too long.
        
        Args:
            workspace_id: Workspace ID
            pipeline_id: Optional pipeline ID to filter by
        
        Returns:
            List of rotting deals with metadata
        """
        from models import db
        
        query = Deal.query.filter_by(
            workspace_id=workspace_id,
            status='open',
            is_deleted=False,
        ).join(DealStage).filter(DealStage.rotting_days.isnot(None))
        
        if pipeline_id:
            query = query.filter_by(pipeline_id=pipeline_id)
        
        # Eager load relationships to avoid lazy loading issues
        query = query.options(
            db.joinedload(Deal.stage),
            db.joinedload(Deal.company)
        )
        
        deals = query.all()
        rotting_deals = []
        
        for deal in deals:
            try:
                if deal.is_rotting():
                    rotting_deals.append({
                        'deal_id': deal.id,
                        'deal_name': deal.name,
                        'stage_name': deal.stage.name if deal.stage else 'Unknown',
                        'days_in_stage': deal.days_in_current_stage(),
                        'rotting_threshold': deal.stage.rotting_days if deal.stage else 0,
                        'owner_id': deal.owner_id,
                        'company_name': deal.company.name if deal.company else None
                    })
            except Exception as e:
                logger.warning(f"Error processing rotting deal {deal.id}: {e}")
                continue
        
        return rotting_deals
    
    @staticmethod
    def create_auto_tasks_for_rotting_deals(workspace_id: int) -> int:
        """
        Create automatic reminder tasks for deals that have been stale.
        
        Args:
            workspace_id: Workspace ID
        
        Returns:
            Number of tasks created
        """
        from models_crm import Task
        
        rotting_deals = PipelineService.get_rotting_deals(workspace_id)
        tasks_created = 0
        
        for deal_info in rotting_deals:
            deal_id = deal_info['deal_id']
            
            # Check if reminder task already exists for this deal
            existing_task = Task.query.filter_by(
                workspace_id=workspace_id,
                deal_id=deal_id,
                status='not_started',
                title=f"Follow up: {deal_info['deal_name']}"
            ).first()
            
            if existing_task:
                continue  # Skip if task already exists
            
            try:
                # Create reminder task
                task = Task(
                    workspace_id=workspace_id,
                    title=f"Follow up: {deal_info['deal_name']}",
                    description=f"This deal has been in '{deal_info['stage_name']}' stage for {deal_info['days_in_stage']} days. Please follow up with the customer.",
                    assignee_id=deal_info['owner_id'],
                    deal_id=deal_id,
                    status='not_started',
                    priority='high',
                    due_date=datetime.utcnow(),
                    is_customer_facing=False
                )
                db.session.add(task)
                tasks_created += 1
            except Exception as e:
                logger.error(f"Failed to create auto-task for deal {deal_id}: {e}")
                continue
        
        if tasks_created > 0:
            try:
                db.session.commit()
                logger.info(f"Created {tasks_created} auto-tasks for rotting deals in workspace {workspace_id}")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Failed to commit auto-tasks: {e}")
                return 0
        
        return tasks_created
