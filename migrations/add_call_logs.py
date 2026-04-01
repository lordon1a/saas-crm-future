"""
Migration: add_call_logs
Creates call_logs table.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from sqlalchemy import text


def upgrade():
    with app.app_context():
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS call_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                contact_id INTEGER REFERENCES contacts(id),
                deal_id INTEGER REFERENCES deals(id),
                logged_by INTEGER NOT NULL REFERENCES users(id),
                direction VARCHAR(20) NOT NULL DEFAULT 'outbound',
                phone_number VARCHAR(50) NOT NULL,
                duration_seconds INTEGER NOT NULL DEFAULT 0,
                outcome VARCHAR(30) NOT NULL DEFAULT 'connected',
                notes TEXT,
                recording_url VARCHAR(500),
                external_call_id VARCHAR(120),
                called_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))

        db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_call_logs_workspace_called ON call_logs(workspace_id, called_at)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_call_logs_contact ON call_logs(contact_id)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_call_logs_external ON call_logs(external_call_id)"))
        db.session.commit()
        print("[OK] add_call_logs migration completed")


def downgrade():
    with app.app_context():
        db.session.execute(text("DROP TABLE IF EXISTS call_logs"))
        db.session.commit()
        print("[OK] add_call_logs rollback completed")


if __name__ == '__main__':
    upgrade()
