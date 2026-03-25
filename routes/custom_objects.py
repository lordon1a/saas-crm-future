from functools import wraps
from flask import Blueprint, request, jsonify, session
from services.custom_object_service import CustomObjectService
import logging

logger = logging.getLogger(__name__)

custom_objects_bp = Blueprint('custom_objects', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or 'workspace_id' not in session:
            return jsonify({'error': 'Unauthorized', 'message': 'Please log in to continue'}), 401
        return f(*args, **kwargs)
    return decorated_function

@custom_objects_bp.route('/', methods=['GET'])
@login_required
def get_custom_objects():
    workspace_id = session['workspace_id']
    objects = CustomObjectService.get_custom_objects(workspace_id)
    return jsonify({
        'status': 'success',
        'custom_objects': [obj.to_dict() for obj in objects]
    })

@custom_objects_bp.route('/', methods=['POST'])
@login_required
def create_custom_object():
    workspace_id = session['workspace_id']
    data = request.json
    
    # Required fields
    if not data or 'name' not in data:
        return jsonify({'error': 'Bad Request', 'message': 'Missing required fields'}), 400
        
    try:
        obj = CustomObjectService.create_custom_object(
            workspace_id=workspace_id,
            name=data['name'],
            singular_label=data.get('singular_label', data.get('name')),
            plural_label=data.get('plural_label', data.get('plural_name')),
            description=data.get('description'),
            icon=data.get('icon', 'fas fa-cube'),
            icon_color=data.get('icon_color', '#6366f1'),
            schema_config=data.get('schema_config', [])
        )
        return jsonify({'status': 'success', 'data': obj.to_dict()}), 201
    except Exception as e:
        logger.error(f"Error creating custom object: {e}")
        return jsonify({'error': 'Internal Error', 'message': str(e)}), 500

@custom_objects_bp.route('/<int:obj_id>', methods=['PUT'])
@login_required
def update_custom_object(obj_id):
    workspace_id = session['workspace_id']
    data = request.json
    
    try:
        obj = CustomObjectService.update_custom_object_schema(workspace_id, obj_id, data)
        return jsonify({'status': 'success', 'data': obj.to_dict()})
    except ValueError as e:
        return jsonify({'error': 'Not Found', 'message': str(e)}), 404
    except Exception as e:
        return jsonify({'error': 'Internal Error', 'message': str(e)}), 500

@custom_objects_bp.route('/<int:obj_id>', methods=['DELETE'])
@login_required
def delete_custom_object(obj_id):
    workspace_id = session['workspace_id']
    try:
        success = CustomObjectService.delete_custom_object(workspace_id, obj_id)
        if success:
            return jsonify({'status': 'success'})
        return jsonify({'error': 'Not Found', 'message': 'Custom object not found'}), 404
    except Exception as e:
        return jsonify({'error': 'Internal Error', 'message': str(e)}), 500

@custom_objects_bp.route('/<int:obj_id>/records', methods=['GET'])
@login_required
def get_records(obj_id):
    workspace_id = session['workspace_id']
    records = CustomObjectService.get_records(workspace_id, obj_id)
    return jsonify({
        'status': 'success',
        'data': [
            {
                'id': rec.id,
                'record_name': rec.record_name,
                'properties': rec.properties,
                'created_at': rec.created_at.isoformat() if rec.created_at else None,
                'updated_at': rec.updated_at.isoformat() if rec.updated_at else None
            } for rec in records
        ]
    })

@custom_objects_bp.route('/<int:obj_id>/records', methods=['POST'])
@login_required
def create_record(obj_id):
    workspace_id = session['workspace_id']
    user_id = session['user_id']
    data = request.json
    
    if not data or 'record_name' not in data:
        return jsonify({'error': 'Bad Request', 'message': 'Missing record_name'}), 400
        
    try:
        rec = CustomObjectService.create_record(
            workspace_id=workspace_id,
            custom_object_id=obj_id,
            record_name=data['record_name'],
            properties=data.get('properties', {}),
            user_id=user_id
        )
        return jsonify({'status': 'success', 'data': {'id': rec.id}}), 201
    except ValueError as e:
        return jsonify({'error': 'Not Found', 'message': str(e)}), 404
    except Exception as e:
        return jsonify({'error': 'Internal Error', 'message': str(e)}), 500

@custom_objects_bp.route('/records/<int:record_id>', methods=['PUT'])
@login_required
def update_record(record_id):
    workspace_id = session['workspace_id']
    data = request.json
    
    try:
        rec = CustomObjectService.update_record(workspace_id, record_id, data)
        return jsonify({'status': 'success', 'data': {'id': rec.id}})
    except ValueError as e:
        return jsonify({'error': 'Not Found', 'message': str(e)}), 404
    except Exception as e:
        return jsonify({'error': 'Internal Error', 'message': str(e)}), 500

@custom_objects_bp.route('/links', methods=['POST'])
@login_required
def create_link():
    workspace_id = session['workspace_id']
    data = request.json
    
    required = ['from_type', 'from_id', 'to_type', 'to_id']
    if not data or not all(k in data for k in required):
        return jsonify({'error': 'Bad Request', 'message': 'Missing link entities'}), 400
        
    try:
        link = CustomObjectService.create_link(
            workspace_id=workspace_id,
            from_type=data['from_type'],
            from_id=data['from_id'],
            to_type=data['to_type'],
            to_id=data['to_id'],
            label=data.get('label')
        )
        return jsonify({'status': 'success', 'data': {'id': link.id}}), 201
    except Exception as e:
        return jsonify({'error': 'Internal Error', 'message': str(e)}), 500

@custom_objects_bp.route('/links/<entity_type>/<int:entity_id>', methods=['GET'])
@login_required
def get_links(entity_type, entity_id):
    workspace_id = session['workspace_id']
    links = CustomObjectService.get_links_for_entity(workspace_id, entity_type, entity_id)
    return jsonify({
        'status': 'success',
        'data': [
            {
                'id': l.id,
                'from_type': l.from_entity_type,
                'from_id': l.from_entity_id,
                'to_type': l.to_entity_type,
                'to_id': l.to_entity_id,
                'label': l.relationship_label,
                'created_at': l.created_at.isoformat() if l.created_at else None
            } for l in links
        ]
    })

@custom_objects_bp.route('/entity-records/<entity_type>/<int:entity_id>', methods=['GET'])
@login_required
def get_linked_records_for_entity(entity_type, entity_id):
    workspace_id = session['workspace_id']
    from models_crm import EntityLink, CustomObjectRecord, CustomObject
    from collections import defaultdict
    
    # from_entity_type='contact', to_entity_type='custom_object_record'
    links = EntityLink.query.filter_by(
        workspace_id=workspace_id,
        from_entity_type=entity_type,
        from_entity_id=entity_id,
        to_entity_type='custom_object_record'
    ).all()
    
    if not links:
        return jsonify({'status': 'success', 'data': []})
        
    record_ids = [l.to_entity_id for l in links]
    records = CustomObjectRecord.query.filter(
        CustomObjectRecord.workspace_id == workspace_id,
        CustomObjectRecord.id.in_(record_ids)
    ).all()
    
    grouped = defaultdict(list)
    for r in records:
        grouped[r.custom_object_id].append({
            'id': r.id,
            'record_name': r.record_name,
            'properties': r.properties,
            'link_id': next((l.id for l in links if l.to_entity_id == r.id), None),
            'created_at': r.created_at.isoformat() if r.created_at else None
        })
        
    objects = CustomObject.query.filter(
        CustomObject.workspace_id == workspace_id,
        CustomObject.id.in_(list(grouped.keys()))
    ).all()
    
    res = []
    for obj in objects:
        res.append({
            'custom_object': obj.to_dict(),
            'records': grouped[obj.id]
        })
        
    return jsonify({'status': 'success', 'data': res})


@custom_objects_bp.route('/links/<int:link_id>', methods=['DELETE'])
@login_required
def delete_link(link_id):
    workspace_id = session['workspace_id']
    try:
        success = CustomObjectService.delete_link(workspace_id, link_id)
        if success:
            return jsonify({'status': 'success'})
        return jsonify({'error': 'Not Found'}), 404
    except Exception as e:
        return jsonify({'error': 'Internal Error', 'message': str(e)}), 500
