"""
Filter Validation Service
Validates filter configurations and workspace access
"""
import logging

logger = logging.getLogger(__name__)


class FilterValidationService:
    """Service for validating filter configurations and access"""
    
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
            from models import db, User, Workspace
            
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
        
        if 'filters' not in filters:
            return False, 'Filters must contain a "filters" key'
        
        if not isinstance(filters['filters'], list):
            return False, 'Filters must be a list'
        
        # Validate each filter
        for idx, filter_item in enumerate(filters['filters']):
            if not isinstance(filter_item, dict):
                return False, f'Filter {idx} must be a dictionary'
            
            if 'field' not in filter_item:
                return False, f'Filter {idx} missing "field" key'
            
            if 'operator' not in filter_item:
                return False, f'Filter {idx} missing "operator" key'
        
        return True, None
