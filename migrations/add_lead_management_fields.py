"""
Migration: Add lead management fields to contacts table
Adds lead_source, lifecycle_stage, qualified_at, converted_at columns
"""
import sqlite3
import os
import sys

def migrate():
    """Add lead management fields to contacts table"""
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
        
        # Check existing columns in contacts table
        cursor.execute("PRAGMA table_info(contacts)")
        columns = [col[1] for col in cursor.fetchall()]
        
        print("\nAdding lead management columns to contacts table...")
        
        # Add lead_source column
        if 'lead_source' not in columns:
            cursor.execute("""
                ALTER TABLE contacts 
                ADD COLUMN lead_source VARCHAR(100)
            """)
            print("✓ Added lead_source column to contacts")
        else:
            print("✓ lead_source column already exists")
        
        # Add lifecycle_stage column
        if 'lifecycle_stage' not in columns:
            cursor.execute("""
                ALTER TABLE contacts 
                ADD COLUMN lifecycle_stage VARCHAR(50) DEFAULT 'lead' NOT NULL
            """)
            print("✓ Added lifecycle_stage column to contacts")
        else:
            print("✓ lifecycle_stage column already exists")
        
        # Add qualified_at column
        if 'qualified_at' not in columns:
            cursor.execute("""
                ALTER TABLE contacts 
                ADD COLUMN qualified_at TIMESTAMP
            """)
            print("✓ Added qualified_at column to contacts")
        else:
            print("✓ qualified_at column already exists")
        
        # Add converted_at column
        if 'converted_at' not in columns:
            cursor.execute("""
                ALTER TABLE contacts 
                ADD COLUMN converted_at TIMESTAMP
            """)
            print("✓ Added converted_at column to contacts")
        else:
            print("✓ converted_at column already exists")
        
        # Create indexes
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_contact_lead_source 
                ON contacts(lead_source)
            """)
            print("✓ Created index on lead_source")
        except Exception as e:
            print(f"⚠ Index on lead_source may already exist: {e}")
        
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_contact_lifecycle_stage 
                ON contacts(lifecycle_stage)
            """)
            print("✓ Created index on lifecycle_stage")
        except Exception as e:
            print(f"⚠ Index on lifecycle_stage may already exist: {e}")
        
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
        
        print("\nAdding lead management columns to contacts table...")
        
        # Check and add lead_source column
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='contacts' AND column_name='lead_source'
        """)
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE contacts 
                ADD COLUMN lead_source VARCHAR(100)
            """)
            conn.commit()
            print("✓ Added lead_source column to contacts")
        else:
            print("✓ lead_source column already exists")
        
        # Check and add lifecycle_stage column
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='contacts' AND column_name='lifecycle_stage'
        """)
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE contacts 
                ADD COLUMN lifecycle_stage VARCHAR(50) DEFAULT 'lead' NOT NULL
            """)
            conn.commit()
            print("✓ Added lifecycle_stage column to contacts")
        else:
            print("✓ lifecycle_stage column already exists")
        
        # Check and add qualified_at column
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='contacts' AND column_name='qualified_at'
        """)
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE contacts 
                ADD COLUMN qualified_at TIMESTAMP
            """)
            conn.commit()
            print("✓ Added qualified_at column to contacts")
        else:
            print("✓ qualified_at column already exists")
        
        # Check and add converted_at column
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='contacts' AND column_name='converted_at'
        """)
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE contacts 
                ADD COLUMN converted_at TIMESTAMP
            """)
            conn.commit()
            print("✓ Added converted_at column to contacts")
        else:
            print("✓ converted_at column already exists")
        
        # Create indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_contact_lead_source 
            ON contacts(lead_source)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_contact_lifecycle_stage 
            ON contacts(lifecycle_stage)
        """)
        conn.commit()
        print("✓ Created indexes on lead management columns")
        
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
    """Remove lead management fields"""
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'whatsapp_crm.db')
        if not os.path.exists(db_path):
            print(f"Database not found at {db_path}")
            sys.exit(1)
        return downgrade_sqlite(db_path)
    
    return downgrade_postgres(database_url)

def downgrade_sqlite(db_path):
    """SQLite downgrade - Note: SQLite doesn't support DROP COLUMN"""
    print("⚠ Note: SQLite doesn't support DROP COLUMN. Columns will remain in table.")
    print("✓ SQLite downgrade completed (no-op)")

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
        
        # Remove columns
        cur.execute("ALTER TABLE contacts DROP COLUMN IF EXISTS lead_source")
        cur.execute("ALTER TABLE contacts DROP COLUMN IF EXISTS lifecycle_stage")
        cur.execute("ALTER TABLE contacts DROP COLUMN IF EXISTS qualified_at")
        cur.execute("ALTER TABLE contacts DROP COLUMN IF EXISTS converted_at")
        print("✓ Removed lead management columns from contacts table")
        
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
