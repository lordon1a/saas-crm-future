"""
Migration: Add company_notes table for company detail page
"""
import sqlite3
import os
import sys


def migrate():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'whatsapp_crm.db')
        if not os.path.exists(db_path):
            print(f"Database not found at {db_path}")
            sys.exit(1)
        return migrate_sqlite(db_path)
    return migrate_postgres(database_url)


def migrate_sqlite(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='company_notes'")
        if cursor.fetchone():
            print("company_notes table already exists — skipping.")
            return
        cursor.execute("""
            CREATE TABLE company_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                company_id INTEGER NOT NULL REFERENCES companies(id),
                user_id INTEGER NOT NULL REFERENCES users(id),
                content TEXT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX idx_company_notes_company ON company_notes(company_id)")
        cursor.execute("CREATE INDEX idx_company_notes_workspace ON company_notes(workspace_id)")
        cursor.execute("CREATE INDEX idx_company_notes_created ON company_notes(created_at)")
        conn.commit()
        print("company_notes table created successfully.")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()


def migrate_postgres(database_url):
    import psycopg2
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT to_regclass('public.company_notes')")
        if cursor.fetchone()[0]:
            print("company_notes table already exists — skipping.")
            return
        cursor.execute("""
            CREATE TABLE company_notes (
                id SERIAL PRIMARY KEY,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                company_id INTEGER NOT NULL REFERENCES companies(id),
                user_id INTEGER NOT NULL REFERENCES users(id),
                content TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cursor.execute("CREATE INDEX idx_company_notes_company ON company_notes(company_id)")
        cursor.execute("CREATE INDEX idx_company_notes_workspace ON company_notes(workspace_id)")
        cursor.execute("CREATE INDEX idx_company_notes_created ON company_notes(created_at)")
        conn.commit()
        print("company_notes table created successfully.")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    migrate()
