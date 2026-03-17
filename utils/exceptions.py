"""
Custom Exception Classes
Provides structured error handling across the application
"""


class AppException(Exception):
    """Base exception class for application errors"""
    status_code = 500
    
    def __init__(self, message, status_code=None, payload=None):
        super().__init__()
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload
    
    def to_dict(self):
        rv = dict(self.payload or ())
        rv['error'] = self.message
        return rv


class ValidationError(AppException):
    """Raised when input validation fails"""
    status_code = 400


class NotFoundError(AppException):
    """Raised when a resource is not found"""
    status_code = 404


class UnauthorizedError(AppException):
    """Raised when authentication is required"""
    status_code = 401


class ForbiddenError(AppException):
    """Raised when user lacks permission"""
    status_code = 403


class ConflictError(AppException):
    """Raised when there's a conflict (e.g., duplicate resource)"""
    status_code = 409


class RateLimitError(AppException):
    """Raised when rate limit is exceeded"""
    status_code = 429


class ExternalServiceError(AppException):
    """Raised when external service (Meta API, Google, etc.) fails"""
    status_code = 502
