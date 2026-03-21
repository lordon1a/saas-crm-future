"""
Migration: Add advanced contact features
- Tags system (tags, contact_tags tables)
- Contact merge history (contact_merge_history table)
- Last activity tracking (last_activity_at column on contacts)

Run with: python -c "from migrations.add_contacts_advanced_features import upgrade; upgrade()"
"""


def upgrade():
    """Add tags, contact_tags, contact_merge_history tables and last_activity_at column"""
    from app import app, db
    from sqlalchemy import text

    with app.app_context():
        try:
            # 1. Add last_activity_at to contacts
            db.session.execute(text("""
                ALTER TABLE contacts
                ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMP
            """))
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_contacts_last_activity_at
                ON contacts(last_activity_at)
            """))

            # 2. Create tags table
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS tags (
                    id SERIAL PRIMARY KEY,
                    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                    name VARCHAR(100) NOT NULL,
                    color VARCHAR(7) DEFAULT '#6366f1',
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    CONSTRAINT uix_tag_workspace_name UNIQUE (workspace_id, name)
                )
            """))
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_tags_workspace_id ON tags(workspace_id)
            """))

            # 3. Create contact_tags table
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS contact_tags (
                    id SERIAL PRIMARY KEY,
                    contact_id INTEGER NOT NULL REFERENCES contacts(id),
                    tag_id INTEGER NOT NULL REFERENCES tags(id),
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    CONSTRAINT uix_contact_tag UNIQUE (contact_id, tag_id)
                )
            """))
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_contact_tags_contact_id ON contact_tags(contact_id)
            """))
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_contact_tags_tag_id ON contact_tags(tag_id)
            """))

            # 4. Create contact_merge_history table
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS contact_merge_history (
                    id SERIAL PRIMARY KEY,
                    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                    primary_contact_id INTEGER NOT NULL REFERENCES contacts(id),
                    merged_contact_id INTEGER NOT NULL,
                    merged_data_json TEXT NOT NULL,
                    merged_by INTEGER NOT NULL REFERENCES users(id),
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """))
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_merge_history_workspace ON contact_merge_history(workspace_id)
            """))
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_merge_history_primary ON contact_merge_history(primary_contact_id)
            """))

            # 5. Backfill last_activity_at from latest activity
            db.session.execute(text("""
                UPDATE contacts c
                SET last_activity_at = sub.latest
                FROM (
                    SELECT contact_id, MAX(created_at) AS latest
                    FROM activities
                    WHERE contact_id IS NOT NULL AND is_deleted = FALSE
                    GROUP BY contact_id
                ) sub
                WHERE c.id = sub.contact_id AND c.last_activity_at IS NULL
            """))

            db.session.commit()
            print("✅ Successfully added advanced contact features (tags, merge history, last_activity_at)")

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error adding advanced contact features: {str(e)}")
            raise


def downgrade():
    """Remove advanced contact features"""
    from app import app, db
    from sqlalchemy import text

    with app.app_context():
        try:
            db.session.execute(text("DROP TABLE IF EXISTS contact_merge_history CASCADE"))
            db.session.execute(text("DROP TABLE IF EXISTS contact_tags CASCADE"))
            db.session.execute(text("DROP TABLE IF EXISTS tags CASCADE"))
            db.session.execute(text("DROP INDEX IF EXISTS idx_contacts_last_activity_at"))
            db.session.execute(text("ALTER TABLE contacts DROP COLUMN IF EXISTS last_activity_at"))
            db.session.commit()
            print("✅ Successfully removed advanced contact features")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error removing advanced contact features: {str(e)}")
            raise


if __name__ == '__main__':
    upgrade()
