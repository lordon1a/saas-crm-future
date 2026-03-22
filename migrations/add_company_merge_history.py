"""
Migration: Create company_merge_history table
Date: 2026-03-22
Description: Adds audit table for company merge operations
"""

import os
import sys

from sqlalchemy import text

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def upgrade(db):
    """Create company_merge_history table and indexes."""
    print("Creating company_merge_history table...")
    inspector = db.inspect(db.engine)
    tables = inspector.get_table_names()

    with db.engine.connect() as conn:
        if 'company_merge_history' not in tables:
            conn.execute(text("""
                CREATE TABLE company_merge_history (
                    id INTEGER PRIMARY KEY,
                    workspace_id INTEGER NOT NULL,
                    primary_company_id INTEGER NOT NULL,
                    merged_company_id INTEGER NOT NULL,
                    merged_data_json TEXT NOT NULL,
                    merged_by INTEGER NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            print("OK: company_merge_history table created")
        else:
            print("OK: company_merge_history table already exists")

        indexes = [idx['name'] for idx in inspector.get_indexes('company_merge_history')] if 'company_merge_history' in inspector.get_table_names() else []
        if 'idx_company_merge_workspace' not in indexes:
            conn.execute(text("CREATE INDEX idx_company_merge_workspace ON company_merge_history(workspace_id)"))
            print("OK: idx_company_merge_workspace created")
        else:
            print("OK: idx_company_merge_workspace already exists")

        if 'idx_company_merge_primary' not in indexes:
            conn.execute(text("CREATE INDEX idx_company_merge_primary ON company_merge_history(primary_company_id)"))
            print("OK: idx_company_merge_primary created")
        else:
            print("OK: idx_company_merge_primary already exists")

        if 'idx_company_merge_merged' not in indexes:
            conn.execute(text("CREATE INDEX idx_company_merge_merged ON company_merge_history(merged_company_id)"))
            print("OK: idx_company_merge_merged created")
        else:
            print("OK: idx_company_merge_merged already exists")

        conn.commit()


def downgrade(db):
    """Drop company_merge_history table."""
    print("Dropping company_merge_history table...")
    with db.engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS company_merge_history"))
        conn.commit()
    print("OK: company_merge_history table dropped")


if __name__ == '__main__':
    from app import app, db

    with app.app_context():
        if len(sys.argv) > 1 and sys.argv[1] == 'downgrade':
            downgrade(db)
        else:
            upgrade(db)
