"""
Custom Fields API Routes
"""
from flask import Blueprint, request, jsonify, session
from functools import wraps

from services.custom_field_service import CustomFieldService

bp = Blueprint('custom_fields', __name__, url_prefix='/api/v1/custom-fields')


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id') or not session.get('workspace_id'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


@bp.route('', methods=['GET'])
@login_required
def list_custom_fields():
    """
    List custom fields for workspace.
    Query params:
        - entity_type: Optional filter (contact, company, deal)
    """
    workspace_id = session.get('workspace_id')
    entity_type = request.args.get('entity_type')
    
    try:
        fields = CustomFieldService.get_fields(workspace_id, entity_type)
        
        return jsonify([
            {
                'id': f.id,
                'entity_type': f.entity_type,
                'field_name': f.field_name,
                'field_type': f.field_type,
                'options': f.options,
                'is_required': f.is_required,
                'created_at': f.created_at.isoformat()
            }
            for f in fields
        ]), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('', methods=['POST'])
@login_required
def create_custom_field():
    """
    Create a new custom field.
    Body:
        - entity_type: contact, company, or deal
        - field_name: Field name
        - field_type: text, number, date, dropdown, checkbox, multi_select
        - options: Array of options (for dropdown/multi_select)
        - is_required: Boolean (default: false)
    """
    workspace_id = session.get('workspace_id')
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    entity_type = data.get('entity_type')
    field_name = data.get('field_name')
    field_type = data.get('field_type')
    options = data.get('options')
    is_required = data.get('is_required', False)
    
    if not all([entity_type, field_name, field_type]):
        return jsonify({'error': 'entity_type, field_name, and field_type are required'}), 400
    
    try:
        field = CustomFieldService.create_field(
            workspace_id=workspace_id,
            entity_type=entity_type,
            field_name=field_name,
            field_type=field_type,
            options=options,
            is_required=is_required
        )
        
        return jsonify({
            'id': field.id,
            'entity_type': field.entity_type,
            'field_name': field.field_name,
            'field_type': field.field_type,
            'options': field.options,
            'is_required': field.is_required,
            'created_at': field.created_at.isoformat()
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/<int:field_id>', methods=['PATCH'])
@login_required
def update_custom_field(field_id):
    """
    Update a custom field.
    Body:
        - field_name: New field name (optional)
        - field_type: New field type (optional)
        - options: New options (optional)
        - is_required: New required status (optional)
    """
    workspace_id = session.get('workspace_id')
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    try:
        field = CustomFieldService.update_field(field_id, workspace_id, **data)
        
        return jsonify({
            'id': field.id,
            'entity_type': field.entity_type,
            'field_name': field.field_name,
            'field_type': field.field_type,
            'options': field.options,
            'is_required': field.is_required,
            'created_at': field.created_at.isoformat()
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/<int:field_id>', methods=['DELETE'])
@login_required
def delete_custom_field(field_id):
    """Delete a custom field and all its values"""
    workspace_id = session.get('workspace_id')
    
    try:
        deleted = CustomFieldService.delete_field(field_id, workspace_id)
        
        if not deleted:
            return jsonify({'error': 'Custom field not found'}), 404
        
        return jsonify({'message': 'Custom field deleted'}), 200
        
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/values', methods=['POST'])
@login_required
def set_custom_field_value():
    """
    Set custom field value for an entity.
    Body:
        - custom_field_id: Field ID
        - entity_id: Entity ID (contact/company/deal)
        - value: Field value
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    custom_field_id = data.get('custom_field_id')
    entity_id = data.get('entity_id')
    value = data.get('value')
    
    if custom_field_id is None or entity_id is None:
        return jsonify({'error': 'custom_field_id and entity_id are required'}), 400
    
    try:
        field_value = CustomFieldService.set_value(custom_field_id, entity_id, value)
        
        return jsonify({
            'id': field_value.id,
            'custom_field_id': field_value.custom_field_id,
            'entity_id': field_value.entity_id,
            'value': field_value.value,
            'updated_at': field_value.updated_at.isoformat()
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/values/<entity_type>/<int:entity_id>', methods=['GET'])
@login_required
def get_custom_field_values(entity_type, entity_id):
    """
    Get all custom field values for an entity.
    Path params:
        - entity_type: contact, company, or deal
        - entity_id: Entity ID
    """
    workspace_id = session.get('workspace_id')
    
    try:
        values = CustomFieldService.get_values(entity_type, entity_id, workspace_id)
        return jsonify(values), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/values/<int:custom_field_id>/<int:entity_id>', methods=['DELETE'])
@login_required
def delete_custom_field_value(custom_field_id, entity_id):
    """Delete a custom field value"""
    try:
        deleted = CustomFieldService.delete_value(custom_field_id, entity_id)
        
        if not deleted:
            return jsonify({'error': 'Custom field value not found'}), 404
        
        return jsonify({'message': 'Custom field value deleted'}), 200
        
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500
