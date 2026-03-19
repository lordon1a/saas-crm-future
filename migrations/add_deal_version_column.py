"""
Migration: Add version column to Deal model for optimistic locking
Date: 2026-03-18
Description: Adds version column to prevent race conditions in concurrent deal updates
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text


def upgrade(db):
    """Add version column to deals table"""
    print("Adding version column to deals table...")
    
    # Check if column already exists
    inspector = db.inspect(db.engine)
    columns = [col['name'] for col in inspector.get_columns('deals')]
    
    if 'version' not in columns:
        # Add version column with default value 0
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE deals ADD COLUMN version INTEGER NOT NULL DEFAULT 0'))
            conn.commit()
        print("✓ Version column added successfully")
    else:
        print("✓ Version column already exists")


def downgrade(db):
    """Remove version column from deals table"""
    print("Removing version column from deals table...")
    
    with db.engine.connect() as conn:
        conn.execute(text('ALTER TABLE deals DROP COLUMN version'))
        conn.commit()
    print("✓ Version column removed successfully")


if __name__ == '__main__':
    from app import app, db
    
    with app.app_context():
        if len(sys.argv) > 1 and sys.argv[1] == 'downgrade':
            downgrade(db)
        else:
            upgrade(db)
