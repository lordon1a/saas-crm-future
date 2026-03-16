"""
Migration: Add Google Workspace Sync Tables
Adds EmailSync, EmailTracking, EmailTrackingClick, and CalendarSync tables
"""
from app import app
from models import db

def migrate():
    with app.app_context():
        print("Creating Google Workspace sync tables...")
        
        # Import models to register them
        from models_crm import EmailSync, EmailTracking, EmailTrackingClick, CalendarSync
        
        # Create tables
        db.create_all()
        
        print("✓ Google Workspace sync tables created successfully!")
        print("  - email_syncs")
        print("  - email_tracking")
        print("  - email_tracking_clicks")
        print("  - calendar_syncs")

if __name__ == '__main__':
    migrate()
