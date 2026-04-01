"""
Migration: add_contact_ads_fields
Adds LinkedIn/Ads attribution fields to contacts.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from sqlalchemy import text


def _has_column_sqlite(table_name, column_name):
    rows = db.session.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _has_column_postgres(table_name, column_name):
    row = db.session.execute(text("""
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = :table_name AND column_name = :column_name
    """), {'table_name': table_name, 'column_name': column_name}).fetchone()
    return bool(row)


def _add_column_if_missing(table_name, column_name, ddl):
    is_sqlite = str(app.config.get('SQLALCHEMY_DATABASE_URI', '')).startswith('sqlite')
    exists = _has_column_sqlite(table_name, column_name) if is_sqlite else _has_column_postgres(table_name, column_name)
    if not exists:
        db.session.execute(text(ddl))


def upgrade():
    with app.app_context():
        _add_column_if_missing('contacts', 'utm_source', "ALTER TABLE contacts ADD COLUMN utm_source VARCHAR(120)")
        _add_column_if_missing('contacts', 'utm_medium', "ALTER TABLE contacts ADD COLUMN utm_medium VARCHAR(120)")
        _add_column_if_missing('contacts', 'utm_campaign', "ALTER TABLE contacts ADD COLUMN utm_campaign VARCHAR(180)")
        _add_column_if_missing('contacts', 'utm_content', "ALTER TABLE contacts ADD COLUMN utm_content VARCHAR(180)")
        _add_column_if_missing('contacts', 'gclid', "ALTER TABLE contacts ADD COLUMN gclid VARCHAR(255)")
        _add_column_if_missing('contacts', 'fbclid', "ALTER TABLE contacts ADD COLUMN fbclid VARCHAR(255)")
        _add_column_if_missing('contacts', 'linkedin_url', "ALTER TABLE contacts ADD COLUMN linkedin_url VARCHAR(500)")
        _add_column_if_missing('contacts', 'linkedin_enriched_at', "ALTER TABLE contacts ADD COLUMN linkedin_enriched_at DATETIME")

        db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_contacts_utm_source ON contacts(utm_source)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_contacts_utm_medium ON contacts(utm_medium)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_contacts_utm_campaign ON contacts(utm_campaign)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_contacts_gclid ON contacts(gclid)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_contacts_fbclid ON contacts(fbclid)"))

        db.session.commit()
        print("[OK] add_contact_ads_fields migration completed")


def downgrade():
    # SQLite does not support dropping columns safely in-place.
    # Keeping data-safe no-op downgrade.
    with app.app_context():
        print("[INFO] add_contact_ads_fields downgrade skipped to preserve data")


if __name__ == '__main__':
    upgrade()
