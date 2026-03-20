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
