"""
Pipeline Service
Business logic for pipeline and deal management
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy import and_, or_
from models import db
from models_crm import Pipeline, DealStage, Deal, Activity

logger = logging.getLogger(__name__)


class PipelineService:
    """Service for managing pipelines and deals"""

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
            data: Deal data (name, company_id, pipeline_id, value, expected_close_date, owner_id)
        
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
        
        # Validate company exists and belongs to workspace
        from models_crm import Company
        company = Company.query.filter_by(
            id=data['company_id'],
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        
        if not company:
            raise ValueError(f"Company {data['company_id']} not found in workspace")
        
        # Get pipeline and first stage
        pipeline = Pipeline.query.filter_by(
            id=data['pipeline_id'],
            workspace_id=workspace_id
        ).first()
        
        if not pipeline:
            raise ValueError(f"Pipeline {data['pipeline_id']} not found")
        
        # Get first stage (lowest order number)
        first_stage = DealStage.query.filter_by(
            pipeline_id=pipeline.id
        ).order_by(DealStage.order.asc()).first()
        
        if not first_stage:
            raise ValueError(f"Pipeline {pipeline.id} has no stages")
        
        # Create deal
        deal = Deal(
            workspace_id=workspace_id,
            name=data['name'],
            company_id=data['company_id'],
            pipeline_id=data['pipeline_id'],
            stage_id=first_stage.id,
            value=data.get('value', 0),
            expected_close_date=data.get('expected_close_date'),
            owner_id=data['owner_id'],
            status='open'
        )
        
        db.session.add(deal)
        db.session.flush()  # Get deal.id
        
        # Create activity
        PipelineService._create_activity(
            workspace_id=workspace_id,
            deal_id=deal.id,
            user_id=data['owner_id'],
            activity_type='system',
            subject=f'Deal created: {deal.name}',
            body=f'Deal created in stage "{first_stage.name}" with value ${deal.value}'
        )
        
        db.session.commit()
        logger.info(f"Created deal {deal.id}: {deal.name}")

        PipelineService._emit_webhook_event(workspace_id, 'deal.created', {
            'deal_id': deal.id,
            'name': deal.name,
            'company_id': deal.company_id,
            'pipeline_id': deal.pipeline_id,
            'stage_id': deal.stage_id,
            'value': float(deal.value),
            'status': deal.status,
            'updated_at': deal.updated_at.isoformat() if deal.updated_at else None,
        })
        
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
        
        # Track changes for activity log
        changes = {}
        
        # Update fields
        for field in ['name', 'value', 'expected_close_date', 'owner_id']:
            if field in data and getattr(deal, field) != data[field]:
                old_value = getattr(deal, field)
                setattr(deal, field, data[field])
                changes[field] = {'old': old_value, 'new': data[field]}
        
        if changes:
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
            
            db.session.commit()
            logger.info(f"Updated deal {deal.id}: {changes}")

            PipelineService._emit_webhook_event(workspace_id, 'deal.updated', {
                'deal_id': deal.id,
                'name': deal.name,
                'company_id': deal.company_id,
                'pipeline_id': deal.pipeline_id,
                'stage_id': deal.stage_id,
                'value': float(deal.value),
                'status': deal.status,
                'changes': changes,
                'updated_at': deal.updated_at.isoformat() if deal.updated_at else None,
            })
        
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
        deal.stage_id = stage_id
        deal.updated_at = datetime.utcnow()
        
        # Create activity
        PipelineService._create_activity(
            workspace_id=workspace_id,
            deal_id=deal.id,
            user_id=user_id,
            activity_type='system',
            subject=f'Deal moved: {deal.name}',
            body=f'Stage changed from "{old_stage.name}" to "{new_stage.name}"'
        )
        
        # Commit with retry mechanism for SQLite lock handling
        max_retries = 3
        retry_delay = 0.1  # Start with 100ms
        
        for attempt in range(max_retries):
            try:
                db.session.commit()
                logger.info(f"Moved deal {deal.id} from stage {old_stage.id} to {stage_id}")
                break  # Success, exit retry loop
            except Exception as e:
                if attempt < max_retries - 1 and 'database is locked' in str(e).lower():
                    logger.warning(f"Database locked, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    # Final attempt failed or different error
                    db.session.rollback()
                    logger.error(f"Failed to commit deal move after {attempt + 1} attempts: {e}")
                    raise

        PipelineService._emit_webhook_event(workspace_id, 'deal.updated', {
            'deal_id': deal.id,
            'name': deal.name,
            'company_id': deal.company_id,
            'pipeline_id': deal.pipeline_id,
            'stage_id': deal.stage_id,
            'status': deal.status,
            'change_type': 'stage_move',
            'previous_stage_id': old_stage.id,
            'new_stage_id': stage_id,
            'updated_at': deal.updated_at.isoformat() if deal.updated_at else None,
        })
        
        return deal
    
    @staticmethod
    def close_deal(workspace_id: int, deal_id: int, status: str, win_loss_reason: str, user_id: int) -> Deal:
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
        if status not in ['won', 'lost']:
            raise ValueError(f"Invalid status: {status}. Must be 'won' or 'lost'")
        
        if not win_loss_reason or not win_loss_reason.strip():
            raise ValueError("Win/loss reason is required when closing a deal")
        
        deal = Deal.query.filter_by(
            id=deal_id,
            workspace_id=workspace_id,
            is_deleted=False,
        ).first()
        
        if not deal:
            raise ValueError(f"Deal {deal_id} not found")
        
        deal.status = status
        deal.win_loss_reason = win_loss_reason
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

        PipelineService._emit_webhook_event(workspace_id, 'deal.updated', {
            'deal_id': deal.id,
            'name': deal.name,
            'company_id': deal.company_id,
            'pipeline_id': deal.pipeline_id,
            'stage_id': deal.stage_id,
            'status': deal.status,
            'win_loss_reason': deal.win_loss_reason,
            'closed_at': deal.closed_at.isoformat() if deal.closed_at else None,
            'updated_at': deal.updated_at.isoformat() if deal.updated_at else None,
        })
        
        return deal
    
    @staticmethod
    def get_deals(workspace_id: int, filters: Optional[Dict[str, Any]] = None) -> List[Deal]:
        """
        Get deals with optional filters.
        
        Args:
            workspace_id: Workspace ID
            filters: Optional filters (stage_id, owner_id, status, company_id)
        
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
            if 'pipeline_id' in filters:
                query = query.filter_by(pipeline_id=filters['pipeline_id'])
        
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
            'by_stage': by_stage
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
        return activity
