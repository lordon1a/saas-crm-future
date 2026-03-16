"""
Custom Field Service - Manage custom fields for contacts, companies, and deals
"""
import json
import logging
from typing import Optional, List, Dict, Any

from models import db
from models_crm import CustomField, CustomFieldValue

logger = logging.getLogger(__name__)


class CustomFieldService:
    """Service for managing custom fields"""
    
    VALID_ENTITY_TYPES = ['contact', 'company', 'deal']
    VALID_FIELD_TYPES = ['text', 'number', 'date', 'dropdown', 'checkbox', 'multi_select']
    
    @staticmethod
    def create_field(workspace_id: int, entity_type: str, field_name: str, 
                    field_type: str, options: Optional[List[str]] = None,
                    is_required: bool = False) -> CustomField:
        """
        Create a new custom field.
        
        Args:
            workspace_id: Workspace ID
            entity_type: Entity type (contact, company, deal)
            field_name: Field name
            field_type: Field type (text, number, date, dropdown, checkbox, multi_select)
            options: Options for dropdown/multi_select fields
            is_required: Whether field is required
            
        Returns:
            CustomField instance
        """
        # Validate entity type
        if entity_type not in CustomFieldService.VALID_ENTITY_TYPES:
            raise ValueError(f'Invalid entity_type. Must be one of: {CustomFieldService.VALID_ENTITY_TYPES}')
        
        # Validate field type
        if field_type not in CustomFieldService.VALID_FIELD_TYPES:
            raise ValueError(f'Invalid field_type. Must be one of: {CustomFieldService.VALID_FIELD_TYPES}')
        
        # Validate options for dropdown/multi_select
        if field_type in ['dropdown', 'multi_select']:
            if not options or not isinstance(options, list):
                raise ValueError(f'{field_type} fields require options list')
        
        # Check for duplicate field name
        existing = CustomField.query.filter_by(
            workspace_id=workspace_id,
            entity_type=entity_type,
            field_name=field_name
        ).first()
        
        if existing:
            raise ValueError(f'Field "{field_name}" already exists for {entity_type}')
        
        # Create field
        custom_field = CustomField(
            workspace_id=workspace_id,
            entity_type=entity_type,
            field_name=field_name,
            field_type=field_type,
            options=json.dumps(options) if options else None,
            is_required=is_required
        )
        
        db.session.add(custom_field)
        db.session.commit()
        
        logger.info(f'Created custom field: {field_name} ({field_type}) for {entity_type}')
        return custom_field
    
    @staticmethod
    def get_fields(workspace_id: int, entity_type: Optional[str] = None) -> List[CustomField]:
        """
        Get custom fields for workspace.
        
        Args:
            workspace_id: Workspace ID
            entity_type: Optional entity type filter
            
        Returns:
            List of CustomField instances
        """
        query = CustomField.query.filter_by(workspace_id=workspace_id)
        
        if entity_type:
            if entity_type not in CustomFieldService.VALID_ENTITY_TYPES:
                raise ValueError(f'Invalid entity_type: {entity_type}')
            query = query.filter_by(entity_type=entity_type)
        
        return query.order_by(CustomField.entity_type, CustomField.field_name).all()
    
    @staticmethod
    def update_field(field_id: int, workspace_id: int, **kwargs) -> CustomField:
        """
        Update custom field.
        
        Args:
            field_id: Field ID
            workspace_id: Workspace ID
            **kwargs: Fields to update (field_name, field_type, options, is_required)
            
        Returns:
            Updated CustomField instance
        """
        field = CustomField.query.filter_by(
            id=field_id,
            workspace_id=workspace_id
        ).first()
        
        if not field:
            raise ValueError('Custom field not found')
        
        # Update allowed fields
        if 'field_name' in kwargs:
            field.field_name = kwargs['field_name']
        
        if 'field_type' in kwargs:
            if kwargs['field_type'] not in CustomFieldService.VALID_FIELD_TYPES:
                raise ValueError(f'Invalid field_type: {kwargs["field_type"]}')
            field.field_type = kwargs['field_type']
        
        if 'options' in kwargs:
            field.options = json.dumps(kwargs['options']) if kwargs['options'] else None
        
        if 'is_required' in kwargs:
            field.is_required = kwargs['is_required']
        
        db.session.commit()
        
        logger.info(f'Updated custom field: {field.field_name}')
        return field
    
    @staticmethod
    def delete_field(field_id: int, workspace_id: int) -> bool:
        """
        Delete custom field and all its values.
        
        Args:
            field_id: Field ID
            workspace_id: Workspace ID
            
        Returns:
            True if deleted
        """
        field = CustomField.query.filter_by(
            id=field_id,
            workspace_id=workspace_id
        ).first()
        
        if not field:
            return False
        
        db.session.delete(field)
        db.session.commit()
        
        logger.info(f'Deleted custom field: {field.field_name}')
        return True
    
    @staticmethod
    def set_value(custom_field_id: int, entity_id: int, value: Any) -> CustomFieldValue:
        """
        Set custom field value for an entity.
        
        Args:
            custom_field_id: Custom field ID
            entity_id: Entity ID (contact/company/deal)
            value: Field value
            
        Returns:
            CustomFieldValue instance
        """
        field = CustomField.query.get(custom_field_id)
        if not field:
            raise ValueError('Custom field not found')
        
        # Validate and convert value based on field type
        validated_value = CustomFieldService._validate_value(field, value)
        
        # Check if value already exists
        field_value = CustomFieldValue.query.filter_by(
            custom_field_id=custom_field_id,
            entity_id=entity_id
        ).first()
        
        if field_value:
            # Update existing value
            field_value.value = validated_value
        else:
            # Create new value
            field_value = CustomFieldValue(
                custom_field_id=custom_field_id,
                entity_id=entity_id,
                value=validated_value
            )
            db.session.add(field_value)
        
        db.session.commit()
        return field_value
    
    @staticmethod
    def get_values(entity_type: str, entity_id: int, workspace_id: int) -> Dict[str, Any]:
        """
        Get all custom field values for an entity.
        
        Args:
            entity_type: Entity type (contact, company, deal)
            entity_id: Entity ID
            workspace_id: Workspace ID
            
        Returns:
            Dict mapping field names to values
        """
        # Get all fields for this entity type
        fields = CustomField.query.filter_by(
            workspace_id=workspace_id,
            entity_type=entity_type
        ).all()
        
        result = {}
        
        for field in fields:
            # Get value for this field
            field_value = CustomFieldValue.query.filter_by(
                custom_field_id=field.id,
                entity_id=entity_id
            ).first()
            
            if field_value:
                # Parse value based on field type
                result[field.field_name] = CustomFieldService._parse_value(field, field_value.value)
            else:
                result[field.field_name] = None
        
        return result
    
    @staticmethod
    def delete_value(custom_field_id: int, entity_id: int) -> bool:
        """
        Delete custom field value.
        
        Args:
            custom_field_id: Custom field ID
            entity_id: Entity ID
            
        Returns:
            True if deleted
        """
        field_value = CustomFieldValue.query.filter_by(
            custom_field_id=custom_field_id,
            entity_id=entity_id
        ).first()
        
        if not field_value:
            return False
        
        db.session.delete(field_value)
        db.session.commit()
        return True
    
    @staticmethod
    def _validate_value(field: CustomField, value: Any) -> str:
        """Validate and convert value to string for storage"""
        if value is None or value == '':
            if field.is_required:
                raise ValueError(f'Field "{field.field_name}" is required')
            return ''
        
        if field.field_type == 'text':
            return str(value)
        
        elif field.field_type == 'number':
            try:
                float(value)  # Validate it's a number
                return str(value)
            except (ValueError, TypeError):
                raise ValueError(f'Invalid number value for field "{field.field_name}"')
        
        elif field.field_type == 'date':
            # Expect ISO format: YYYY-MM-DD
            from datetime import datetime
            try:
                datetime.fromisoformat(str(value))
                return str(value)
            except ValueError:
                raise ValueError(f'Invalid date format for field "{field.field_name}". Use YYYY-MM-DD')
        
        elif field.field_type == 'checkbox':
            return 'true' if value in [True, 'true', '1', 1] else 'false'
        
        elif field.field_type == 'dropdown':
            options = json.loads(field.options) if field.options else []
            if str(value) not in options:
                raise ValueError(f'Invalid option for field "{field.field_name}". Must be one of: {options}')
            return str(value)
        
        elif field.field_type == 'multi_select':
            options = json.loads(field.options) if field.options else []
            if isinstance(value, list):
                for v in value:
                    if str(v) not in options:
                        raise ValueError(f'Invalid option "{v}" for field "{field.field_name}"')
                return json.dumps(value)
            else:
                raise ValueError(f'multi_select field "{field.field_name}" requires a list value')
        
        return str(value)
    
    @staticmethod
    def _parse_value(field: CustomField, value: str) -> Any:
        """Parse stored string value based on field type"""
        if not value:
            return None
        
        if field.field_type == 'number':
            try:
                return float(value) if '.' in value else int(value)
            except ValueError:
                return value
        
        elif field.field_type == 'checkbox':
            return value == 'true'
        
        elif field.field_type == 'multi_select':
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return []
        
        return value
