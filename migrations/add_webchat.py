"""
Migration: add_webchat
Creates webchat_configs, chat_sessions, chat_messages tables.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from sqlalchemy import text


def upgrade():
    with app.app_context():
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS webchat_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL UNIQUE REFERENCES workspaces(id),
                widget_title VARCHAR(120) NOT NULL DEFAULT 'Merhaba',
                welcome_message TEXT NOT NULL DEFAULT 'Size nasil yardimci olabiliriz?',
                primary_color VARCHAR(20) NOT NULL DEFAULT '#0ea5e9',
                bot_name VARCHAR(80) NOT NULL DEFAULT 'Asistan',
                collect_name BOOLEAN NOT NULL DEFAULT 1,
                collect_email BOOLEAN NOT NULL DEFAULT 1,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                auto_create_contact BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))

        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                contact_id INTEGER REFERENCES contacts(id),
                visitor_id VARCHAR(120) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'open',
                assigned_to INTEGER REFERENCES users(id),
                source_url VARCHAR(500),
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_message_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))

        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
                sender_type VARCHAR(20) NOT NULL,
                sender_id INTEGER,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))

        db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_chat_sessions_workspace_status ON chat_sessions(workspace_id, status)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_chat_sessions_visitor ON chat_sessions(visitor_id)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created ON chat_messages(session_id, created_at)"))
        db.session.commit()
        print("[OK] add_webchat migration completed")


def downgrade():
    with app.app_context():
        db.session.execute(text("DROP TABLE IF EXISTS chat_messages"))
        db.session.execute(text("DROP TABLE IF EXISTS chat_sessions"))
        db.session.execute(text("DROP TABLE IF EXISTS webchat_configs"))
        db.session.commit()
        print("[OK] add_webchat rollback completed")


if __name__ == '__main__':
    upgrade()
