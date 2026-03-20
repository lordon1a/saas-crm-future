from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, PasswordResetToken
from datetime import datetime, timedelta
import secrets
import hashlib

class AuthManager:
    @staticmethod
    def hash_password(password):
        """Hash a password using werkzeug's pbkdf2:sha256"""
        return generate_password_hash(password, method='pbkdf2:sha256')
    
    @staticmethod
    def verify_password(password_hash, password):
        """Verify a password against its hash"""
        return check_password_hash(password_hash, password)
    
    @staticmethod
    def authenticate_user(email, password):
        """Authenticate a user by email and password"""
        user = User.query.filter_by(email=email).first()
        if user and AuthManager.verify_password(user.password_hash, password):
            return user
        return None
    
    @staticmethod
    def create_user(name, email, password, role='agent'):
        """Create a new user with hashed password"""
        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            raise ValueError(f"User with email {email} already exists")
        
        # Validate role
        if role not in ['admin', 'agent']:
            raise ValueError(f"Invalid role: {role}. Must be 'admin' or 'agent'")
        
        password_hash = AuthManager.hash_password(password)
        user = User(name=name, email=email, password_hash=password_hash, role=role)
        
        db.session.add(user)
        db.session.commit()
        
        return user

    @staticmethod
    def create_password_reset_token(email, ip_address=None):
        """
        Create a password reset token for user with given email.
        Returns token string if successful, None if user not found.
        """
        user = User.query.filter_by(email=email.strip().lower()).first()
        if not user:
            # Don't reveal if email exists or not (security best practice)
            return None
        
        # Generate secure random token
        raw_token = secrets.token_urlsafe(32)
        # Hash token for storage (additional security layer)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        
        # Invalidate any existing unused tokens for this user
        PasswordResetToken.query.filter_by(
            user_id=user.id,
            used_at=None
        ).update({'used_at': datetime.utcnow()})
        
        # Create new token (expires in 1 hour)
        reset_token = PasswordResetToken(
            user_id=user.id,
            token=token_hash,
            expires_at=datetime.utcnow() + timedelta(hours=1),
            ip_address=ip_address
        )
        
        db.session.add(reset_token)
        db.session.commit()
        
        # Return raw token (not hash) to send in email
        return raw_token
    
    @staticmethod
    def verify_reset_token(token):
        """
        Verify password reset token and return user if valid.
        Returns None if token is invalid, expired, or already used.
        """
        if not token:
            return None
        
        # Hash the provided token to match stored hash
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        reset_token = PasswordResetToken.query.filter_by(
            token=token_hash,
            used_at=None
        ).first()
        
        if not reset_token:
            return None
        
        # Check if expired
        if reset_token.expires_at < datetime.utcnow():
            return None
        
        return User.query.get(reset_token.user_id)
    
    @staticmethod
    def reset_password_with_token(token, new_password):
        """
        Reset user password using valid token.
        Returns True if successful, False otherwise.
        """
        user = AuthManager.verify_reset_token(token)
        if not user:
            return False
        
        # Hash the provided token to find the record
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Update password
        user.password_hash = AuthManager.hash_password(new_password)
        
        # Mark token as used
        reset_token = PasswordResetToken.query.filter_by(
            token=token_hash,
            used_at=None
        ).first()
        
        if reset_token:
            reset_token.used_at = datetime.utcnow()
        
        db.session.commit()
        return True
