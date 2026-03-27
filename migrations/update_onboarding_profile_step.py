"""
Migration: Add profile_setup to onboarding_progress table
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db
from app import app

from sqlalchemy import text

def upgrade():
    """Add profile_setup column to onboarding_progress table"""
    with app.app_context():
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE onboarding_progress ADD COLUMN profile_setup BOOLEAN DEFAULT 0"))
                conn.commit()
            print("✅ Added profile_setup column to onboarding_progress table")
        except Exception as e:
            print(f"❌ Error adding column: {e}")

if __name__ == '__main__':
    upgrade()
