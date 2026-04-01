"""
Migration: Add Workflow Re-enrollment Control
==============================================
Adds re_enrollment_mode to workflow_automations and creates workflow_enrollments table.

Changes:
1. Add re_enrollment_mode column to workflow_automations table
   - Values: 'always' | 'never' | 'once_per_day' | 'once_per_week'
   - Default: 'always'

2. Create workflow_enrollments table
   - Tracks which entities are enrolled in which workflows
   - Prevents re-enrollment spam based on re_enrollment_mode
   - Composite index on (workflow_id, entity_id, entity_type)

Run: python migrations/add_workflow_enrollment.py
Or: flask db upgrade (if using Flask-Migrate)
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from datetime import datetime


def run_migration():
    """Run the migration"""
    from sqlalchemy import inspect, text
    with app.app_context():
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        # 1. Add re_enrollment_mode column to workflow_automations
        print("Adding re_enrollment_mode column to workflow_automations...")
        
        # Check if column already exists
        columns = inspector.get_columns('workflow_automations')
        column_names = [c['name'] for c in columns]
        
        if 're_enrollment_mode' not in column_names:
            db.session.execute(text("""
                ALTER TABLE workflow_automations 
                ADD COLUMN re_enrollment_mode VARCHAR(30) DEFAULT 'always' NOT NULL;
            """))
            print("  - re_enrollment_mode column added to workflow_automations")
        else:
            print("  - re_enrollment_mode column already exists, skipping...")
        
        # 2. Create workflow_enrollments table
        table_name = 'workflow_enrollments'
        if table_name not in existing_tables:
            print("Creating workflow_enrollments table...")
            
            db.session.execute(text("""
                CREATE TABLE workflow_enrollments (
                    id SERIAL PRIMARY KEY,
                    workflow_id INTEGER NOT NULL REFERENCES workflow_automations(id) ON DELETE CASCADE,
                    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                    entity_id INTEGER NOT NULL,
                    entity_type VARCHAR(50) NOT NULL,
                    enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    completed_at TIMESTAMP,
                    status VARCHAR(20) DEFAULT 'running' NOT NULL
                );
            """))
            print("  - workflow_enrollments table created")
            
            # Create indexes
            print("Creating indexes...")
            
            db.session.execute(text("""
                CREATE INDEX idx_workflow_enrollment_workflow_entity
                ON workflow_enrollments(workflow_id, entity_id, entity_type);
            """))
            print("  - idx_workflow_enrollment_workflow_entity (composite)")
            
            db.session.execute(text("""
                CREATE INDEX idx_workflow_enrollment_workspace
                ON workflow_enrollments(workspace_id, status);
            """))
            print("  - idx_workflow_enrollment_workspace")
            
            db.session.execute(text("""
                CREATE INDEX idx_workflow_enrollment_entity
                ON workflow_enrollments(entity_type, entity_id, enrolled_at);
            """))
            print("  - idx_workflow_enrollment_entity")
            
        else:
            print("  - workflow_enrollments table already exists, skipping...")
        
        db.session.commit()
        print("\n[OK] Migration completed successfully!")


def rollback_migration():
    """Rollback the migration"""
    from sqlalchemy import text
    with app.app_context():
        print("Rolling back migration...")
        
        # Drop indexes first
        db.session.execute(text("DROP INDEX IF EXISTS idx_workflow_enrollment_entity;"))
        db.session.execute(text("DROP INDEX IF EXISTS idx_workflow_enrollment_workspace;"))
        db.session.execute(text("DROP INDEX IF EXISTS idx_workflow_enrollment_workflow_entity;"))
        
        # Drop table
        db.session.execute(text("DROP TABLE IF EXISTS workflow_enrollments CASCADE;"))
        
        # Remove column from workflow_automations
        db.session.execute(text("ALTER TABLE workflow_automations DROP COLUMN IF EXISTS re_enrollment_mode;"))
        
        db.session.commit()
        print("[OK] Rollback completed!")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--rollback':
        rollback_migration()
    else:
        run_migration()
