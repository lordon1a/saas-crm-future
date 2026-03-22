"""
Migration: Add contact_id column to Deal model
Date: 2026-03-22
Description: Adds optional primary contact link for deals
"""

import os
import sys

from sqlalchemy import text

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def upgrade(db):
    """Add contact_id column and index to deals table."""
    print("Adding contact_id column to deals table...")
    inspector = db.inspect(db.engine)
    columns = [col["name"] for col in inspector.get_columns("deals")]

    with db.engine.connect() as conn:
        if "contact_id" not in columns:
            conn.execute(text("ALTER TABLE deals ADD COLUMN contact_id INTEGER"))
            print("OK: contact_id column added")
        else:
            print("OK: contact_id column already exists")

        indexes = [idx["name"] for idx in inspector.get_indexes("deals")]
        if "idx_deals_contact_id" not in indexes:
            conn.execute(text("CREATE INDEX idx_deals_contact_id ON deals(contact_id)"))
            print("OK: idx_deals_contact_id index added")
        else:
            print("OK: idx_deals_contact_id index already exists")

        conn.commit()


def downgrade(db):
    """Remove contact_id column from deals table."""
    print("Removing contact_id column from deals table...")
    with db.engine.connect() as conn:
        conn.execute(text("DROP INDEX IF EXISTS idx_deals_contact_id"))
        conn.execute(text("ALTER TABLE deals DROP COLUMN contact_id"))
        conn.commit()
    print("OK: contact_id column removed")


if __name__ == "__main__":
    from app import app, db

    with app.app_context():
        if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
            downgrade(db)
        else:
            upgrade(db)
