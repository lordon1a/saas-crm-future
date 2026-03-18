"""
Pipeline Settings API Routes
Handles configuration of pipeline stages (name, probability, rotting_days, order)
"""
from flask import Blueprint, request, jsonify, session
from models_crm import db, DealStage, Pipeline
from functools import wraps
import logging

logger = logging.getLogger(__name__)

pipeline_settings_bp = Blueprint('pipeline_settings', __name__, url_prefix='/api/v1/pipeline')


def login_required_api(f):
    """Decorator to require login for API endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function


@pipeline_settings_bp.route('/settings', methods=['GET'])
@login_required_api
def get_pipeline_settings():
    """
    GET /api/v1/pipeline/settings
    Returns all stage details ordered by 'order' field
    """
    try:
        workspace_id = session.get('workspace_id')
        
        # Get workspace's default pipeline
        pipeline = Pipeline.query.filter_by(workspace_id=workspace_id, is_default=True).first()
        if not pipeline:
            return jsonify({'error': 'Pipeline not found'}), 404
        
        # Get all active stages ordered by order field
        stages = DealStage.query.filter_by(
            pipeline_id=pipeline.id,
            is_active=True
        ).order_by(DealStage.order).all()
        
        stages_data = []
        for stage in stages:
            stages_data.append({
                'id': stage.id,
                'name': stage.name,
                'probability': stage.probability,
                'rotting_days': stage.rotting_days,
                'order': stage.order,
                'is_active': stage.is_active
            })
        
        return jsonify({
            'pipeline_id': pipeline.id,
            'pipeline_name': pipeline.name,
            'stages': stages_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching pipeline settings: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


@pipeline_settings_bp.route('/settings', methods=['PUT'])
@login_required_api
def update_pipeline_settings():
    """
    PUT /api/v1/pipeline/settings
    Bulk update stages: update existing, soft delete missing, create new ones
    
    Payload example:
    {
        "pipeline_name": "Satış Süreci",
        "stages": [
            {"id": 1, "name": "Değerlendirilen", "probability": 50, "order": 0, "rotting_days": 7},
            {"name": "Yeni Aşama", "probability": 75, "order": 1, "rotting_days": null}
        ]
    }
    """
    try:
        workspace_id = session.get('workspace_id')
        data = request.get_json()
        
        if not data or 'stages' not in data:
            return jsonify({'error': 'Invalid payload'}), 400
        
        # Get workspace's default pipeline
        pipeline = Pipeline.query.filter_by(workspace_id=workspace_id, is_default=True).first()
        if not pipeline:
            return jsonify({'error': 'Pipeline not found'}), 404
        
        # Update pipeline name if provided
        if 'pipeline_name' in data and data['pipeline_name']:
            pipeline.name = data['pipeline_name']
        
        incoming_stages = data['stages']
        incoming_ids = [s['id'] for s in incoming_stages if 'id' in s and s['id']]
        
        # Step 1: Temporarily set all existing stages to high order numbers to avoid conflicts
        existing_stages = DealStage.query.filter_by(pipeline_id=pipeline.id).all()
        for idx, stage in enumerate(existing_stages):
            stage.order = 1000 + idx
        db.session.flush()
        
        # Step 2: Soft delete stages not in incoming list
        for stage in existing_stages:
            if stage.id not in incoming_ids:
                stage.is_active = False
                logger.info(f"Soft deleted stage: {stage.name} (id={stage.id})")
        
        # Step 3: Update or create stages with correct order
        for stage_data in incoming_stages:
            stage_id = stage_data.get('id')
            
            if stage_id:
                # Update existing stage
                stage = DealStage.query.get(stage_id)
                if stage and stage.pipeline_id == pipeline.id:
                    stage.name = stage_data.get('name', stage.name)
                    stage.probability = stage_data.get('probability', stage.probability)
                    stage.rotting_days = stage_data.get('rotting_days')
                    stage.order = stage_data.get('order', stage.order)
                    stage.is_active = True  # Reactivate if was soft deleted
                    logger.info(f"Updated stage: {stage.name} (id={stage.id})")
            else:
                # Create new stage
                new_stage = DealStage(
                    pipeline_id=pipeline.id,
                    name=stage_data.get('name', 'Yeni Aşama'),
                    probability=stage_data.get('probability', 100),
                    rotting_days=stage_data.get('rotting_days'),
                    order=stage_data.get('order', 0),
                    is_active=True
                )
                db.session.add(new_stage)
                logger.info(f"Created new stage: {new_stage.name}")
        
        db.session.commit()
        
        return jsonify({
            'message': 'Pipeline settings updated successfully',
            'pipeline_id': pipeline.id
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating pipeline settings: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500
