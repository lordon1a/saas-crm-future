"""
Add Web Forms and Form Submissions tables
Migration: add_web_forms
"""

from migration_base import *


def upgrade():
    """Create web_forms and form_submissions tables"""
    
    conn = engine.connect()
    trans = conn.begin()
    
    try:
        # Create web_forms table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS web_forms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL,
                created_by INTEGER,
                name VARCHAR(200) NOT NULL,
                fields_json TEXT,
                submit_action VARCHAR(50) DEFAULT 'create_contact',
                redirect_url VARCHAR(500),
                notify_user_id INTEGER,
                is_active BOOLEAN DEFAULT 1,
                submission_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspaces (id),
                FOREIGN KEY (created_by) REFERENCES users (id),
                FOREIGN KEY (notify_user_id) REFERENCES users (id)
            )
        """))
        
        # Create form_submissions table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS form_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                form_id INTEGER NOT NULL,
                workspace_id INTEGER NOT NULL,
                data_json TEXT NOT NULL,
                contact_id INTEGER,
                ip_address VARCHAR(50),
                user_agent VARCHAR(500),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (form_id) REFERENCES web_forms (id),
                FOREIGN KEY (workspace_id) REFERENCES workspaces (id),
                FOREIGN KEY (contact_id) REFERENCES contacts (id)
            )
        """))
        
        # Create indexes
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_web_forms_workspace ON web_forms(workspace_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_web_forms_active ON web_forms(is_active)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_form_submissions_form ON form_submissions(form_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_form_submissions_contact ON form_submissions(contact_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_form_submissions_created ON form_submissions(created_at)"))
        
        trans.commit()
        print("Migration add_web_forms completed successfully")
        
    except Exception as e:
        trans.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


def downgrade():
    """Drop web_forms and form_submissions tables"""
    conn = engine.connect()
    trans = conn.begin()
    
    try:
        conn.execute(text("DROP TABLE IF EXISTS form_submissions"))
        conn.execute(text("DROP TABLE IF EXISTS web_forms"))
        trans.commit()
        print("Migration add_web_forms rolled back successfully")
    except Exception as e:
        trans.rollback()
        print(f"Rollback failed: {e}")
        raise
    finally:
        conn.close()
