"""
Setup test data for development
Creates workspace, user, and basic CRM data
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import app, db
from models import User, Workspace
from werkzeug.security import generate_password_hash


def setup_test_data():
    """Setup basic test data"""
    with app.app_context():
        print("Setting up test data...")
        
        # Check if workspace exists
        workspace = Workspace.query.first()
        if not workspace:
            workspace = Workspace(company_name='Test Company')
            db.session.add(workspace)
            db.session.flush()
            print(f"✓ Created workspace: {workspace.company_name}")
        else:
            print(f"✓ Using existing workspace: {workspace.company_name}")
        
        # Check if user exists
        user = User.query.filter_by(email='admin@test.com').first()
        if not user:
            user = User(
                workspace_id=workspace.id,
                name='Admin User',
                email='admin@test.com',
                password_hash=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(user)
            print(f"✓ Created user: {user.email} (password: admin123)")
        else:
            print(f"✓ Using existing user: {user.email}")
        
        db.session.commit()
        print("\n✓ Test data setup complete!")
        print(f"\nWorkspace ID: {workspace.id}")
        print(f"User ID: {user.id}")
        print(f"\nYou can now run:")
        print("  python seed_crm_data.py")
        print("  python seed_tasks.py")


if __name__ == '__main__':
    setup_test_data()
