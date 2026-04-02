"""
Filter Validation Service
Validates filter configurations and workspace access
"""
import logging

logger = logging.getLogger(__name__)


class FilterValidationService:
    """Service for validating filter configurations and access"""

    MAX_TOP_LEVEL_FILTERS = 50
    MAX_GROUPS = 15
    MAX_GROUP_CONDITIONS = 20
    MAX_IN_LIST_ITEMS = 200

    @staticmethod
    def _supported_operators():
        from services.filter_service import FilterService

        return set(FilterService.SUPPORTED_OPERATORS.keys())

    @staticmethod
    def _validate_condition(filter_item, supported_operators, location):
        if not isinstance(filter_item, dict):
            return False, f'{location} must be a dictionary'

        field_name = filter_item.get('field')
        operator = filter_item.get('operator')
        value = filter_item.get('value')

        if not field_name:
            return False, f'{location} missing "field" key'

        if not operator:
            return False, f'{location} missing "operator" key'

        if operator not in supported_operators:
            return False, f'{location} has unsupported operator: {operator}'

        if operator in ('in', 'not_in') and isinstance(value, list) and len(value) > FilterValidationService.MAX_IN_LIST_ITEMS:
            return (
                False,
                f'{location} list is too large. Maximum {FilterValidationService.MAX_IN_LIST_ITEMS} items allowed',
            )

        if operator == 'between':
            if not isinstance(value, list) or len(value) != 2:
                return False, f'{location} with "between" operator must have a list with exactly 2 values'

        return True, None
    
    @staticmethod
    def check_workspace_access(workspace_id, user_id):
        """Check if user has access to workspace
        
        Args:
            workspace_id: Workspace ID to check
            user_id: User ID to validate
            
        Returns:
            bool: True if user has access, False otherwise
        """
        try:
            from models import User, Workspace
            
            # Check if user exists
            user = User.query.get(user_id)
            if not user:
                logger.warning(f'User {user_id} not found')
                return False
            
            # Check if workspace exists
            workspace = Workspace.query.get(workspace_id)
            if not workspace:
                logger.warning(f'Workspace {workspace_id} not found')
                return False
            
            # Check if user belongs to workspace
            if user.workspace_id != workspace_id:
                logger.warning(f'User {user_id} does not belong to workspace {workspace_id}')
                return False
            
            return True
            
        except Exception as e:
            logger.error(f'Error checking workspace access: {str(e)}')
            return False
    
    @staticmethod
    def validate_filters(filters, entity_type):
        """Validate filter configuration
        
        Args:
            filters: Filter configuration dict
            entity_type: 'contact' or 'company'
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not filters:
            return True, None
        
        if not isinstance(filters, dict):
            return False, 'Filters must be a dictionary'
        
        if entity_type not in ('contact', 'company'):
            return False, f'Unsupported entity type: {entity_type}'

        has_filter_list = 'filters' in filters
        has_groups = 'groups' in filters

        if not has_filter_list and not has_groups:
            return False, 'Filters must contain either "filters" or "groups"'

        supported_operators = FilterValidationService._supported_operators()

        if has_filter_list:
            filter_list = filters.get('filters')
            if not isinstance(filter_list, list):
                return False, '"filters" must be a list'

            if len(filter_list) > FilterValidationService.MAX_TOP_LEVEL_FILTERS:
                return (
                    False,
                    f'Too many filters. Maximum {FilterValidationService.MAX_TOP_LEVEL_FILTERS} top-level filters allowed',
                )

            for idx, filter_item in enumerate(filter_list):
                is_valid, error_message = FilterValidationService._validate_condition(
                    filter_item,
                    supported_operators,
                    f'Filter {idx}',
                )
                if not is_valid:
                    return False, error_message

        if has_groups:
            groups = filters.get('groups')
            if not isinstance(groups, list):
                return False, '"groups" must be a list'

            if len(groups) > FilterValidationService.MAX_GROUPS:
                return False, f'Too many groups. Maximum {FilterValidationService.MAX_GROUPS} groups allowed'

            group_logic = filters.get('groupLogic', 'OR')
            if group_logic not in ('AND', 'OR'):
                return False, '"groupLogic" must be either "AND" or "OR"'

            for group_index, group in enumerate(groups):
                if not isinstance(group, dict):
                    return False, f'Group {group_index} must be a dictionary'

                logic = group.get('logic', 'AND')
                if logic not in ('AND', 'OR'):
                    return False, f'Group {group_index} has invalid logic: {logic}'

                conditions = group.get('conditions')
                if not isinstance(conditions, list):
                    return False, f'Group {group_index} must contain a "conditions" list'

                if len(conditions) > FilterValidationService.MAX_GROUP_CONDITIONS:
                    return (
                        False,
                        f'Group {group_index} has too many conditions. '
                        f'Maximum {FilterValidationService.MAX_GROUP_CONDITIONS} allowed',
                    )

                for condition_index, filter_item in enumerate(conditions):
                    is_valid, error_message = FilterValidationService._validate_condition(
                        filter_item,
                        supported_operators,
                        f'Group {group_index} condition {condition_index}',
                    )
                    if not is_valid:
                        return False, error_message
        
        return True, None
