"""
Seed Demo User for Production
Creates a demo admin account if it doesn't exist
"""
from app import app, db
from models import User, Workspace
from services.auth_manager import AuthManager

def seed_demo_user():
    with app.app_context():
        print("🌱 Seeding demo user...")
        
        # Check if demo workspace exists
        demo_workspace = Workspace.query.filter_by(company_name='Demo Company').first()
        
        if not demo_workspace:
            print("Creating demo workspace...")
            demo_workspace = Workspace(company_name='Demo Company')
            db.session.add(demo_workspace)
            db.session.flush()
        
        # Check if demo user exists
        demo_user = User.query.filter_by(email='admin@example.com').first()
        
        if not demo_user:
            print("Creating demo user: admin@example.com / admin123")
            password_hash = AuthManager.hash_password('admin123')
            demo_user = User(
                workspace_id=demo_workspace.id,
                name='Demo Admin',
                email='admin@example.com',
                password_hash=password_hash,
                role='admin'
            )
            db.session.add(demo_user)
            db.session.commit()
            print("✅ Demo user created successfully!")
            print("   Email: admin@example.com")
            print("   Password: admin123")
        else:
            print("✓ Demo user already exists")
            print("   Email: admin@example.com")
            print("   Password: admin123")

if __name__ == '__main__':
    seed_demo_user()
