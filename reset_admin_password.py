"""
Reset admin@example.com password to admin123
Run this on Render using: python reset_admin_password.py
"""
from app import app, db
from models import User
from services.auth_manager import AuthManager

with app.app_context():
    print("\n" + "="*60)
    print("PASSWORD RESET SCRIPT")
    print("="*60)
    
    # Find admin@example.com
    user = User.query.filter_by(email='admin@example.com').first()
    
    if not user:
        print("\n❌ User admin@example.com NOT FOUND!")
        print("Creating new user...")
        
        # Get first workspace or create one
        from models import Workspace
        workspace = Workspace.query.first()
        if not workspace:
            workspace = Workspace(company_name='Demo Company')
            db.session.add(workspace)
            db.session.flush()
        
        # Create user
        password_hash = AuthManager.hash_password('admin123')
        user = User(
            workspace_id=workspace.id,
            name='Demo Admin',
            email='admin@example.com',
            password_hash=password_hash,
            role='admin'
        )
        db.session.add(user)
        db.session.commit()
        print(f"✅ User created!")
    else:
        print(f"\n✅ User found: {user.email}")
        print(f"   Name: {user.name}")
        print(f"   Role: {user.role}")
        print(f"   Workspace ID: {user.workspace_id}")
        
        # Reset password
        print("\n🔄 Resetting password to 'admin123'...")
        user.password_hash = AuthManager.hash_password('admin123')
        db.session.commit()
        print("✅ Password reset successful!")
    
    # Verify
    print("\n🔍 Verifying password...")
    is_valid = AuthManager.verify_password(user.password_hash, 'admin123')
    print(f"   Password 'admin123' valid: {is_valid}")
    
    if is_valid:
        print("\n" + "="*60)
        print("SUCCESS! You can now login with:")
        print("   Email: admin@example.com")
        print("   Password: admin123")
        print("="*60 + "\n")
    else:
        print("\n❌ ERROR: Password verification failed!")
        print("="*60 + "\n")
