"""
Rate Limiting Utilities
Provides decorators for API rate limiting
"""
from functools import wraps
from flask import request, jsonify, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging

logger = logging.getLogger(__name__)


def get_user_identifier():
    """
    Get unique identifier for rate limiting.
    Priority: user_id > workspace_id > IP address
    """
    user_id = session.get('user_id')
    if user_id:
        return f'user:{user_id}'
    
    workspace_id = session.get('workspace_id')
    if workspace_id:
        return f'workspace:{workspace_id}'
    
    return get_remote_address()


def is_internal_request():
    """Check if request is from internal/trusted source"""
    # Socket.io requests
    if request.path.startswith('/socket.io'):
        return True
    
    # Localhost requests
    remote = request.remote_addr or ''
    if remote in ('127.0.0.1', 'localhost', '::1'):
        return True
    
    return False


# Rate limit configurations by endpoint type
RATE_LIMITS = {
    'auth': '10 per minute',           # Login, register
    'api_read': '100 per minute',      # GET requests
    'api_write': '50 per minute',      # POST, PUT, PATCH, DELETE
    'api_bulk': '10 per minute',       # Bulk operations
    'webhook': '1000 per hour',        # External webhooks
    'public_api': '60 per hour',       # Public API endpoints
    'export': '5 per minute',          # CSV/Excel exports
    'import': '3 per minute',          # CSV/Excel imports
}


def rate_limit(limit_key='api_read'):
    """
    Decorator for rate limiting endpoints
    
    Usage:
        @rate_limit('api_write')
        def create_contact():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Skip rate limiting for internal requests
            if is_internal_request():
                return f(*args, **kwargs)
            
            # Get rate limit for this endpoint type
            limit = RATE_LIMITS.get(limit_key, '100 per minute')
            
            # Log rate limit check
            identifier = get_user_identifier()
            logger.debug(f'Rate limit check: {identifier} - {limit_key} - {limit}')
            
            # Continue with request
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def get_rate_limit_for_method(method):
    """Get appropriate rate limit based on HTTP method"""
    if method in ('GET', 'HEAD', 'OPTIONS'):
        return 'api_read'
    elif method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        return 'api_write'
    else:
        return 'api_read'
