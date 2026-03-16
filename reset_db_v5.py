import os
from app import app
from models import db, Workspace, User
from werkzeug.security import generate_password_hash

with app.app_context():
    print("Dropping all tables...")
    db.drop_all()
    print("Creating all tables...")
    db.create_all()
    
    print("Adding demo workspaces...")
    ws1 = Workspace(company_name='Ayse Butik', whatsapp_phone_number_id='123456789')
    ws2 = Workspace(company_name='Sleekflow Demo', whatsapp_phone_number_id='987654321')
    db.session.add_all([ws1, ws2])
    db.session.commit()
    
    print("Adding demo users...")
    u1 = User(workspace_id=ws1.id, name='Admin Ayse', email='admin@ayse.com', password_hash=generate_password_hash('admin123'), role='admin')
    u2 = User(workspace_id=ws2.id, name='Sleek Admin', email='admin@sleek.com', password_hash=generate_password_hash('admin123'), role='admin')
    db.session.add_all([u1, u2])
    db.session.commit()
    
    print("DB V5 Multi-Tenant Migration Completed Successfully.")
