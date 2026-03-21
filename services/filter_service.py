"""
Filter Service - Advanced filtering for contacts and companies
Supports complex queries with AND/OR logic, multiple operators, and custom fields
"""
from sqlalchemy import and_, or_, func, cast, String, Integer, Date
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class FilterService:
    """Advanced filtering service for CRM entities"""
    
    SUPPORTED_OPERATORS = {
        'equals': lambda field, value: field == value,
        'not_equals': lambda field, value: field != value,
        'contains': lambda field, value: field.ilike(f'%{value}%'),
        'not_contains': lambda field, value: ~field.ilike(f'%{value}%'),
        'starts_with': lambda field, value: field.ilike(f'{value}%'),
        'ends_with': lambda field, value: field.ilike(f'%{value}'),
        'greater_than': lambda field, value: field > value,
        'less_than': lambda field, value: field < value,
        'greater_than_or_equal': lambda field, value: field >= value,
        'less_than_or_equal': lambda field, value: field <= value,
        'is_null': lambda field, value: field.is_(None),
        'is_not_null': lambda field, value: field.isnot(None),
        'in': lambda field, value: field.in_(value if isinstance(value, list) else [value]),
        'not_in': lambda field, value: ~field.in_(value if isinstance(value, list) else [value]),
        'between': lambda field, value: field.between(value[0], value[1]) if isinstance(value, list) and len(value) == 2 else True,
    }
    
    @staticmethod
    def apply_filters(entity_type, workspace_id, user_id, filters, page=1, per_page=50, sort_by='display_order', sort_order='asc'):
        """Apply advanced filters to contacts or companies
        
        Args:
            entity_type: 'contact' or 'company'
            workspace_id: Workspace ID
            user_id: User ID
            filters: Filter configuration dict with 'filters' list
            page: Page number
            per_page: Items per page
            sort_by: Sort field
            sort_order: 'asc' or 'desc'
            
        Returns:
            Tuple of (results, pagination_info)
        """
        from models import db
        
        try:
            if entity_type == 'contact':
                return FilterService._apply_contact_filters(
                    workspace_id, user_id, filters, page, per_page, sort_by, sort_order
                )
            elif entity_type == 'company':
                return FilterService._apply_company_filters(
                    workspace_id, user_id, filters, page, per_page, sort_by, sort_order
                )
            else:
                raise ValueError(f'Unsupported entity type: {entity_type}')
        except Exception as e:
            logger.error(f'Error applying filters: {str(e)}', exc_info=True)
            raise
    
    @staticmethod
    def _apply_contact_filters(workspace_id, user_id, filters, page, per_page, sort_by, sort_order):
        """Apply filters to contacts"""
        from models_crm import Contact, Company
        from models import db
        
        query = Contact.query.filter_by(workspace_id=workspace_id, is_deleted=False)
        
        # Apply filters
        if filters:
            filter_conditions = None
            
            # Check if using group-based filters
            if 'groups' in filters:
                group_logic = filters.get('groupLogic', 'OR')
                filter_conditions = FilterService._build_group_filter_conditions(
                    Contact, filters['groups'], group_logic, workspace_id
                )
            elif 'filters' in filters:
                # Legacy single filter list
                filter_conditions = FilterService._build_filter_conditions(
                    Contact, filters['filters'], workspace_id
                )
            
            if filter_conditions is not None:
                query = query.filter(filter_conditions)
        
        # Eager load company
        query = query.options(db.joinedload(Contact.company))
        
        # Get total count
        total = query.count()
        
        # Apply sorting
        sort_field = getattr(Contact, sort_by, Contact.display_order)
        if sort_order == 'desc':
            query = query.order_by(sort_field.desc())
        else:
            query = query.order_by(sort_field.asc())
        
        # Apply pagination
        offset = (page - 1) * per_page
        results = query.offset(offset).limit(per_page).all()
        
        pagination_info = {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page,
            'has_next': page * per_page < total,
            'has_prev': page > 1
        }
        
        return results, pagination_info
    
    @staticmethod
    def _apply_company_filters(workspace_id, user_id, filters, page, per_page, sort_by, sort_order):
        """Apply filters to companies"""
        from models_crm import Company
        from models import db
        
        query = Company.query.filter_by(workspace_id=workspace_id, is_deleted=False)
        
        # Apply filters
        if filters:
            filter_conditions = None
            
            # Check if using group-based filters
            if 'groups' in filters:
                group_logic = filters.get('groupLogic', 'OR')
                filter_conditions = FilterService._build_group_filter_conditions(
                    Company, filters['groups'], group_logic, workspace_id
                )
            elif 'filters' in filters:
                # Legacy single filter list
                filter_conditions = FilterService._build_filter_conditions(
                    Company, filters['filters'], workspace_id
                )
            
            if filter_conditions is not None:
                query = query.filter(filter_conditions)
        
        # Eager load parent company
        query = query.options(db.joinedload(Company.parent_company))
        
        # Get total count
        total = query.count()
        
        # Apply sorting
        sort_field = getattr(Company, sort_by, Company.display_order)
        if sort_order == 'desc':
            query = query.order_by(sort_field.desc())
        else:
            query = query.order_by(sort_field.asc())
        
        # Apply pagination
        offset = (page - 1) * per_page
        results = query.offset(offset).limit(per_page).all()
        
        pagination_info = {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page,
            'has_next': page * per_page < total,
            'has_prev': page > 1
        }
        
        return results, pagination_info
    
    @staticmethod
    def _build_filter_conditions(model, filter_list, workspace_id):
        """Build SQLAlchemy filter conditions from filter list
        
        Args:
            model: SQLAlchemy model class
            filter_list: List of filter dicts with field, operator, value
            workspace_id: Workspace ID for validation
            
        Returns:
            SQLAlchemy filter condition or None
        """
        if not filter_list:
            return None
        
        conditions = []
        
        for filter_item in filter_list:
            field_name = filter_item.get('field')
            operator = filter_item.get('operator')
            value = filter_item.get('value')
            
            if not field_name or not operator:
                continue
            
            # Get the model field
            if not hasattr(model, field_name):
                logger.warning(f'Field {field_name} not found on model {model.__name__}')
                continue
            
            field = getattr(model, field_name)
            
            # Get operator function
            operator_func = FilterService.SUPPORTED_OPERATORS.get(operator)
            if not operator_func:
                logger.warning(f'Unsupported operator: {operator}')
                continue
            
            # Apply operator
            try:
                condition = operator_func(field, value)
                conditions.append(condition)
            except Exception as e:
                logger.error(f'Error applying filter {field_name} {operator} {value}: {str(e)}')
                continue
        
        # Combine all conditions with AND
        if conditions:
            return and_(*conditions)
        
        return None
    
    @staticmethod
    def _build_group_filter_conditions(model, groups, group_logic, workspace_id):
        """Build SQLAlchemy filter conditions from filter groups
        
        Args:
            model: SQLAlchemy model class
            groups: List of filter groups with logic and conditions
            group_logic: 'AND' or 'OR' to combine groups
            workspace_id: Workspace ID for validation
            
        Returns:
            SQLAlchemy filter condition or None
        """
        if not groups:
            return None
        
        group_conditions = []
        
        for group in groups:
            logic = group.get('logic', 'AND')
            conditions_list = group.get('conditions', [])
            
            if not conditions_list:
                continue
            
            # Build conditions for this group
            conditions = []
            for filter_item in conditions_list:
                field_name = filter_item.get('field')
                operator = filter_item.get('operator')
                value = filter_item.get('value')
                
                if not field_name or not operator:
                    continue
                
                # Get the model field
                if not hasattr(model, field_name):
                    logger.warning(f'Field {field_name} not found on model {model.__name__}')
                    continue
                
                field = getattr(model, field_name)
                
                # Get operator function
                operator_func = FilterService.SUPPORTED_OPERATORS.get(operator)
                if not operator_func:
                    logger.warning(f'Unsupported operator: {operator}')
                    continue
                
                # Apply operator
                try:
                    condition = operator_func(field, value)
                    conditions.append(condition)
                except Exception as e:
                    logger.error(f'Error applying filter {field_name} {operator} {value}: {str(e)}')
                    continue
            
            # Combine conditions within group based on group logic
            if conditions:
                if logic == 'OR':
                    group_conditions.append(or_(*conditions))
                else:
                    group_conditions.append(and_(*conditions))
        
        # Combine all groups based on group_logic
        if group_conditions:
            if group_logic == 'AND':
                return and_(*group_conditions)
            else:
                return or_(*group_conditions)
        
        return None
    
    @staticmethod
    def evaluate_quick_filter(quick_filter_id, entity_type):
        """Evaluate a quick filter preset
        
        Args:
            quick_filter_id: Quick filter identifier
            entity_type: 'contact' or 'company'
            
        Returns:
            Filter configuration dict
        """
        quick_filters = {
            'contact': {
                'high_score': {
                    'filters': [
                        {'field': 'lead_score', 'operator': 'greater_than_or_equal', 'value': 80}
                    ]
                },
                'recent': {
                    'filters': [
                        {'field': 'created_at', 'operator': 'greater_than', 
                         'value': (datetime.now() - timedelta(days=7)).isoformat()}
                    ]
                },
                'no_company': {
                    'filters': [
                        {'field': 'company_id', 'operator': 'is_null', 'value': None}
                    ]
                },
                'starred': {
                    'filters': [
                        {'field': 'is_starred', 'operator': 'equals', 'value': True}
                    ]
                }
            },
            'company': {
                'recent': {
                    'filters': [
                        {'field': 'created_at', 'operator': 'greater_than',
                         'value': (datetime.now() - timedelta(days=7)).isoformat()}
                    ]
                },
                'large': {
                    'filters': [
                        {'field': 'size', 'operator': 'in', 'value': ['201-500', '500+']}
                    ]
                },
                'no_parent': {
                    'filters': [
                        {'field': 'parent_company_id', 'operator': 'is_null', 'value': None}
                    ]
                }
            }
        }
        
        entity_filters = quick_filters.get(entity_type, {})
        filter_config = entity_filters.get(quick_filter_id)
        
        if not filter_config:
            raise ValueError(f'Unknown quick filter: {quick_filter_id}')
        
        return filter_config
