# Role-based permission system for team member management

from functools import wraps
from flask import jsonify, session
from models import User, db

# Define role hierarchy and permissions
ROLE_PERMISSIONS = {
    'owner': {
        'manage_team': True,
        'manage_billing': True,
        'delete_workspace': True,
        'manage_crm': True,
        'assign_entities': True,
        'view_all': True,
        'edit_all': True,
        'transfer_ownership': True,
        'change_roles': True,
        'remove_members': True
    },
    'admin': {
        'manage_team': True,
        'manage_billing': False,
        'delete_workspace': False,
        'manage_crm': True,
        'assign_entities': True,
        'view_all': True,
        'edit_all': True,
        'transfer_ownership': False,
        'change_roles': False,  # Can only manage member/viewer roles
        'remove_members': True  # Can only remove member/viewer roles
    },
    'member': {
        'manage_team': False,
        'manage_billing': False,
        'delete_workspace': False,
        'manage_crm': True,
        'assign_entities': True,  # Can assign own entities
        'view_all': True,
        'edit_all': False,  # Can only edit assigned entities
        'transfer_ownership': False,
        'change_roles': False,
        'remove_members': False
    },
    'viewer': {
        'manage_team': False,
        'manage_billing': False,
        'delete_workspace': False,
        'manage_crm': False,
        'assign_entities': False,
        'view_all': True,
        'edit_all': False,
        'transfer_ownership': False,
        'change_roles': False,
        'remove_members': False
    }
}


def check_permission(user, permission):
    """
    Check if a user has a specific permission based on their role.
    
    Args:
        user: User object
        permission: Permission string (e.g., 'manage_team', 'assign_entities')
    
    Returns:
        bool: True if user has permission, False otherwise
    """
    if not user or not user.is_active:
        return False
    
    role = user.role
    if role not in ROLE_PERMISSIONS:
        return False
    
    return ROLE_PERMISSIONS[role].get(permission, False)


def require_permission(permission):
    """
    Decorator to require a specific permission for a route.
    
    Usage:
        @require_permission('manage_team')
        def my_route():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get('user_id')
            if not user_id:
                return jsonify({'error': 'Authentication required'}), 401
            
            user = User.query.get(user_id)
            if not user or not user.is_active:
                return jsonify({'error': 'User not found or inactive'}), 403
            
            if not check_permission(user, permission):
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_role(*allowed_roles):
    """
    Decorator to require specific roles for a route.
    
    Usage:
        @require_role('owner', 'admin')
        def my_route():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get('user_id')
            if not user_id:
                return jsonify({'error': 'Authentication required'}), 401
            
            user = User.query.get(user_id)
            if not user or not user.is_active:
                return jsonify({'error': 'User not found or inactive'}), 403
            
            if user.role not in allowed_roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def can_manage_member(current_user, target_user):
    """
    Check if current user can manage (change role/remove) target user.
    
    Args:
        current_user: User object performing the action
        target_user: User object being managed
    
    Returns:
        bool: True if current user can manage target user
    """
    if not current_user or not target_user:
        return False
    
    # Can't manage yourself
    if current_user.id == target_user.id:
        return False
    
    # Can't manage users from different workspaces
    if current_user.workspace_id != target_user.workspace_id:
        return False
    
    # Owner can manage anyone except themselves
    if current_user.role == 'owner':
        return target_user.role != 'owner'
    
    # Admin can manage member and viewer roles only
    if current_user.role == 'admin':
        return target_user.role in ['member', 'viewer']
    
    # Member and viewer can't manage anyone
    return False


def can_assign_entity(user, entity):
    """
    Check if user can assign an entity to team members.
    
    Args:
        user: User object
        entity: CRM entity object (Contact, Company, Deal, Task, Conversation)
    
    Returns:
        bool: True if user can assign the entity
    """
    if not user or not user.is_active:
        return False
    
    # Owner and admin can assign any entity
    if user.role in ['owner', 'admin']:
        return True
    
    # Member can assign entities they own or are assigned to
    if user.role == 'member':
        # Check if entity is assigned to user or unassigned
        assigned_to = getattr(entity, 'assigned_to', None) or getattr(entity, 'owner_id', None) or getattr(entity, 'assignee_id', None)
        return assigned_to is None or assigned_to == user.id
    
    # Viewer can't assign
    return False


# ============================================================================
# ENTITY-LEVEL ACCESS CONTROL (IDOR Protection)
# ============================================================================

def get_current_user_from_session():
    """Get current authenticated user from session"""
    user_id = session.get('user_id')
    workspace_id = session.get('workspace_id')
    
    if not user_id or not workspace_id:
        return None
    
    return User.query.filter_by(id=user_id, workspace_id=workspace_id).first()


def check_workspace_access(user, workspace_id):
    """
    Verify user belongs to the workspace (CRITICAL for multi-tenant isolation)
    
    Args:
        user: User object
        workspace_id: Workspace ID to check
    
    Returns:
        bool: True if user has access
    """
    if not user or not workspace_id:
        return False
    
    return user.workspace_id == workspace_id


def check_entity_access(user, entity, action='read'):
    """
    Central function to check if user has permission to access an entity.
    This is the CORE IDOR protection mechanism.
    
    Args:
        user: Current user object
        entity: Entity object (Contact, Company, Deal, Task, etc.)
        action: 'read', 'write', 'delete'
    
    Returns:
        bool: True if user has access
    
    Security Rules:
        1. Workspace isolation (CRITICAL): User can only access entities in their workspace
        2. Role-based access: owner/admin can access all, member/viewer have restrictions
        3. Ownership check: Users can access entities assigned to them
        4. Team visibility: Managers can access their team's entities
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not user or not entity:
        return False
    
    # RULE 1: Workspace isolation check (CRITICAL - prevents cross-tenant access)
    if hasattr(entity, 'workspace_id'):
        if entity.workspace_id != user.workspace_id:
            logger.warning(
                f"SECURITY: Cross-workspace access attempt blocked - "
                f"user {user.id} (workspace {user.workspace_id}) "
                f"tried to access entity in workspace {entity.workspace_id}"
            )
            return False
    
    # RULE 2: Owner and admin can access everything in their workspace
    if user.role in ['owner', 'admin']:
        return True
    
    # RULE 3: For write/delete actions, require ownership or higher privileges
    if action in ['write', 'delete']:
        # Check various ownership fields
        owner_fields = ['owner_id', 'assignee_id', 'assigned_to', 'created_by']
        
        for field in owner_fields:
            if hasattr(entity, field):
                field_value = getattr(entity, field)
                if field_value == user.id:
                    return True
        
        # Member role cannot write/delete entities they don't own
        if user.role == 'member':
            logger.info(
                f"Access denied: member user {user.id} attempted {action} "
                f"on entity they don't own"
            )
            return False
        
        # Viewer role cannot write/delete anything
        if user.role == 'viewer':
            return False
    
    # RULE 4: For read action, check visibility based on role
    if action == 'read':
        # Member can read entities assigned to them or unassigned
        if user.role == 'member':
            owner_fields = ['owner_id', 'assignee_id', 'assigned_to']
            
            for field in owner_fields:
                if hasattr(entity, field):
                    field_value = getattr(entity, field)
                    # Can read if assigned to them or unassigned
                    if field_value is None or field_value == user.id:
                        return True
            
            # If entity has no ownership field, allow read (e.g., tags, pipelines)
            if not any(hasattr(entity, field) for field in owner_fields):
                return True
            
            # Entity is assigned to someone else
            return False
        
        # Viewer can read all in workspace (read-only role)
        if user.role == 'viewer':
            return True
    
    # Default deny
    return False


def require_entity_access(entity_getter, action='read'):
    """
    Decorator to enforce entity-level access control on endpoints.
    This prevents IDOR vulnerabilities by checking ownership before allowing access.
    
    Usage:
        @require_entity_access(lambda: Deal.query.get(deal_id), action='write')
        def update_deal(deal_id):
            # Access is automatically checked
            pass
    
    Args:
        entity_getter: Function that returns the entity to check
        action: 'read', 'write', 'delete'
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            import logging
            logger = logging.getLogger(__name__)
            
            user = get_current_user_from_session()
            
            if not user:
                return jsonify({'error': 'Authentication required'}), 401
            
            # Get entity using the provided getter function
            try:
                entity = entity_getter()
            except Exception as e:
                logger.error(f"Error getting entity: {e}")
                return jsonify({'error': 'Invalid request'}), 400
            
            if not entity:
                return jsonify({'error': 'Resource not found'}), 404
            
            # Check access
            if not check_entity_access(user, entity, action):
                logger.warning(
                    f"SECURITY: Access denied - user {user.id} ({user.role}) "
                    f"attempted {action} on {type(entity).__name__} {entity.id}"
                )
                return jsonify({'error': 'Access denied to this resource'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_accessible_entities_query(user, entity_class, base_query=None):
    """
    Filter a query to only return entities the user can access.
    Use this for list endpoints to prevent IDOR enumeration.
    
    Args:
        user: Current user object
        entity_class: SQLAlchemy model class (Contact, Company, Deal, etc.)
        base_query: Optional base query to filter (if None, creates new query)
    
    Returns:
        SQLAlchemy query filtered by access rules
    
    Usage:
        query = get_accessible_entities_query(user, Deal)
        deals = query.filter(Deal.status == 'open').all()
    """
    if base_query is None:
        base_query = entity_class.query
    
    # Always filter by workspace (CRITICAL)
    base_query = base_query.filter_by(workspace_id=user.workspace_id)
    
    # Owner and admin can see all in workspace
    if user.role in ['owner', 'admin']:
        return base_query
    
    # Member can only see entities assigned to them
    if user.role == 'member':
        # Try different ownership field names
        if hasattr(entity_class, 'assigned_to'):
            return base_query.filter(
                db.or_(
                    entity_class.assigned_to == user.id,
                    entity_class.assigned_to == None
                )
            )
        elif hasattr(entity_class, 'assignee_id'):
            return base_query.filter(
                db.or_(
                    entity_class.assignee_id == user.id,
                    entity_class.assignee_id == None
                )
            )
        elif hasattr(entity_class, 'owner_id'):
            return base_query.filter(
                db.or_(
                    entity_class.owner_id == user.id,
                    entity_class.owner_id == None
                )
            )
    
    # Viewer can see all (read-only)
    if user.role == 'viewer':
        return base_query
    
    # Default: return base query
    return base_query
