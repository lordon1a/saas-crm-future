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
                pipeline_id=data['pipeline_id'],
                stage_id=stage_id,
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
        
        # Track changes for activity log
        changes = {}
        
        # Update fields
        for field in ['name', 'value', 'expected_close_date', 'owner_id']:
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
            import eventlet
            eventlet.spawn_n(
                PipelineService._emit_webhook_event,
                workspace_id,
                'deal.updated',
                {
                    'deal_id': deal.id,
                    'name': deal.name,
                    'company_id': deal.company_id,
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
        
        try:
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
                'pipeline_id': deal.pipeline_id,
                'stage_id': deal.stage_id,
                'status': deal.status,
                'win_loss_reason': deal.win_loss_reason,
                'closed_at': deal.closed_at.isoformat() if deal.closed_at else None,
                'updated_at': deal.updated_at.isoformat() if deal.updated_at else None,
            })
        except Exception as webhook_error:
            logger.warning(f"Webhook dispatch failed (non-blocking): {webhook_error}")
        
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
