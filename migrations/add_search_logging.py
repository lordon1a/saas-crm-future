"""
Migration: Add search_logs table for search analytics
Run this script to enable search behavior tracking
"""
import sqlite3
import os
import sys

def migrate():
    """Add search_logs table"""
    database_url = os.environ.get('DATABASE_URL')
    
    # Use SQLite for local development
    if not database_url:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'whatsapp_crm.db')
        if not os.path.exists(db_path):
            print(f"Database not found at {db_path}")
            sys.exit(1)
        return migrate_sqlite(db_path)
    
    # Use PostgreSQL for production
    return migrate_postgres(database_url)

def migrate_sqlite(db_path):
    """SQLite migration"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Connected to SQLite database successfully")
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='search_logs'
        """)
        
        if cursor.fetchone():
            print("✓ search_logs table already exists")
            cursor.close()
            conn.close()
            return
        
        print("\nCreating search_logs table...")
        
        cursor.execute("""
            CREATE TABLE search_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                search_query VARCHAR(500) NOT NULL,
                search_type VARCHAR(50) NOT NULL,
                entity_type VARCHAR(50),
                results_count INTEGER DEFAULT 0,
                clicked_result_id INTEGER,
                clicked_result_type VARCHAR(50),
                search_duration_ms INTEGER,
                filters_applied TEXT,
                user_agent VARCHAR(500),
                ip_address VARCHAR(45),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX idx_search_log_workspace_id 
            ON search_logs(workspace_id)
        """)
        cursor.execute("""
            CREATE INDEX idx_search_log_user_id 
            ON search_logs(user_id)
        """)
        cursor.execute("""
            CREATE INDEX idx_search_log_query 
            ON search_logs(search_query)
        """)
        cursor.execute("""
            CREATE INDEX idx_search_log_type 
            ON search_logs(search_type)
        """)
        cursor.execute("""
            CREATE INDEX idx_search_log_created_at 
            ON search_logs(created_at)
        """)
        cursor.execute("""
            CREATE INDEX idx_search_log_workspace_created 
            ON search_logs(workspace_id, created_at)
        """)
        cursor.execute("""
            CREATE INDEX idx_search_log_user_created 
            ON search_logs(user_id, created_at)
        """)
        
        conn.commit()
        print("✓ Created search_logs table with indexes")
        
        cursor.close()
        conn.close()
        
        print("\n✓ SQLite migration completed successfully")
        
    except Exception as e:
        print(f"\n✗ Migration failed: {str(e)}")
        conn.rollback()
        conn.close()
        sys.exit(1)

def migrate_postgres(database_url):
    """PostgreSQL migration"""
    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed. Install with: pip install psycopg2-binary")
        sys.exit(1)
    
    # Fix for Render's postgres:// URL
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        print("Connected to PostgreSQL database successfully")
        
        # Check if table exists
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name='search_logs'
        """)
        
        if cur.fetchone():
            print("✓ search_logs table already exists")
            cur.close()
            conn.close()
            return
        
        print("\nCreating search_logs table...")
        
        cur.execute("""
            CREATE TABLE search_logs (
                id SERIAL PRIMARY KEY,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                search_query VARCHAR(500) NOT NULL,
                search_type VARCHAR(50) NOT NULL,
                entity_type VARCHAR(50),
                results_count INTEGER DEFAULT 0,
                clicked_result_id INTEGER,
                clicked_result_type VARCHAR(50),
                search_duration_ms INTEGER,
                filters_applied TEXT,
                user_agent VARCHAR(500),
                ip_address VARCHAR(45),
                created_at TIMESTAMP DEFAULT NOW() NOT NULL
            )
        """)
        
        # Create indexes
        cur.execute("""
            CREATE INDEX idx_search_log_workspace_id ON search_logs(workspace_id)
        """)
        cur.execute("""
            CREATE INDEX idx_search_log_user_id ON search_logs(user_id)
        """)
        cur.execute("""
            CREATE INDEX idx_search_log_query ON search_logs(search_query)
        """)
        cur.execute("""
            CREATE INDEX idx_search_log_type ON search_logs(search_type)
        """)
        cur.execute("""
            CREATE INDEX idx_search_log_created_at ON search_logs(created_at)
        """)
        cur.execute("""
            CREATE INDEX idx_search_log_workspace_created 
            ON search_logs(workspace_id, created_at)
        """)
        cur.execute("""
            CREATE INDEX idx_search_log_user_created 
            ON search_logs(user_id, created_at)
        """)
        
        conn.commit()
        print("✓ Created search_logs table with indexes")
        
        cur.close()
        conn.close()
        
        print("\n✓ PostgreSQL migration completed successfully")
        
    except Exception as e:
        print(f"\n✗ Migration failed: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        sys.exit(1)

if __name__ == '__main__':
    migrate()
