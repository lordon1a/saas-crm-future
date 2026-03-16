"""
Pipeline API Routes
API endpoints for pipeline and deal management
"""
from flask import Blueprint, request, jsonify, session
from models import db
from models_crm import Pipeline, DealStage, Deal, Company
from services.pipeline_service import PipelineService
from functools import wraps
from datetime import datetime, date
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
    pipelines = Pipeline.query.filter_by(workspace_id=workspace_id).all()
    
    result = []
    for pipeline in pipelines:
        result.append({
            'id': pipeline.id,
            'name': pipeline.name,
            'is_default': pipeline.is_default,
            'stages': [{
                'id': stage.id,
                'name': stage.name,
                'order': stage.order,
                'probability': stage.probability
            } for stage in pipeline.stages],
            'created_at': pipeline.created_at.isoformat()
        })
    
    return jsonify(result), 200


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
            'probability': stage.probability
        } for stage in pipeline.stages],
        'created_at': pipeline.created_at.isoformat()
    }), 200


# ═══ DEALS ═══

@bp.route('/deals', methods=['GET'])
@login_required_api
def get_deals():
    """
    Get deals with optional filters.
    Query params: stage_id, owner_id, status, company_id, pipeline_id
    """
    workspace_id = session.get('workspace_id')
    
    # Build filters from query params
    filters = {}
    if request.args.get('stage_id'):
        filters['stage_id'] = int(request.args.get('stage_id'))
    if request.args.get('owner_id'):
        filters['owner_id'] = int(request.args.get('owner_id'))
    if request.args.get('status'):
        filters['status'] = request.args.get('status')
    if request.args.get('company_id'):
        filters['company_id'] = int(request.args.get('company_id'))
    if request.args.get('pipeline_id'):
        filters['pipeline_id'] = int(request.args.get('pipeline_id'))
    
    deals = PipelineService.get_deals(workspace_id, filters)
    
    result = []
    for deal in deals:
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
            'closed_at': deal.closed_at.isoformat() if deal.closed_at else None
        })
    
    return jsonify(result), 200


@bp.route('/deals/<int:deal_id>', methods=['GET'])
@login_required_api
def get_deal(deal_id):
    """Get a specific deal"""
    workspace_id = session.get('workspace_id')
    deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id).first()
    
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
    Required: name, company_id, pipeline_id, owner_id
    Optional: value, expected_close_date
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
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error creating deal: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


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
        
        return jsonify({
            'id': deal.id,
            'name': deal.name,
            'value': float(deal.value),
            'expected_close_date': deal.expected_close_date.isoformat() if deal.expected_close_date else None,
            'owner_id': deal.owner_id,
            'updated_at': deal.updated_at.isoformat()
        }), 200
    
    except ValueError as e:
        logger.error(f"Error updating deal: {e}")
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
        
        return jsonify({
            'id': deal.id,
            'stage_id': deal.stage_id,
            'stage_name': deal.stage.name,
            'updated_at': deal.updated_at.isoformat()
        }), 200
    
    except ValueError as e:
        logger.error(f"Error moving deal stage: {e}")
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
        
        return jsonify({
            'id': deal.id,
            'status': deal.status,
            'win_loss_reason': deal.win_loss_reason,
            'closed_at': deal.closed_at.isoformat(),
            'updated_at': deal.updated_at.isoformat()
        }), 200
    
    except ValueError as e:
        logger.error(f"Error closing deal: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error closing deal: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/deals/<int:deal_id>', methods=['DELETE'])
@login_required_api
def delete_deal(deal_id):
    """Delete a deal"""
    workspace_id = session.get('workspace_id')
    deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id).first()
    
    if not deal:
        return jsonify({'error': 'Deal not found'}), 404
    
    try:
        db.session.delete(deal)
        db.session.commit()
        logger.info(f"Deleted deal {deal_id}")
        return jsonify({'message': 'Deal deleted successfully'}), 200
    except Exception as e:
        logger.error(f"Error deleting deal: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


# ═══ FORECASTING ═══

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
