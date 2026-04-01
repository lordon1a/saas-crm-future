"""
Migration: Add workflow versioning and usage tracking tables
=============================================================
Adds:
- workflow_versions: Version history for workflows
- workflow_usage: Monthly usage tracking for credits/limits

Run: python migrations/add_workflow_versioning_tables.py
"""
import sqlite3
import os
import sys

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'crm.db')


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if tables already exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='workflow_versions'")
    if cursor.fetchone():
        print("workflow_versions table already exists, skipping")
    else:
        cursor.execute("""
            CREATE TABLE workflow_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id INTEGER NOT NULL,
                workspace_id INTEGER NOT NULL,
                version_number INTEGER NOT NULL DEFAULT 1,
                name VARCHAR(200) NOT NULL,
                description TEXT,
                trigger_type VARCHAR(50) NOT NULL,
                trigger_config TEXT,
                condition_logic VARCHAR(10) DEFAULT 'AND',
                canvas_data TEXT,
                status VARCHAR(20) NOT NULL DEFAULT 'draft',
                created_by INTEGER,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                published_at TIMESTAMP,
                FOREIGN KEY (workflow_id) REFERENCES workflow_automations(id),
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        """)
        cursor.execute("CREATE INDEX idx_workflow_versions_lookup ON workflow_versions(workflow_id, workspace_id)")
        cursor.execute("CREATE INDEX idx_workflow_versions_status ON workflow_versions(status)")
        print("  [OK] workflow_versions table created")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='workflow_usage'")
    if cursor.fetchone():
        print("workflow_usage table already exists, skipping")
    else:
        cursor.execute("""
            CREATE TABLE workflow_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                total_executions INTEGER NOT NULL DEFAULT 0,
                total_actions INTEGER NOT NULL DEFAULT 0,
                total_errors INTEGER NOT NULL DEFAULT 0,
                total_duration_ms BIGINT NOT NULL DEFAULT 0,
                action_breakdown TEXT,
                max_executions INTEGER NOT NULL DEFAULT 10000,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            )
        """)
        cursor.execute("CREATE INDEX idx_workflow_usage_lookup ON workflow_usage(workspace_id, year, month)")
        print("  [OK] workflow_usage table created")
    
    conn.commit()
    conn.close()
    print("\nMigration complete!")


if __name__ == '__main__':
    migrate()
