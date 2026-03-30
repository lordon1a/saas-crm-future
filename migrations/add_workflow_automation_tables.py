"""
Migration: Add Workflow Automation Tables
=========================================
Creates the following tables:
- workflow_automations
- workflow_conditions
- workflow_actions
- workflow_executions
- workflow_execution_queue

Run: python migrations/add_workflow_automation_tables.py
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
    with app.app_context():
        # Check if tables already exist
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        table_name = 'workflow_automations'
        if table_name in existing_tables:
            print(f"✓ Table '{table_name}' already exists, skipping...")
            return
        
        print("Creating workflow automation tables...")
        
        # Create workflow_automations table
        db.engine.execute("""
            CREATE TABLE workflow_automations (
                id SERIAL PRIMARY KEY,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                name VARCHAR(200) NOT NULL,
                description TEXT,
                is_active BOOLEAN DEFAULT TRUE NOT NULL,
                trigger_type VARCHAR(50) NOT NULL,
                trigger_config JSONB,
                condition_logic VARCHAR(10) DEFAULT 'AND' NOT NULL,
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                run_count INTEGER DEFAULT 0,
                last_run_at TIMESTAMP
            );
        """)
        print("  ✓ workflow_automations table created")
        
        # Create workflow_conditions table
        db.engine.execute("""
            CREATE TABLE workflow_conditions (
                id SERIAL PRIMARY KEY,
                workflow_id INTEGER NOT NULL REFERENCES workflow_automations(id) ON DELETE CASCADE,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                field_name VARCHAR(100) NOT NULL,
                operator VARCHAR(50) NOT NULL,
                value VARCHAR(500),
                order_index INTEGER DEFAULT 0 NOT NULL
            );
        """)
        print("  ✓ workflow_conditions table created")
        
        # Create workflow_actions table
        db.engine.execute("""
            CREATE TABLE workflow_actions (
                id SERIAL PRIMARY KEY,
                workflow_id INTEGER NOT NULL REFERENCES workflow_automations(id) ON DELETE CASCADE,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                action_type VARCHAR(50) NOT NULL,
                action_config JSONB,
                delay_minutes INTEGER DEFAULT 0 NOT NULL,
                order_index INTEGER DEFAULT 0 NOT NULL,
                created_by INTEGER REFERENCES users(id)
            );
        """)
        print("  ✓ workflow_actions table created")
        
        # Create workflow_executions table
        db.engine.execute("""
            CREATE TABLE workflow_executions (
                id SERIAL PRIMARY KEY,
                workflow_id INTEGER NOT NULL REFERENCES workflow_automations(id) ON DELETE CASCADE,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                entity_type VARCHAR(50),
                entity_id INTEGER,
                status VARCHAR(20) DEFAULT 'pending' NOT NULL,
                triggered_by VARCHAR(100),
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                error_message TEXT,
                actions_executed JSONB
            );
        """)
        print("  ✓ workflow_executions table created")
        
        # Create workflow_execution_queue table
        db.engine.execute("""
            CREATE TABLE workflow_execution_queue (
                id SERIAL PRIMARY KEY,
                workflow_id INTEGER NOT NULL REFERENCES workflow_automations(id) ON DELETE CASCADE,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                entity_type VARCHAR(50),
                entity_id INTEGER,
                action_id INTEGER REFERENCES workflow_actions(id) ON DELETE CASCADE,
                scheduled_at TIMESTAMP NOT NULL,
                executed_at TIMESTAMP,
                status VARCHAR(20) DEFAULT 'pending' NOT NULL
            );
        """)
        print("  ✓ workflow_execution_queue table created")
        
        # Create indexes
        print("Creating indexes...")
        
        db.engine.execute("""
            CREATE INDEX idx_workflow_workspace_active 
            ON workflow_automations(workspace_id, is_active);
        """)
        print("  ✓ idx_workflow_workspace_active")
        
        db.engine.execute("""
            CREATE INDEX idx_workflow_automations_lookup
            ON workflow_automations(workspace_id, trigger_type, is_active);
        """)
        print("  ✓ idx_workflow_automations_lookup (composite index for trigger_event queries)")
        
        db.engine.execute("""
            CREATE INDEX idx_workflow_condition_workflow 
            ON workflow_conditions(workflow_id);
        """)
        print("  ✓ idx_workflow_condition_workflow")
        
        db.engine.execute("""
            CREATE INDEX idx_workflow_action_workflow 
            ON workflow_actions(workflow_id);
        """)
        print("  ✓ idx_workflow_action_workflow")
        
        db.engine.execute("""
            CREATE INDEX idx_execution_workflow 
            ON workflow_executions(workflow_id, started_at);
        """)
        print("  ✓ idx_execution_workflow")
        
        db.engine.execute("""
            CREATE INDEX idx_execution_entity 
            ON workflow_executions(entity_type, entity_id);
        """)
        print("  ✓ idx_execution_entity")
        
        db.engine.execute("""
            CREATE INDEX idx_queue_scheduled 
            ON workflow_execution_queue(scheduled_at, status);
        """)
        print("  ✓ idx_queue_scheduled")
        
        db.engine.execute("""
            CREATE INDEX idx_queue_workspace 
            ON workflow_execution_queue(workspace_id, status);
        """)
        print("  ✓ idx_queue_workspace")
        
        db.session.commit()
        print("\n✅ Migration completed successfully!")


def rollback_migration():
    """Rollback the migration"""
    with app.app_context():
        print("Rolling back migration...")
        
        db.engine.execute("DROP TABLE IF EXISTS workflow_execution_queue CASCADE;")
        db.engine.execute("DROP TABLE IF EXISTS workflow_executions CASCADE;")
        db.engine.execute("DROP TABLE IF EXISTS workflow_actions CASCADE;")
        db.engine.execute("DROP TABLE IF EXISTS workflow_conditions CASCADE;")
        db.engine.execute("DROP TABLE IF EXISTS workflow_automations CASCADE;")
        
        db.session.commit()
        print("✅ Rollback completed!")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--rollback':
        rollback_migration()
    else:
        run_migration()
