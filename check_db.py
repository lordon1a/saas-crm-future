"""
Database check script - Verify users in database
"""
from app import app, db
from models import User, Workspace

with app.app_context():
    print("\n" + "="*60)
    print("DATABASE CHECK")
    print("="*60)
    
    # Check workspaces
    workspaces = Workspace.query.all()
    print(f"\n📊 Total Workspaces: {len(workspaces)}")
    for ws in workspaces:
        print(f"   - ID: {ws.id}, Company: {ws.company_name}")
    
    # Check users
    users = User.query.all()
    print(f"\n👥 Total Users: {len(users)}")
    for user in users:
        print(f"   - ID: {user.id}, Email: {user.email}, Name: {user.name}, Role: {user.role}, Workspace: {user.workspace_id}")
    
    # Check specific demo user
    demo_user = User.query.filter_by(email='admin@example.com').first()
    if demo_user:
        print(f"\n✅ Demo user exists!")
        print(f"   Email: {demo_user.email}")
        print(f"   Name: {demo_user.name}")
        print(f"   Role: {demo_user.role}")
        print(f"   Workspace ID: {demo_user.workspace_id}")
        
        # Test password
        from services.auth_manager import AuthManager
        is_valid = AuthManager.verify_password(demo_user.password_hash, 'admin123')
        print(f"   Password 'admin123' valid: {is_valid}")
    else:
        print(f"\n❌ Demo user NOT found!")
    
    print("\n" + "="*60 + "\n")
