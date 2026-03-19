"""
Pipeline API Routes
API endpoints for pipeline and deal management
"""
from flask import Blueprint, request, jsonify, session
from models import db
from models_crm import Pipeline, DealStage, Deal, Company, Contact
from services.pipeline_service import PipelineService
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
            query = query.join(Contact, Contact.company_id == Deal.company_id).filter(
                Contact.id == filters['contact_id'],
                Contact.workspace_id == workspace_id,
                Contact.is_deleted == False,
            )
        if filters.get('pipeline_id'):
            query = query.filter_by(pipeline_id=filters['pipeline_id'])
        
        # Eager load relationships
        from models import db
        query = query.options(
            db.joinedload(Deal.company),
            db.joinedload(Deal.pipeline),
            db.joinedload(Deal.stage)
        )
        
        # Paginate
        pagination = query.order_by(Deal.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        result = []
        for deal in pagination.items:
            result.append({
                'id': deal.id,
                'name': deal.name,
                'company': {
                    'id': deal.company.id,
                    'name': deal.company.name
                } if deal.company else None,
                'pipeline_id': deal.pipeline_id,
                'pipeline_name': deal.pipeline.name,
                'stage': {
                    'id': deal.stage.id,
                    'name': deal.stage.name,
                    'order': deal.stage.order,
                    'probability': deal.stage.probability
                },
                'value': float(deal.value),
                'expected_close_date': deal.expected_close_date.isoformat() if deal.expected_close_date else None,
                'owner_id': deal.owner_id,
                'status': deal.status,
                'win_loss_reason': deal.win_loss_reason,
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
    workspace_id = session.get('workspace_id')
    deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id, is_deleted=False).first()
    
    if not deal:
        return jsonify({'error': 'Deal not found'}), 404
    
    return jsonify({
        'id': deal.id,
        'name': deal.name,
        'company': {
            'id': deal.company.id,
            'name': deal.company.name
        } if deal.company else None,
        'pipeline_id': deal.pipeline_id,
        'pipeline_name': deal.pipeline.name,
        'stage': {
            'id': deal.stage.id,
            'name': deal.stage.name,
            'order': deal.stage.order,
            'probability': deal.stage.probability
        },
        'value': float(deal.value),
        'expected_close_date': deal.expected_close_date.isoformat() if deal.expected_close_date else None,
        'owner_id': deal.owner_id,
        'status': deal.status,
        'win_loss_reason': deal.win_loss_reason,
        'created_at': deal.created_at.isoformat(),
        'updated_at': deal.updated_at.isoformat() if deal.updated_at else None,
        'closed_at': deal.closed_at.isoformat() if deal.closed_at else None
    }), 200


@bp.route('/deals', methods=['POST'])
@login_required_api
def create_deal():
    """
    Create a new deal.
    Required: name, contact_id, pipeline_id
    Optional: company_id, value, expected_close_date, stage_id
    
    If contact_id is provided but company_id is not:
    - If contact is a CRM Contact with company, use that company
    - If contact is a Customer (Telegram/WhatsApp), create a company from customer data
    """
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json()
    
    try:
        # Parse expected_close_date if provided
        if 'expected_close_date' in data and data['expected_close_date']:
            data['expected_close_date'] = datetime.fromisoformat(data['expected_close_date']).date()
        
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
        
        return jsonify({
            'id': deal.id,
            'name': deal.name,
            'company_id': deal.company_id,
            'pipeline_id': deal.pipeline_id,
            'stage_id': deal.stage_id,
            'value': float(deal.value),
            'expected_close_date': deal.expected_close_date.isoformat() if deal.expected_close_date else None,
            'owner_id': deal.owner_id,
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
    Allowed fields: name, value, expected_close_date, owner_id
    """
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json()
    
    try:
        # Parse expected_close_date if provided
        if 'expected_close_date' in data and data['expected_close_date']:
            data['expected_close_date'] = datetime.fromisoformat(data['expected_close_date']).date()
        
        deal = PipelineService.update_deal(workspace_id, deal_id, data, user_id)
        
        # Prepare response data before async operations
        response_data = {
            'id': deal.id,
            'name': deal.name,
            'value': float(deal.value),
            'expected_close_date': deal.expected_close_date.isoformat() if deal.expected_close_date else None,
            'owner_id': deal.owner_id,
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
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json()
    
    if 'stage_id' not in data:
        return jsonify({'error': 'stage_id is required'}), 400
    
    try:
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


@bp.route('/deals/<int:deal_id>/close', methods=['POST'])
@login_required_api
def close_deal(deal_id):
    """
    Close a deal as won or lost.
    Required: status ('won' or 'lost'), win_loss_reason
    """
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json()
    
    if 'status' not in data:
        return jsonify({'error': 'status is required'}), 400
    if 'win_loss_reason' not in data:
        return jsonify({'error': 'win_loss_reason is required'}), 400
    
    try:
        deal = PipelineService.close_deal(
            workspace_id,
            deal_id,
            data['status'],
            data['win_loss_reason'],
            user_id
        )
        
        # Prepare response data before async operations
        response_data = {
            'id': deal.id,
            'status': deal.status,
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


@bp.route('/deals/<int:deal_id>', methods=['DELETE'])
@login_required_api
def delete_deal(deal_id):
    """Soft delete a deal"""
    workspace_id = session.get('workspace_id')
    deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id, is_deleted=False).first()
    
    if not deal:
        return jsonify({'error': 'Deal not found'}), 404
    
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
            float(deal.value) * (deal.stage.probability if deal.stage else 0.0)
            for deal in deals
        )
        
        return jsonify({
            'total_value': round(total_value, 2),
            'open_deals': open_deals,
            'weighted_forecast': round(weighted_forecast, 2)
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

