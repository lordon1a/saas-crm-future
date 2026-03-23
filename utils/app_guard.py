"""
App Guard Middleware - Checks if an app is installed and active in workspace
"""
from functools import wraps
from flask import abort, session
from models_crm import WorkspaceApp, db
import logging

logger = logging.getLogger(__name__)


def require_app(app_slug):
    """
    Decorator to check if an app is installed and active in the current workspace.
    
    Usage:
        @require_app('docgen')
        def my_endpoint():
            ...
    
    Args:
        app_slug: The slug of the app to check (e.g., 'docgen', 'sms')
    
    Raises:
        403: If the app is not installed or not active in the workspace
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                abort(401, description="Oturum açmanız gerekiyor")
            
            workspace_id = session.get('workspace_id')
            if not workspace_id:
                abort(401, description="Workspace context missing")
            
            # Check if app is installed and active
            installed = WorkspaceApp.query.filter_by(
                workspace_id=workspace_id,
                app_slug=app_slug,
                is_active=True
            ).first()
            
            if not installed:
                logger.warning(
                    f"Access denied: App '{app_slug}' not active for workspace {workspace_id}"
                )
                abort(403, description=f"'{app_slug}' uygulaması bu workspace'te aktif değil.")
            
            return f(*args, **kwargs)
        return decorated
    return decorator
