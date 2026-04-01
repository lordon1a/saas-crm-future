"""
Pipeline API Routes
API endpoints for pipeline and deal management
"""
from flask import Blueprint, request, jsonify, session
from models import db
from models_crm import Pipeline, DealStage, Deal, Company, Contact, DealLineItem, Quote, Product, WinLossReason
from services.pipeline_service import PipelineService
from services.deal_contact_service import DealContactService
from services.pipeline_advanced_service import PipelineAdvancedService
from services.quickbooks_service import QuickBooksService
from services.collaboration_service import CollaborationService
from functools import wraps
from datetime import datetime, date
from sqlalchemy.orm import joinedload
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('pipeline', __name__, url_prefix='/api/v1')


def login_required_api(f):
    """Decorator to require authentication for API endpoints"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'error': 'Unauthorized'}), 401
        if not session.get('workspace_id'):
            return jsonify({'error': 'Workspace context missing'}), 401
        return f(*args, **kwargs)
    return decorated


# ═══ PIPELINES ═══

@bp.route('/pipelines', methods=['GET'])
@login_required_api
def get_pipelines():
    """Get all pipelines for the workspace"""
    workspace_id = session.get('workspace_id')
    
    try:
        # Eager load stages to avoid lazy loading issues
        pipelines = Pipeline.query.filter_by(workspace_id=workspace_id).options(
            joinedload(Pipeline.stages)
        ).all()
        
        result = []
        for pipeline in pipelines:
            try:
                result.append({
                    'id': pipeline.id,
                    'name': pipeline.name,
                    'is_default': pipeline.is_default,
                    'stages': [{
                        'id': stage.id,
                        'name': stage.name,
                        'order': stage.order,
                        'probability': stage.probability,
                        'rotting_days': stage.rotting_days
                    } for stage in sorted(pipeline.stages, key=lambda s: s.order) if stage.is_active],
                    'created_at': pipeline.created_at.isoformat()
                })
            except Exception as e:
                logger.error(f"Error processing pipeline {pipeline.id}: {e}")
                continue
        
        return jsonify(result), 200
    except Exception as e:
        import traceback
        logger.error(f"Error getting pipelines: {e}")
        logger.error(traceback.format_exc())
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@bp.route('/pipelines/<int:pipeline_id>', methods=['GET'])
@login_required_api
def get_pipeline(pipeline_id):
    """Get a specific pipeline with its stages"""
    workspace_id = session.get('workspace_id')
    pipeline = PipelineService.get_pipeline_with_stages(workspace_id, pipeline_id)
    
    if not pipeline:
        return jsonify({'error': 'Pipeline not found'}), 404
    
    return jsonify({
        'id': pipeline.id,
        'name': pipeline.name,
        'is_default': pipeline.is_default,
        'stages': [{
            'id': stage.id,
            'name': stage.name,
            'order': stage.order,
            'probability': stage.probability,
            'rotting_days': stage.rotting_days
        } for stage in pipeline.stages if stage.is_active],
        'created_at': pipeline.created_at.isoformat()
    }), 200


@bp.route('/pipeline/stages', methods=['GET'])
@login_required_api
def get_pipeline_stages_compat():
    """Compatibility endpoint for workflow builder clients."""
    workspace_id = session.get('workspace_id')

    try:
        pipeline = Pipeline.query.filter_by(workspace_id=workspace_id, is_default=True).first()
        if not pipeline:
            return jsonify({'error': 'Pipeline not found'}), 404

        stages = DealStage.query.filter_by(
            pipeline_id=pipeline.id,
            is_active=True
        ).order_by(DealStage.order).all()

        return jsonify({
            'pipeline_id': pipeline.id,
            'pipeline_name': pipeline.name,
            'stages': [{
                'id': stage.id,
                'name': stage.name,
                'probability': stage.probability,
                'rotting_days': stage.rotting_days,
                'order': stage.order,
                'is_active': stage.is_active,
            } for stage in stages]
        }), 200
    except Exception as e:
        logger.error(f"Error fetching pipeline stages compatibility endpoint: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


# ═══ DEALS ═══

@bp.route('/deals', methods=['GET'])
@login_required_api
def get_deals():
    """
    Get deals with optional filters and pagination.
    Query params: stage_id, owner_id, status, company_id, contact_id, pipeline_id, page, per_page
    """
    workspace_id = session.get('workspace_id')
    
    try:
        # Pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        per_page = min(per_page, 100)  # Max 100 items per page
        
        # Build filters from query params
        filters = {}
        if request.args.get('stage_id'):
            try:
                filters['stage_id'] = int(request.args.get('stage_id'))
            except (TypeError, ValueError):
                return jsonify({'error': 'Geçersiz parametre formatı, tamsayı bekleniyor.'}), 400
        if request.args.get('owner_id'):
            try:
                filters['owner_id'] = int(request.args.get('owner_id'))
            except (TypeError, ValueError):
                return jsonify({'error': 'Geçersiz parametre formatı, tamsayı bekleniyor.'}), 400
        if request.args.get('status'):
            filters['status'] = request.args.get('status')
        if request.args.get('company_id'):
            try:
                filters['company_id'] = int(request.args.get('company_id'))
            except (TypeError, ValueError):
                return jsonify({'error': 'Geçersiz parametre formatı, tamsayı bekleniyor.'}), 400
        if request.args.get('contact_id'):
            try:
                filters['contact_id'] = int(request.args.get('contact_id'))
            except (TypeError, ValueError):
                return jsonify({'error': 'Geçersiz parametre formatı, tamsayı bekleniyor.'}), 400
        if request.args.get('pipeline_id'):
            try:
                filters['pipeline_id'] = int(request.args.get('pipeline_id'))
            except (TypeError, ValueError):
                return jsonify({'error': 'Geçersiz parametre formatı, tamsayı bekleniyor.'}), 400
        if request.args.get('forecast_category'):
            filters['forecast_category'] = request.args.get('forecast_category')
        if request.args.get('revenue_type'):
            filters['revenue_type'] = request.args.get('revenue_type')
        if request.args.get('churn_risk'):
            filters['churn_risk'] = request.args.get('churn_risk')
        
        # Build query
        query = Deal.query.filter_by(workspace_id=workspace_id, is_deleted=False)
        
        # Apply filters
        if filters.get('stage_id'):
            query = query.filter_by(stage_id=filters['stage_id'])
        if filters.get('owner_id'):
            query = query.filter_by(owner_id=filters['owner_id'])
        if filters.get('status'):
            query = query.filter_by(status=filters['status'])
        if filters.get('company_id'):
            query = query.filter_by(company_id=filters['company_id'])
        if filters.get('contact_id'):
            contact_filter = Contact.query.filter_by(
                id=filters['contact_id'],
                workspace_id=workspace_id,
                is_deleted=False,
            ).first()
            if not contact_filter:
                return jsonify({'error': 'Contact not found'}), 404

            if contact_filter.company_id:
                # Backward-compatible behavior:
                # include legacy deals without contact_id that were linked by company only.
                query = query.filter(
                    db.or_(
                        Deal.contact_id == filters['contact_id'],
                        db.and_(
                            Deal.contact_id.is_(None),
                            Deal.company_id == contact_filter.company_id
                        )
                    )
                )
            else:
                query = query.filter(Deal.contact_id == filters['contact_id'])
        if filters.get('pipeline_id'):
            query = query.filter_by(pipeline_id=filters['pipeline_id'])
        if filters.get('forecast_category'):
            query = query.filter_by(forecast_category=filters['forecast_category'])
        if filters.get('revenue_type'):
            query = query.filter_by(revenue_type=filters['revenue_type'])
        if filters.get('churn_risk'):
            query = query.filter_by(churn_risk=filters['churn_risk'])
        
        # Eager load relationships
        query = query.options(
            joinedload(Deal.company),
            joinedload(Deal.primary_contact),
            joinedload(Deal.pipeline),
            joinedload(Deal.stage)
        )
        
        # Paginate
        pagination = query.order_by(Deal.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        result = []
        for deal in pagination.items:
            committee = DealContactService.calculate_committee_score(workspace_id, deal.id)
            result.append({
                'id': deal.id,
                'name': deal.name,
                'company': {
                    'id': deal.company.id,
                    'name': deal.company.name
                } if deal.company else None,
                'contact_id': deal.contact_id,
                'contact': {
                    'id': deal.primary_contact.id,
                    'full_name': deal.primary_contact.full_name,
                    'email': deal.primary_contact.email,
                    'phone': deal.primary_contact.phone
                } if deal.primary_contact else None,
                'pipeline_id': deal.pipeline_id,
                'pipeline_name': deal.pipeline.name,
                'stage': {
                    'id': deal.stage.id,
                    'name': deal.stage.name,
                    'order': deal.stage.order,
                    'probability': deal.stage.probability
                },
                'value': float(deal.value),
                'revenue_type': deal.revenue_type,
                'mrr': float(deal.mrr or 0),
                'arr': float(deal.arr or 0),
                'renewal_date': deal.renewal_date.isoformat() if deal.renewal_date else None,
                'churn_risk': deal.churn_risk,
                'expected_close_date': deal.expected_close_date.isoformat() if deal.expected_close_date else None,
                'owner_id': deal.owner_id,
                'next_step': deal.next_step,
                'next_step_due_at': deal.next_step_due_at.isoformat() if deal.next_step_due_at else None,
                'last_activity_at': deal.last_activity_at.isoformat() if deal.last_activity_at else None,
                'forecast_category': deal.forecast_category,
                'status': deal.status,
                'win_loss_reason_id': deal.win_loss_reason_id,
                'win_loss_reason': deal.win_loss_reason,
                'committee_score': committee['committee_score'],
                'committee_member_count': committee['member_count'],
                'committee_strength': committee['strength'],
                'created_at': deal.created_at.isoformat(),
                'updated_at': deal.updated_at.isoformat() if deal.updated_at else None,
                'closed_at': deal.closed_at.isoformat() if deal.closed_at else None,
                'stage_entered_at': deal.stage_entered_at.isoformat() if deal.stage_entered_at else None,
                'days_in_stage': deal.days_in_current_stage(),
                'is_rotting': deal.is_rotting()
            })
        
        return jsonify({
            'deals': result,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        }), 200
    except Exception as e:
        import traceback
        logger.error(f"Error getting deals: {e}")
        logger.error(traceback.format_exc())
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@bp.route('/deals/<int:deal_id>', methods=['GET'])
@login_required_api
def get_deal(deal_id):
    """Get a specific deal"""
    from utils.permissions import check_entity_access, get_current_user_from_session
    
    workspace_id = session.get('workspace_id')
    user = get_current_user_from_session()
    
    deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id, is_deleted=False).first()
    
    if not deal:
        return jsonify({'error': 'Deal not found'}), 404
    
    # SECURITY: Check entity access (IDOR protection)
    if not check_entity_access(user, deal, 'read'):
        logger.warning(f"Access denied: user {user.id} attempted to read deal {deal_id}")
        return jsonify({'error': 'Access denied to this deal'}), 403
    
    committee = DealContactService.calculate_committee_score(workspace_id, deal_id)

    return jsonify({
        'id': deal.id,
        'name': deal.name,
        'company': {
            'id': deal.company.id,
            'name': deal.company.name
        } if deal.company else None,
        'contact_id': deal.contact_id,
        'contact': {
            'id': deal.primary_contact.id,
            'full_name': deal.primary_contact.full_name,
            'email': deal.primary_contact.email,
            'phone': deal.primary_contact.phone
        } if deal.primary_contact else None,
        'pipeline_id': deal.pipeline_id,
        'pipeline_name': deal.pipeline.name,
        'stage': {
            'id': deal.stage.id,
            'name': deal.stage.name,
            'order': deal.stage.order,
            'probability': deal.stage.probability
        },
        'value': float(deal.value),
        'revenue_type': deal.revenue_type,
        'mrr': float(deal.mrr or 0),
        'arr': float(deal.arr or 0),
        'renewal_date': deal.renewal_date.isoformat() if deal.renewal_date else None,
        'churn_risk': deal.churn_risk,
        'expected_close_date': deal.expected_close_date.isoformat() if deal.expected_close_date else None,
        'owner_id': deal.owner_id,
        'next_step': deal.next_step,
        'next_step_due_at': deal.next_step_due_at.isoformat() if deal.next_step_due_at else None,
        'last_activity_at': deal.last_activity_at.isoformat() if deal.last_activity_at else None,
        'forecast_category': deal.forecast_category,
        'status': deal.status,
        'win_loss_reason_id': deal.win_loss_reason_id,
        'win_loss_reason': deal.win_loss_reason,
        'committee_score': committee['committee_score'],
        'committee_member_count': committee['member_count'],
        'committee_strength': committee['strength'],
        'created_at': deal.created_at.isoformat(),
        'updated_at': deal.updated_at.isoformat() if deal.updated_at else None,
        'closed_at': deal.closed_at.isoformat() if deal.closed_at else None
    }), 200


@bp.route('/deals', methods=['POST'])
@login_required_api
def create_deal():
    """
    Create a new deal.
    Required: name, pipeline_id
    Optional: contact_id, company_id, value, expected_close_date, stage_id
    
    If contact_id is provided but company_id is not:
    - If contact is a CRM Contact with company, use that company
    - If contact is a Customer (Telegram/WhatsApp), create a company from customer data
    """
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json() or {}
    
    try:
        # Parse expected_close_date if provided
        if 'expected_close_date' in data and data['expected_close_date']:
            data['expected_close_date'] = datetime.fromisoformat(data['expected_close_date']).date()
        if 'renewal_date' in data and data['renewal_date']:
            data['renewal_date'] = datetime.fromisoformat(data['renewal_date']).date()
        if 'next_step_due_at' in data and data['next_step_due_at']:
            data['next_step_due_at'] = datetime.fromisoformat(data['next_step_due_at'])
        
        # Set owner_id to current user if not provided
        if 'owner_id' not in data:
            data['owner_id'] = user_id
        
        # Handle contact_id -> company_id resolution
        if 'contact_id' in data and not data.get('company_id'):
            from models_crm import Contact, Company
            from models import Customer
            
            contact_id = data['contact_id']
            
            # Try to find CRM Contact first
            crm_contact = Contact.query.filter_by(
                id=contact_id,
                workspace_id=workspace_id,
                is_deleted=False
            ).first()
            
            if crm_contact:
                # CRM Contact found
                if crm_contact.company_id:
                    data['company_id'] = crm_contact.company_id
                    data['contact_id'] = crm_contact.id
                else:
                    # Create a company for this contact
                    try:
                        company_name = f"{crm_contact.full_name}'s Company"
                        company = Company(
                            workspace_id=workspace_id,
                            name=company_name,
                            phone=crm_contact.phone or crm_contact.whatsapp_phone
                        )
                        db.session.add(company)
                        db.session.commit()
                        
                        # Link contact to company
                        crm_contact.company_id = company.id
                        db.session.commit()
                        
                        data['company_id'] = company.id
                        data['contact_id'] = crm_contact.id
                        logger.info(f"Created company {company.id} for contact {crm_contact.id}")
                    except Exception as e:
                        db.session.rollback()
                        logger.error(f"Error creating company for contact: {e}")
                        raise ValueError(f"Failed to create company for contact")
            else:
                # Try to find Customer (Telegram/WhatsApp user)
                customer = Customer.query.filter_by(
                    id=contact_id,
                    workspace_id=workspace_id
                ).first()
                
                if customer:
                    try:
                        # Create company from customer data
                        company_name = customer.company or f"{customer.profile_name or 'Unknown'}'s Company"
                        company = Company(
                            workspace_id=workspace_id,
                            name=company_name,
                            phone=customer.phone_number
                        )
                        db.session.add(company)
                        db.session.commit()
                        
                        # Create CRM Contact from Customer
                        crm_contact = Contact(
                            workspace_id=workspace_id,
                            company_id=company.id,
                            customer_id=customer.id,
                            first_name=customer.profile_name or 'Unknown',
                            last_name='',
                            phone=customer.phone_number,
                            whatsapp_phone=customer.phone_number,
                            email=customer.email,
                            job_title=customer.job_title
                        )
                        db.session.add(crm_contact)
                        db.session.commit()
                        
                        data['company_id'] = company.id
                        data['contact_id'] = crm_contact.id
                        logger.info(f"Created CRM Contact {crm_contact.id} and Company {company.id} from Customer {customer.id}")
                    except Exception as e:
                        db.session.rollback()
                        logger.error(f"Error creating company/contact from customer: {e}")
                        raise ValueError(f"Failed to create company from customer data")
                else:
                    raise ValueError(f"Contact {contact_id} not found")
        
        # Validate company_id is set
        if not data.get('company_id'):
            raise ValueError("company_id is required or could not be determined from contact_id")
        
        deal = PipelineService.create_deal(workspace_id, data)
        
        # Mark onboarding step as complete
        from services.onboarding_service import OnboardingService
        OnboardingService.complete_step(workspace_id, 'first_deal_created')
        
        # Trigger workflow automation for deal_created
        try:
            from services.workflow_service import WorkflowService
            WorkflowService.trigger_event(
                workspace_id=workspace_id,
                trigger_type='deal_created',
                entity_type='deal',
                entity_id=deal.id
            )
        except Exception as e:
            logger.error(f"Workflow trigger error for deal_created: {e}")
        
        return jsonify({
            'id': deal.id,
            'name': deal.name,
            'company_id': deal.company_id,
            'contact_id': deal.contact_id,
            'pipeline_id': deal.pipeline_id,
            'stage_id': deal.stage_id,
            'value': float(deal.value),
            'revenue_type': deal.revenue_type,
            'mrr': float(deal.mrr or 0),
            'arr': float(deal.arr or 0),
            'renewal_date': deal.renewal_date.isoformat() if deal.renewal_date else None,
            'churn_risk': deal.churn_risk,
            'expected_close_date': deal.expected_close_date.isoformat() if deal.expected_close_date else None,
            'owner_id': deal.owner_id,
            'next_step': deal.next_step,
            'next_step_due_at': deal.next_step_due_at.isoformat() if deal.next_step_due_at else None,
            'forecast_category': deal.forecast_category,
            'status': deal.status,
            'created_at': deal.created_at.isoformat()
        }), 201
    
    except ValueError as e:
        logger.error(f"Error creating deal: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        import traceback
        logger.error(f"Unexpected error creating deal: {e}")
        logger.error(traceback.format_exc())
        print(traceback.format_exc())
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/deals/<int:deal_id>', methods=['PATCH'])
@login_required_api
def update_deal(deal_id):
    """
    Update a deal.
    Allowed fields: name, value, expected_close_date, owner_id, contact_id
    """
    from utils.permissions import check_entity_access, get_current_user_from_session
    
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    user = get_current_user_from_session()
    data = request.get_json() or {}
    
    try:
        # Parse expected_close_date if provided
        if 'expected_close_date' in data and data['expected_close_date']:
            data['expected_close_date'] = datetime.fromisoformat(data['expected_close_date']).date()
        if 'renewal_date' in data and data['renewal_date']:
            data['renewal_date'] = datetime.fromisoformat(data['renewal_date']).date()
        if 'next_step_due_at' in data and data['next_step_due_at']:
            data['next_step_due_at'] = datetime.fromisoformat(data['next_step_due_at'])
        
        # Get deal
        deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id, is_deleted=False).first()
        
        if not deal:
            return jsonify({'error': 'Deal not found'}), 404
        
        # SECURITY: Check entity access (IDOR protection)
        if not check_entity_access(user, deal, 'write'):
            logger.warning(f"Access denied: user {user.id} attempted to update deal {deal_id}")
            return jsonify({'error': 'Access denied to this deal'}), 403
        
        # Update deal
        deal = PipelineService.update_deal(workspace_id, deal_id, data, user_id)
        
        # Prepare response data before async operations
        response_data = {
            'id': deal.id,
            'name': deal.name,
            'value': float(deal.value),
            'revenue_type': deal.revenue_type,
            'mrr': float(deal.mrr or 0),
            'arr': float(deal.arr or 0),
            'renewal_date': deal.renewal_date.isoformat() if deal.renewal_date else None,
            'churn_risk': deal.churn_risk,
            'expected_close_date': deal.expected_close_date.isoformat() if deal.expected_close_date else None,
            'owner_id': deal.owner_id,
            'contact_id': deal.contact_id,
            'next_step': deal.next_step,
            'next_step_due_at': deal.next_step_due_at.isoformat() if deal.next_step_due_at else None,
            'forecast_category': deal.forecast_category,
            'updated_at': deal.updated_at.isoformat()
        }

        # Notify followers AFTER commit (asenkron spawn - response'u bloklamaz)
        try:
            import gevent
            gevent.spawn(
                CollaborationService.notify_followers_on_entity_change,
                workspace_id=workspace_id,
                entity_type='deal',
                entity_id=deal.id,
                message=f'Takip ettiginiz deal guncellendi: {deal.name}',
            )
        except Exception as notify_error:
            logger.warning(f"Failed to spawn follower notification: {notify_error}")

        # Trigger deal_amount_changed workflow if value was updated
        if 'value' in data:
            try:
                from services.workflow_service import WorkflowService
                WorkflowService.trigger_event(
                    workspace_id=workspace_id,
                    trigger_type='deal_amount_changed',
                    entity_type='deal',
                    entity_id=deal.id,
                    context={'new_value': float(deal.value)}
                )
            except Exception as e:
                logger.error(f"Workflow trigger error for deal_amount_changed: {e}")

        return jsonify(response_data), 200
    
    except ValueError as e:
        logger.error(f"Error updating deal: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error updating deal: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/<int:deal_id>/stage', methods=['PATCH'])
@login_required_api
def move_deal_stage(deal_id):
    """
    Move a deal to a different stage.
    Required: stage_id
    """
    from utils.permissions import check_entity_access, get_current_user_from_session
    
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    user = get_current_user_from_session()
    data = request.get_json()
    
    if 'stage_id' not in data:
        return jsonify({'error': 'stage_id is required'}), 400
    
    try:
        # Get deal
        deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id, is_deleted=False).first()
        
        if not deal:
            return jsonify({'error': 'Deal not found'}), 404
        
        # SECURITY: Check entity access (IDOR protection)
        if not check_entity_access(user, deal, 'write'):
            logger.warning(f"Access denied: user {user.id} attempted to move deal {deal_id} stage")
            return jsonify({'error': 'Access denied to this deal'}), 403
        
        # Store old stage_id for workflow trigger
        old_stage_id = deal.stage_id
        new_stage_id = data['stage_id']
        
        # Move stage
        # Note: Workflow trigger for deal_stage_changed is handled asynchronously
        # in PipelineService.move_deal_to_stage() via gevent spawn
        deal = PipelineService.move_deal_to_stage(
            workspace_id, 
            deal_id, 
            data['stage_id'], 
            user_id
        )
        
        # Prepare response data before async operations
        response_data = {
            'id': deal.id,
            'stage_id': deal.stage_id,
            'stage_name': deal.stage.name,
            'updated_at': deal.updated_at.isoformat()
        }

        # Notify followers AFTER commit (asenkron spawn - response'u bloklamaz)
        try:
            import gevent
            gevent.spawn(
                CollaborationService.notify_followers_on_entity_change,
                workspace_id=workspace_id,
                entity_type='deal',
                entity_id=deal.id,
                message=f'Deal asamasi degisti: {deal.name} -> {deal.stage.name}',
            )
        except Exception as notify_error:
            logger.warning(f"Failed to spawn follower notification: {notify_error}")
        
        return jsonify(response_data), 200
    
    except ValueError as e:
        logger.error(f"Error moving deal stage: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error moving deal stage: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/<int:deal_id>/contacts', methods=['GET'])
@login_required_api
def list_deal_contacts(deal_id):
    """List stakeholders for a deal."""
    from utils.permissions import check_entity_access, get_current_user_from_session

    workspace_id = session.get('workspace_id')
    user = get_current_user_from_session()
    deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id, is_deleted=False).first()
    if not deal:
        return jsonify({'error': 'Deal not found'}), 404
    if not check_entity_access(user, deal, 'read'):
        logger.warning(f"Access denied: user {user.id} attempted to list stakeholders for deal {deal_id}")
        return jsonify({'error': 'Access denied to this deal'}), 403

    try:
        stakeholders = DealContactService.list_stakeholders(workspace_id, deal_id)
        committee = DealContactService.calculate_committee_score(workspace_id, deal_id)
        return jsonify({
            'deal_id': deal_id,
            'stakeholders': stakeholders,
            'committee': committee,
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error listing deal stakeholders: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/<int:deal_id>/contacts', methods=['POST'])
@login_required_api
def add_deal_contact(deal_id):
    """Add or upsert a stakeholder for a deal."""
    from utils.permissions import check_entity_access, get_current_user_from_session

    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    user = get_current_user_from_session()
    data = request.get_json() or {}

    contact_id = data.get('contact_id')
    if not contact_id:
        return jsonify({'error': 'contact_id is required'}), 400

    deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id, is_deleted=False).first()
    if not deal:
        return jsonify({'error': 'Deal not found'}), 404
    if not check_entity_access(user, deal, 'write'):
        logger.warning(f"Access denied: user {user.id} attempted to add stakeholder for deal {deal_id}")
        return jsonify({'error': 'Access denied to this deal'}), 403

    try:
        contact_id = int(contact_id)
    except (TypeError, ValueError):
        return jsonify({'error': 'contact_id must be an integer'}), 400

    try:
        link = DealContactService.add_stakeholder(
            workspace_id=workspace_id,
            deal_id=deal_id,
            contact_id=contact_id,
            user_id=user_id,
            role=data.get('role'),
            is_primary=data.get('is_primary') if 'is_primary' in data else None,
            influence_score=data.get('influence_score') if 'influence_score' in data else None,
            decision_weight=data.get('decision_weight') if 'decision_weight' in data else None,
        )
        committee = DealContactService.calculate_committee_score(workspace_id, deal_id)
        return jsonify({
            'deal_id': deal_id,
            'contact_id': link.contact_id,
            'role': link.role,
            'is_primary': bool(link.is_primary),
            'influence_score': link.influence_score,
            'decision_weight': link.decision_weight,
            'committee': committee,
            'created_at': link.created_at.isoformat() if link.created_at else None,
            'updated_at': link.updated_at.isoformat() if link.updated_at else None,
        }), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error adding stakeholder to deal: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/<int:deal_id>/contacts/<int:contact_id>', methods=['PATCH'])
@login_required_api
def update_deal_contact(deal_id, contact_id):
    """Update stakeholder metadata on a deal."""
    from utils.permissions import check_entity_access, get_current_user_from_session

    workspace_id = session.get('workspace_id')
    user = get_current_user_from_session()
    data = request.get_json() or {}

    deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id, is_deleted=False).first()
    if not deal:
        return jsonify({'error': 'Deal not found'}), 404
    if not check_entity_access(user, deal, 'write'):
        logger.warning(f"Access denied: user {user.id} attempted to update stakeholder for deal {deal_id}")
        return jsonify({'error': 'Access denied to this deal'}), 403

    if 'role' not in data and 'is_primary' not in data and 'influence_score' not in data and 'decision_weight' not in data:
        return jsonify({'error': 'At least one field is required: role, is_primary, influence_score, or decision_weight'}), 400

    try:
        link = DealContactService.update_stakeholder(
            workspace_id=workspace_id,
            deal_id=deal_id,
            contact_id=contact_id,
            role=data.get('role') if 'role' in data else None,
            is_primary=data.get('is_primary') if 'is_primary' in data else None,
            influence_score=data.get('influence_score') if 'influence_score' in data else None,
            decision_weight=data.get('decision_weight') if 'decision_weight' in data else None,
        )
        committee = DealContactService.calculate_committee_score(workspace_id, deal_id)
        return jsonify({
            'deal_id': deal_id,
            'contact_id': link.contact_id,
            'role': link.role,
            'is_primary': bool(link.is_primary),
            'influence_score': link.influence_score,
            'decision_weight': link.decision_weight,
            'committee': committee,
            'updated_at': link.updated_at.isoformat() if link.updated_at else None,
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating stakeholder on deal: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/<int:deal_id>/contacts/<int:contact_id>', methods=['DELETE'])
@login_required_api
def remove_deal_contact(deal_id, contact_id):
    """Remove stakeholder from a deal."""
    from utils.permissions import check_entity_access, get_current_user_from_session

    workspace_id = session.get('workspace_id')
    user = get_current_user_from_session()
    deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id, is_deleted=False).first()
    if not deal:
        return jsonify({'error': 'Deal not found'}), 404
    if not check_entity_access(user, deal, 'write'):
        logger.warning(f"Access denied: user {user.id} attempted to remove stakeholder for deal {deal_id}")
        return jsonify({'error': 'Access denied to this deal'}), 403

    try:
        DealContactService.remove_stakeholder(workspace_id, deal_id, contact_id)
        committee = DealContactService.calculate_committee_score(workspace_id, deal_id)
        return jsonify({'message': 'Stakeholder removed', 'committee': committee}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error removing stakeholder from deal: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/<int:deal_id>/close', methods=['POST'])
@login_required_api
def close_deal(deal_id):
    """
    Close a deal as won or lost.
    Required: status ('won' or 'lost'), win_loss_reason_id
    """
    from utils.permissions import check_entity_access, get_current_user_from_session
    
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    user = get_current_user_from_session()
    data = request.get_json() or {}
    
    if 'status' not in data:
        return jsonify({'error': 'status is required'}), 400
    if 'win_loss_reason_id' not in data:
        return jsonify({'error': 'win_loss_reason_id is required'}), 400
    
    try:
        # Get deal
        deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id, is_deleted=False).first()
        
        if not deal:
            return jsonify({'error': 'Deal not found'}), 404
        
        # SECURITY: Check entity access (IDOR protection)
        if not check_entity_access(user, deal, 'write'):
            logger.warning(f"Access denied: user {user.id} attempted to close deal {deal_id}")
            return jsonify({'error': 'Access denied to this deal'}), 403
        
        # Store old status for workflow trigger
        old_status = deal.status
        new_status = data['status']
        
        # Close deal
        # Note: Workflow trigger for deal_won/deal_lost is handled asynchronously
        # in PipelineService.close_deal() via gevent spawn
        deal = PipelineService.close_deal(
            workspace_id,
            deal_id,
            data['status'],
            data.get('win_loss_reason'),
            user_id,
            data.get('win_loss_reason_id')
        )
        
        # Prepare response data before async operations
        response_data = {
            'id': deal.id,
            'status': deal.status,
            'win_loss_reason_id': deal.win_loss_reason_id,
            'win_loss_reason': deal.win_loss_reason,
            'closed_at': deal.closed_at.isoformat(),
            'updated_at': deal.updated_at.isoformat()
        }

        # QuickBooks invoice creation AFTER commit (asenkron spawn - response'u bloklamaz)
        if deal.status == 'won':
            try:
                import gevent
                gevent.spawn(
                    QuickBooksService.create_invoice_for_deal,
                    workspace_id,
                    user_id,
                    deal.id
                )
            except Exception as exc:
                logger.warning('QuickBooks invoice spawn failed for deal %s: %s', deal.id, exc)

            try:
                from services.ads_sync_service import GoogleAdsService
                import gevent
                gevent.spawn(
                    GoogleAdsService.send_conversion,
                    workspace_id,
                    deal.id,
                    float(deal.value or 0),
                )
            except Exception as exc:
                logger.warning('Google Ads conversion spawn failed for deal %s: %s', deal.id, exc)

        # Notify followers AFTER commit (asenkron spawn - response'u bloklamaz)
        try:
            import gevent
            gevent.spawn(
                CollaborationService.notify_followers_on_entity_change,
                workspace_id=workspace_id,
                entity_type='deal',
                entity_id=deal.id,
                message=f'Deal kapatildi: {deal.name} ({deal.status})',
            )
        except Exception as notify_error:
            logger.warning(f"Failed to spawn follower notification: {notify_error}")
        
        return jsonify(response_data), 200
    
    except ValueError as e:
        logger.error(f"Error closing deal: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error closing deal: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/<int:deal_id>/reopen', methods=['POST'])
@login_required_api
def reopen_deal(deal_id):
    """Reopen a won/lost deal back to open."""
    from utils.permissions import check_entity_access, get_current_user_from_session

    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    user = get_current_user_from_session()

    deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id, is_deleted=False).first()
    if not deal:
        return jsonify({'error': 'Deal not found'}), 404
    if not check_entity_access(user, deal, 'write'):
        logger.warning(f"Access denied: user {user.id} attempted to reopen deal {deal_id}")
        return jsonify({'error': 'Access denied to this deal'}), 403

    try:
        reopened = PipelineService.reopen_deal(workspace_id, deal_id, user_id)
        return jsonify({
            'id': reopened.id,
            'status': reopened.status,
            'win_loss_reason_id': reopened.win_loss_reason_id,
            'win_loss_reason': reopened.win_loss_reason,
            'closed_at': reopened.closed_at.isoformat() if reopened.closed_at else None,
            'updated_at': reopened.updated_at.isoformat() if reopened.updated_at else None,
            'message': 'Deal yeniden açıldı'
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error reopening deal: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/deleted', methods=['GET'])
@login_required_api
def list_deleted_deals():
    """List deals in recycle bin."""
    workspace_id = session.get('workspace_id')
    limit = request.args.get('limit', 100, type=int)

    try:
        deleted_deals = PipelineService.list_deleted_deals(workspace_id, limit=limit)
        return jsonify({
            'deals': [{
                'id': deal.id,
                'name': deal.name,
                'value': float(deal.value or 0),
                'status': deal.status,
                'company': {
                    'id': deal.company.id,
                    'name': deal.company.name
                } if deal.company else None,
                'deleted_at': deal.deleted_at.isoformat() if deal.deleted_at else None,
                'updated_at': deal.updated_at.isoformat() if deal.updated_at else None,
                'closed_at': deal.closed_at.isoformat() if deal.closed_at else None,
            } for deal in deleted_deals]
        }), 200
    except Exception as e:
        logger.error(f"Error listing deleted deals: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/<int:deal_id>/trash', methods=['POST'])
@login_required_api
def trash_deal(deal_id):
    """Move deal to recycle bin."""
    from utils.permissions import check_entity_access, get_current_user_from_session

    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    user = get_current_user_from_session()

    deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id, is_deleted=False).first()
    if not deal:
        return jsonify({'error': 'Deal not found'}), 404
    if not check_entity_access(user, deal, 'delete'):
        logger.warning(f"Access denied: user {user.id} attempted to trash deal {deal_id}")
        return jsonify({'error': 'Access denied to this deal'}), 403

    try:
        PipelineService.soft_delete_deal(workspace_id, deal_id, user_id)
        return jsonify({'message': 'Deal çöp kutusuna taşındı'}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error trashing deal: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/<int:deal_id>/untrash', methods=['POST'])
@login_required_api
def untrash_deal(deal_id):
    """Restore a deal from recycle bin."""
    from utils.permissions import check_entity_access, get_current_user_from_session

    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    user = get_current_user_from_session()

    deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id, is_deleted=True).first()
    if not deal:
        return jsonify({'error': 'Deal not found'}), 404
    if not check_entity_access(user, deal, 'delete'):
        logger.warning(f"Access denied: user {user.id} attempted to untrash deal {deal_id}")
        return jsonify({'error': 'Access denied to this deal'}), 403

    try:
        PipelineService.restore_deleted_deal(workspace_id, deal_id, user_id)
        return jsonify({'message': 'Deal geri yüklendi'}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error untrashing deal: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/<int:deal_id>', methods=['DELETE'])
@login_required_api
def delete_deal(deal_id):
    """Soft delete a deal"""
    from utils.permissions import check_entity_access, get_current_user_from_session
    
    workspace_id = session.get('workspace_id')
    user = get_current_user_from_session()
    
    deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id, is_deleted=False).first()
    
    if not deal:
        return jsonify({'error': 'Deal not found'}), 404
    
    # SECURITY: Check entity access (IDOR protection)
    if not check_entity_access(user, deal, 'delete'):
        logger.warning(f"Access denied: user {user.id} attempted to delete deal {deal_id}")
        return jsonify({'error': 'Access denied to this deal'}), 403
    
    try:
        deal.is_deleted = True
        deal.deleted_at = datetime.utcnow()
        db.session.commit()
        logger.info(f"Soft deleted deal {deal_id}")
        return jsonify({'message': 'Kayıt başarıyla silindi (çöp kutusuna taşındı)'}), 200
    except Exception as e:
        logger.error(f"Error deleting deal: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/<int:deal_id>/restore', methods=['POST'])
@login_required_api
def restore_deal(deal_id):
    """Restore a soft deleted deal"""
    workspace_id = session.get('workspace_id')
    deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id, is_deleted=True).first()

    if not deal:
        return jsonify({'error': 'Deal not found'}), 404

    try:
        deal.is_deleted = False
        deal.deleted_at = None
        db.session.commit()
        return jsonify({'message': 'Kayıt başarıyla geri yüklendi'}), 200
    except Exception as e:
        logger.error(f"Error restoring deal: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


# ═══ FORECASTING & ANALYTICS ═══

@bp.route('/deals/analytics', methods=['GET'])
@login_required_api
def get_analytics():
    """
    Get pipeline analytics and KPI metrics.
    Query params: pipeline_id (optional)
    Returns: total_value, open_deals, weighted_forecast
    """
    workspace_id = session.get('workspace_id')
    pipeline_id = request.args.get('pipeline_id', type=int)
    
    try:
        # Build query for open deals
        query = Deal.query.filter_by(
            workspace_id=workspace_id,
            is_deleted=False,
            status='open'
        )
        
        if pipeline_id:
            query = query.filter_by(pipeline_id=pipeline_id)
        
        # Eager load stage for probability calculation
        query = query.options(db.joinedload(Deal.stage))
        deals = query.all()
        
        # Calculate metrics
        total_value = sum(float(deal.value) for deal in deals)
        open_deals = len(deals)
        weighted_forecast = sum(
            float(deal.value) * ((deal.stage.probability / 100.0) if deal.stage else 0.0)
            for deal in deals
        )
        by_category = {
            'pipeline': round(sum(float(d.value) for d in deals if d.forecast_category == 'pipeline'), 2),
            'best_case': round(sum(float(d.value) for d in deals if d.forecast_category == 'best_case'), 2),
            'commit': round(sum(float(d.value) for d in deals if d.forecast_category == 'commit'), 2),
        }
        
        return jsonify({
            'total_value': round(total_value, 2),
            'open_deals': open_deals,
            'weighted_forecast': round(weighted_forecast, 2),
            'by_category': by_category
        }), 200
        
    except Exception as e:
        import traceback
        logger.error(f"Error calculating analytics: {e}")
        logger.error(traceback.format_exc())
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@bp.route('/deals/forecast', methods=['GET'])
@login_required_api
def get_forecast():
    """
    Get sales forecast.
    Query params: pipeline_id (optional)
    """
    workspace_id = session.get('workspace_id')
    pipeline_id = request.args.get('pipeline_id', type=int)
    
    try:
        forecast = PipelineService.calculate_forecast(workspace_id, pipeline_id)
        return jsonify(forecast), 200
    except Exception as e:
        logger.error(f"Error calculating forecast: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/win-loss-reasons', methods=['GET'])
@login_required_api
def list_win_loss_reasons():
    """List active win/loss taxonomy reasons."""
    workspace_id = session.get('workspace_id')
    category = request.args.get('category')
    try:
        reasons = PipelineAdvancedService.list_win_loss_reasons(workspace_id, category)
        return jsonify({
            'reasons': [{
                'id': r.id,
                'category': r.category,
                'code': r.code,
                'label': r.label,
                'is_active': bool(r.is_active),
            } for r in reasons]
        }), 200
    except Exception as e:
        logger.error(f"Error listing win/loss reasons: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/win-loss-reasons', methods=['POST'])
@login_required_api
def create_win_loss_reason():
    """Create a win/loss reason taxonomy row."""
    workspace_id = session.get('workspace_id')
    data = request.get_json() or {}
    try:
        reason = PipelineAdvancedService.create_win_loss_reason(workspace_id, data)
        return jsonify({
            'id': reason.id,
            'category': reason.category,
            'code': reason.code,
            'label': reason.label,
            'is_active': bool(reason.is_active),
        }), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating win/loss reason: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/hygiene', methods=['GET'])
@login_required_api
def get_deal_hygiene():
    """Return sales hygiene report (next step / stale activity)."""
    workspace_id = session.get('workspace_id')
    stale_days = request.args.get('stale_days', default=7, type=int)
    try:
        report = PipelineAdvancedService.get_hygiene_report(workspace_id, stale_days)
        return jsonify(report), 200
    except Exception as e:
        logger.error(f"Error building deal hygiene report: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/duplicates', methods=['GET'])
@login_required_api
def find_deal_duplicates():
    """Find likely duplicate deals."""
    workspace_id = session.get('workspace_id')
    try:
        groups = PipelineAdvancedService.find_deal_duplicates(workspace_id)
        return jsonify({'duplicate_groups': groups}), 200
    except Exception as e:
        logger.error(f"Error finding deal duplicates: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/merge', methods=['POST'])
@login_required_api
def merge_deals():
    """Merge two deals. Body: { primary_id, secondary_id }"""
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json() or {}
    primary_id = data.get('primary_id')
    secondary_id = data.get('secondary_id')
    if not primary_id or not secondary_id:
        return jsonify({'error': 'primary_id and secondary_id are required'}), 400
    try:
        deal = PipelineAdvancedService.merge_deals(workspace_id, int(primary_id), int(secondary_id), user_id)
        return jsonify({
            'message': 'Deals merged successfully',
            'deal': {
                'id': deal.id,
                'name': deal.name,
                'value': float(deal.value),
                'status': deal.status,
            }
        }), 200
    except (ValueError, LookupError) as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error merging deals: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/products', methods=['GET'])
@login_required_api
def list_products():
    """List active products for CPQ catalog."""
    workspace_id = session.get('workspace_id')
    search = request.args.get('search')
    active_only = request.args.get('active_only', default='true').lower() != 'false'
    try:
        products = PipelineAdvancedService.list_products(workspace_id, search, active_only)
        return jsonify({
            'products': [{
                'id': p.id,
                'sku': p.sku,
                'name': p.name,
                'description': p.description,
                'currency': p.currency,
                'unit_price': float(p.unit_price),
                'is_active': bool(p.is_active),
            } for p in products]
        }), 200
    except Exception as e:
        logger.error(f"Error listing products: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/products', methods=['POST'])
@login_required_api
def create_product():
    """Create product row for CPQ catalog."""
    workspace_id = session.get('workspace_id')
    data = request.get_json() or {}
    try:
        product = PipelineAdvancedService.create_product(workspace_id, data)
        return jsonify({
            'id': product.id,
            'sku': product.sku,
            'name': product.name,
            'description': product.description,
            'currency': product.currency,
            'unit_price': float(product.unit_price),
            'is_active': bool(product.is_active),
        }), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating product: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/<int:deal_id>/line-items', methods=['GET'])
@login_required_api
def list_deal_line_items(deal_id):
    """List line items for a deal."""
    workspace_id = session.get('workspace_id')
    try:
        items = PipelineAdvancedService.list_deal_line_items(workspace_id, deal_id)
        return jsonify({
            'line_items': [{
                'id': i.id,
                'deal_id': i.deal_id,
                'product_id': i.product_id,
                'item_name': i.item_name,
                'quantity': float(i.quantity),
                'unit_price': float(i.unit_price),
                'discount_pct': float(i.discount_pct),
                'tax_pct': float(i.tax_pct),
                'total_amount': float(i.total_amount),
            } for i in items]
        }), 200
    except Exception as e:
        logger.error(f"Error listing line items: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/<int:deal_id>/line-items', methods=['POST'])
@login_required_api
def add_deal_line_item(deal_id):
    """Add a line item to deal and recalculate amount."""
    workspace_id = session.get('workspace_id')
    data = request.get_json() or {}
    try:
        item = PipelineAdvancedService.add_deal_line_item(workspace_id, deal_id, data)
        return jsonify({
            'id': item.id,
            'deal_id': item.deal_id,
            'product_id': item.product_id,
            'item_name': item.item_name,
            'quantity': float(item.quantity),
            'unit_price': float(item.unit_price),
            'discount_pct': float(item.discount_pct),
            'tax_pct': float(item.tax_pct),
            'total_amount': float(item.total_amount),
        }), 201
    except (ValueError, LookupError) as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error adding line item: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/<int:deal_id>/line-items/<int:line_item_id>', methods=['DELETE'])
@login_required_api
def delete_deal_line_item(deal_id, line_item_id):
    """Delete a line item from deal."""
    workspace_id = session.get('workspace_id')
    try:
        PipelineAdvancedService.remove_deal_line_item(workspace_id, deal_id, line_item_id)
        return jsonify({'message': 'Line item removed'}), 200
    except (ValueError, LookupError) as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting line item: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/<int:deal_id>/quotes', methods=['GET'])
@login_required_api
def list_deal_quotes(deal_id):
    """List quotes created for a deal."""
    workspace_id = session.get('workspace_id')
    try:
        quotes = PipelineAdvancedService.list_quotes(workspace_id, deal_id)
        return jsonify({
            'quotes': [{
                'id': q.id,
                'deal_id': q.deal_id,
                'quote_number': q.quote_number,
                'status': q.status,
                'valid_until': q.valid_until.isoformat() if q.valid_until else None,
                'currency': q.currency,
                'subtotal': float(q.subtotal),
                'discount_total': float(q.discount_total),
                'tax_total': float(q.tax_total),
                'grand_total': float(q.grand_total),
                'notes': q.notes,
                'created_at': q.created_at.isoformat() if q.created_at else None,
            } for q in quotes]
        }), 200
    except Exception as e:
        logger.error(f"Error listing quotes: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/<int:deal_id>/quotes', methods=['POST'])
@login_required_api
def create_deal_quote(deal_id):
    """Create quote from deal line-items."""
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json() or {}
    if data.get('valid_until'):
        data['valid_until'] = datetime.fromisoformat(data['valid_until']).date()
    try:
        quote = PipelineAdvancedService.create_quote_from_deal(workspace_id, deal_id, user_id, data)
        return jsonify({
            'id': quote.id,
            'deal_id': quote.deal_id,
            'quote_number': quote.quote_number,
            'status': quote.status,
            'valid_until': quote.valid_until.isoformat() if quote.valid_until else None,
            'currency': quote.currency,
            'subtotal': float(quote.subtotal),
            'discount_total': float(quote.discount_total),
            'tax_total': float(quote.tax_total),
            'grand_total': float(quote.grand_total),
        }), 201
    except (ValueError, LookupError) as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating deal quote: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/rotting', methods=['GET'])
@login_required_api
def get_rotting_deals():
    """
    Get deals that have been in their stage too long.
    Query params: pipeline_id (optional)
    """
    workspace_id = session.get('workspace_id')
    if not workspace_id or not isinstance(workspace_id, int):
        return jsonify({'error': 'Invalid workspace'}), 400
    
    # Handle pipeline_id parameter - can be None, empty string, or valid int
    pipeline_id_str = request.args.get('pipeline_id', '').strip()
    pipeline_id = None
    
    if pipeline_id_str:
        try:
            pipeline_id = int(pipeline_id_str)
            if pipeline_id < 1:
                return jsonify({'error': 'Invalid pipeline_id'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid pipeline_id format'}), 400
    
    try:
        rotting_deals = PipelineService.get_rotting_deals(workspace_id, pipeline_id)
        return jsonify({'rotting_deals': rotting_deals}), 200
    except Exception as e:
        logger.error(f"Error getting rotting deals: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/auto-tasks', methods=['POST'])
@login_required_api
def create_auto_tasks():
    """
    Manually trigger auto-task creation for rotting deals.
    """
    workspace_id = session.get('workspace_id')
    if not workspace_id or not isinstance(workspace_id, int):
        return jsonify({'error': 'Invalid workspace'}), 400
    
    try:
        tasks_created = PipelineService.create_auto_tasks_for_rotting_deals(workspace_id)
        return jsonify({
            'message': f'Created {tasks_created} reminder tasks',
            'tasks_created': tasks_created
        }), 200
    except Exception as e:
        logger.error(f"Error creating auto-tasks: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

