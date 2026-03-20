"""
Migration: Add password_reset_tokens table for forgot password feature
Run this script to add password reset functionality
"""
import sqlite3
import os
import sys

def migrate():
    """Add password_reset_tokens table"""
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
        
        # Check if password_reset_tokens table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='password_reset_tokens'
        """)
        
        if not cursor.fetchone():
            # Create password_reset_tokens table
            cursor.execute("""
                CREATE TABLE password_reset_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token VARCHAR(64) UNIQUE NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    used_at TIMESTAMP,
                    created_at TIMESTAMP NOT NULL,
                    ip_address VARCHAR(50),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            print("✓ Created password_reset_tokens table")
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX idx_password_reset_tokens_user_id 
                ON password_reset_tokens(user_id)
            """)
            cursor.execute("""
                CREATE INDEX idx_password_reset_tokens_token 
                ON password_reset_tokens(token)
            """)
            cursor.execute("""
                CREATE INDEX idx_password_reset_tokens_expires_at 
                ON password_reset_tokens(expires_at)
            """)
            print("✓ Created indexes on password_reset_tokens table")
        else:
            print("✓ password_reset_tokens table already exists")
        
        conn.commit()
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
        
        # Check if password_reset_tokens table exists
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name='password_reset_tokens'
        """)
        
        if not cur.fetchone():
            # Create password_reset_tokens table
            cur.execute("""
                CREATE TABLE password_reset_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    token VARCHAR(64) UNIQUE NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    used_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                    ip_address VARCHAR(50)
                )
            """)
            conn.commit()
            print("✓ Created password_reset_tokens table")
            
            # Create indexes
            cur.execute("""
                CREATE INDEX idx_password_reset_tokens_user_id 
                ON password_reset_tokens(user_id)
            """)
            cur.execute("""
                CREATE INDEX idx_password_reset_tokens_token 
                ON password_reset_tokens(token)
            """)
            cur.execute("""
                CREATE INDEX idx_password_reset_tokens_expires_at 
                ON password_reset_tokens(expires_at)
            """)
            conn.commit()
            print("✓ Created indexes on password_reset_tokens table")
        else:
            print("✓ password_reset_tokens table already exists")
        
        cur.close()
        conn.close()
        
        print("\n✓ PostgreSQL migration completed successfully")
        
    except Exception as e:
        print(f"\n✗ Migration failed: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        sys.exit(1)

def downgrade():
    """Remove password_reset_tokens table"""
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'whatsapp_crm.db')
        if not os.path.exists(db_path):
            print(f"Database not found at {db_path}")
            sys.exit(1)
        return downgrade_sqlite(db_path)
    
    return downgrade_postgres(database_url)

def downgrade_sqlite(db_path):
    """SQLite downgrade"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Connected to SQLite database successfully")
        
        # Drop password_reset_tokens table
        cursor.execute("DROP TABLE IF EXISTS password_reset_tokens")
        print("✓ Dropped password_reset_tokens table")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✓ SQLite downgrade completed")
        
    except Exception as e:
        print(f"✗ Downgrade failed: {str(e)}")
        conn.rollback()
        conn.close()
        sys.exit(1)

def downgrade_postgres(database_url):
    """PostgreSQL downgrade"""
    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed")
        sys.exit(1)
    
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        print("Connected to PostgreSQL database successfully")
        
        # Drop password_reset_tokens table
        cur.execute("DROP TABLE IF EXISTS password_reset_tokens CASCADE")
        print("✓ Dropped password_reset_tokens table")
        
        conn.commit()
        cur.close()
        conn.close()
        
        print("✓ PostgreSQL downgrade completed successfully")
        
    except Exception as e:
        print(f"✗ Downgrade failed: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'downgrade':
        downgrade()
    else:
        migrate()
