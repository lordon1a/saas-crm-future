"""
Add canvas_data column to workflow_automations table
This stores ReactFlow node positions and edges for visual workflow builder
"""
from models import db
from sqlalchemy import text

def upgrade():
    """Add canvas_data column"""
    try:
        # SQLite
        db.session.execute(text('ALTER TABLE workflow_automations ADD COLUMN canvas_data TEXT'))
        db.session.commit()
        print("✓ Added canvas_data column to workflow_automations")
    except Exception as e:
        print(f"Note: {e}")
        db.session.rollback()

def downgrade():
    """Remove canvas_data column"""
    # SQLite doesn't support DROP COLUMN easily, so we skip it
    print("Downgrade not supported for SQLite")
