"""
Migration: Create deal_contacts table
Date: 2026-03-22
Description: Adds many-to-many stakeholder links between deals and contacts
"""

import os
import sys

from sqlalchemy import text

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def upgrade(db):
    """Create deal_contacts table and backfill from deals.contact_id."""
    print("Creating deal_contacts table...")
    inspector = db.inspect(db.engine)
    tables = inspector.get_table_names()

    with db.engine.connect() as conn:
        if "deal_contacts" not in tables:
            conn.execute(text("""
                CREATE TABLE deal_contacts (
                    id INTEGER PRIMARY KEY,
                    workspace_id INTEGER NOT NULL,
                    deal_id INTEGER NOT NULL,
                    contact_id INTEGER NOT NULL,
                    role VARCHAR(100),
                    is_primary BOOLEAN NOT NULL DEFAULT 0,
                    added_by INTEGER,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME,
                    CONSTRAINT uix_deal_contact UNIQUE (deal_id, contact_id)
                )
            """))
            print("OK: deal_contacts table created")
        else:
            print("OK: deal_contacts table already exists")

        indexes = [idx["name"] for idx in inspector.get_indexes("deal_contacts")] if "deal_contacts" in inspector.get_table_names() else []
        if "idx_deal_contacts_workspace_deal" not in indexes:
            conn.execute(text("CREATE INDEX idx_deal_contacts_workspace_deal ON deal_contacts(workspace_id, deal_id)"))
            print("OK: idx_deal_contacts_workspace_deal created")
        else:
            print("OK: idx_deal_contacts_workspace_deal already exists")

        if "idx_deal_contacts_contact_id" not in indexes:
            conn.execute(text("CREATE INDEX idx_deal_contacts_contact_id ON deal_contacts(contact_id)"))
            print("OK: idx_deal_contacts_contact_id created")
        else:
            print("OK: idx_deal_contacts_contact_id already exists")

        # Backfill existing primary contact values from deals.contact_id
        deal_rows = conn.execute(text("""
            SELECT id, workspace_id, contact_id
            FROM deals
            WHERE contact_id IS NOT NULL
        """)).fetchall()

        inserted = 0
        for row in deal_rows:
            exists = conn.execute(text("""
                SELECT 1 FROM deal_contacts
                WHERE deal_id = :deal_id AND contact_id = :contact_id
                LIMIT 1
            """), {'deal_id': row.id, 'contact_id': row.contact_id}).fetchone()
            if exists:
                continue
            conn.execute(text("""
                INSERT INTO deal_contacts (workspace_id, deal_id, contact_id, is_primary, created_at, updated_at)
                VALUES (:workspace_id, :deal_id, :contact_id, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """), {
                'workspace_id': row.workspace_id,
                'deal_id': row.id,
                'contact_id': row.contact_id,
            })
            inserted += 1

        conn.commit()
        print(f"OK: Backfilled {inserted} stakeholder rows from deals.contact_id")


def downgrade(db):
    """Drop deal_contacts table."""
    print("Dropping deal_contacts table...")
    with db.engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS deal_contacts"))
        conn.commit()
    print("OK: deal_contacts table dropped")


if __name__ == "__main__":
    from app import app, db

    with app.app_context():
        if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
            downgrade(db)
        else:
            upgrade(db)
