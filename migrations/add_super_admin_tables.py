"""
Migration: Add super_admins and impersonate_logs tables
Run this script to add super admin functionality
"""
import psycopg2
import os
import sys

def migrate():
    """Add super_admins and impersonate_logs tables"""
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)
    
    # Fix for Render's postgres:// URL
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        print("Connected to database successfully")
        
        # Check if super_admins table exists
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name='super_admins'
        """)
        
        if not cur.fetchone():
            # Create super_admins table
            cur.execute("""
                CREATE TABLE super_admins (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    last_login TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            conn.commit()
            print("✓ Created super_admins table")
        else:
            print("✓ super_admins table already exists")
        
        # Check if impersonate_logs table exists
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name='impersonate_logs'
        """)
        
        if not cur.fetchone():
            # Create impersonate_logs table
            cur.execute("""
                CREATE TABLE impersonate_logs (
                    id SERIAL PRIMARY KEY,
                    super_admin_id INTEGER REFERENCES super_admins(id),
                    workspace_id INTEGER REFERENCES workspaces(id),
                    started_at TIMESTAMP DEFAULT NOW(),
                    ended_at TIMESTAMP,
                    ip_address VARCHAR(50)
                )
            """)
            conn.commit()
            print("✓ Created impersonate_logs table")
        else:
            print("✓ impersonate_logs table already exists")
        
        cur.close()
        conn.close()
        
        print("\n✓ Migration completed successfully")
        
    except Exception as e:
        print(f"\n✗ Migration failed: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        sys.exit(1)

def downgrade():
    """Remove super_admins and impersonate_logs tables"""
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)
    
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        print("Connected to database successfully")
        
        # Drop tables in reverse order (foreign keys)
        cur.execute("DROP TABLE IF EXISTS impersonate_logs CASCADE")
        cur.execute("DROP TABLE IF EXISTS super_admins CASCADE")
        
        conn.commit()
        cur.close()
        conn.close()
        
        print("✓ Downgrade completed successfully")
        
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
