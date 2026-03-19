from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User

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
