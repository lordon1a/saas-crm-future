"""
Migration: add_zoom_integration
Creates zoom/linkedin ads integration tables and adds video_provider to meeting_links.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from sqlalchemy import text


def _ensure_column(table_name, column_name, ddl):
    db_uri = str(app.config.get('SQLALCHEMY_DATABASE_URI', ''))
    is_sqlite = db_uri.startswith('sqlite')

    if is_sqlite:
        res = db.session.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        cols = {row[1] for row in res}
        if column_name not in cols:
            db.session.execute(text(ddl))
        return

    res = db.session.execute(text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :table_name AND column_name = :column_name
    """), {'table_name': table_name, 'column_name': column_name}).fetchone()
    if not res:
        db.session.execute(text(ddl))


def upgrade():
    with app.app_context():
        _ensure_column(
            'meeting_links',
            'video_provider',
            "ALTER TABLE meeting_links ADD COLUMN video_provider VARCHAR(20) DEFAULT 'none'"
        )

        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS zoom_integrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                user_id INTEGER NOT NULL REFERENCES users(id),
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                token_expires_at DATETIME,
                zoom_user_id VARCHAR(120),
                zoom_email VARCHAR(255),
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(workspace_id, user_id)
            )
        """))

        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS linkedin_integrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                user_id INTEGER NOT NULL REFERENCES users(id),
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                token_expires_at DATETIME,
                linkedin_member_id VARCHAR(120),
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(workspace_id, user_id)
            )
        """))

        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS facebook_ads_integrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                page_id VARCHAR(120),
                page_name VARCHAR(255),
                access_token TEXT NOT NULL,
                webhook_subscribed BOOLEAN NOT NULL DEFAULT 0,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))

        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS google_ads_integrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                user_id INTEGER NOT NULL REFERENCES users(id),
                customer_id VARCHAR(120),
                conversion_action_id VARCHAR(120),
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                token_expires_at DATETIME,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(workspace_id, user_id)
            )
        """))

        db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_zoom_integrations_workspace_user ON zoom_integrations(workspace_id, user_id)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_linkedin_integrations_workspace_user ON linkedin_integrations(workspace_id, user_id)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_facebook_ads_integrations_workspace ON facebook_ads_integrations(workspace_id)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_google_ads_integrations_workspace_user ON google_ads_integrations(workspace_id, user_id)"))

        db.session.commit()
        print("[OK] add_zoom_integration migration completed")


def downgrade():
    with app.app_context():
        db.session.execute(text("DROP TABLE IF EXISTS google_ads_integrations"))
        db.session.execute(text("DROP TABLE IF EXISTS facebook_ads_integrations"))
        db.session.execute(text("DROP TABLE IF EXISTS linkedin_integrations"))
        db.session.execute(text("DROP TABLE IF EXISTS zoom_integrations"))
        db.session.commit()
        print("[OK] add_zoom_integration rollback completed")


if __name__ == '__main__':
    upgrade()
