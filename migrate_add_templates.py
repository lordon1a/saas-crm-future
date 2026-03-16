"""
Migration script to add MessageTemplate table to existing database
"""
from app import app
from models import db

def migrate():
    with app.app_context():
        print("Creating MessageTemplate table...")
        try:
            # Create all tables (will only create missing ones)
            db.create_all()
            print("✓ Migration completed successfully!")
            print("  MessageTemplate table is now available")
        except Exception as e:
            print(f"✗ Migration failed: {e}")

if __name__ == '__main__':
    migrate()
