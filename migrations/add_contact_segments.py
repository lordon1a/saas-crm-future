"""
Migration: Add Contact Segments

Creates tables for dynamic segment system:
- ContactSegment: Segment definitions with filter criteria
- SegmentMembership: Tracks which contacts belong to which segments

Run with: python migrations/add_contact_segments.py
"""
import sys
from datetime import datetime

def upgrade():
    from app import db
    from models_crm import ContactSegment, SegmentMembership
    
    # Create tables
    db.create_all()
    
    print("[OK] Contact segments tables created successfully")

def downgrade():
    from app import db
    
    # Drop tables in correct order (child first due to foreign key)
    try:
        db.session.execute(db.text("DROP TABLE IF EXISTS segment_memberships"))
        db.session.execute(db.text("DROP TABLE IF EXISTS contact_segments"))
        db.session.commit()
        print("[OK] Contact segments tables dropped")
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] Failed to drop tables: {e}")

if __name__ == '__main__':
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from app import app
    with app.app_context():
        if len(sys.argv) > 1 and sys.argv[1] == 'downgrade':
            downgrade()
        else:
            upgrade()
