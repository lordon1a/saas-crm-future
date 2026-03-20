"""
Migration: Add assigned_to fields to Contact and Company tables
Run this script to add team member assignment functionality to CRM entities
"""
import sqlite3
import os
import sys

def migrate():
    """Add assigned_to fields to Contact and Company tables"""
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
        contact_columns = [col[1] for col in cursor.fetchall()]
        
        # Check existing columns in companies table
        cursor.execute("PRAGMA table_info(companies)")
        company_columns = [col[1] for col in cursor.fetchall()]
        
        print("\nAdding assigned_to columns to CRM tables...")
        
        # Add assigned_to column to contacts
        if 'assigned_to' not in contact_columns:
            cursor.execute("""
                ALTER TABLE contacts 
                ADD COLUMN assigned_to INTEGER
            """)
            # Create index
            cursor.execute("""
                CREATE INDEX idx_contacts_assigned_to 
                ON contacts(assigned_to)
            """)
            print("✓ Added assigned_to column to contacts table")
        else:
            print("✓ assigned_to column already exists in contacts table")
        
        # Add assigned_to column to companies
        if 'assigned_to' not in company_columns:
            cursor.execute("""
                ALTER TABLE companies 
                ADD COLUMN assigned_to INTEGER
            """)
            # Create index
            cursor.execute("""
                CREATE INDEX idx_companies_assigned_to 
                ON companies(assigned_to)
            """)
            print("✓ Added assigned_to column to companies table")
        else:
            print("✓ assigned_to column already exists in companies table")
        
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
        
        print("\nAdding assigned_to columns to CRM tables...")
        
        # Check and add assigned_to column to contacts
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='contacts' AND column_name='assigned_to'
        """)
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE contacts 
                ADD COLUMN assigned_to INTEGER REFERENCES users(id)
            """)
            cur.execute("""
                CREATE INDEX idx_contacts_assigned_to ON contacts(assigned_to)
            """)
            conn.commit()
            print("✓ Added assigned_to column to contacts table")
        else:
            print("✓ assigned_to column already exists in contacts table")
        
        # Check and add assigned_to column to companies
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='companies' AND column_name='assigned_to'
        """)
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE companies 
                ADD COLUMN assigned_to INTEGER REFERENCES users(id)
            """)
            cur.execute("""
                CREATE INDEX idx_companies_assigned_to ON companies(assigned_to)
            """)
            conn.commit()
            print("✓ Added assigned_to column to companies table")
        else:
            print("✓ assigned_to column already exists in companies table")
        
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
    """Remove assigned_to fields from Contact and Company tables"""
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
    print("⚠ Note: SQLite doesn't support DROP COLUMN. Columns remain in tables.")
    print("To fully remove columns, you would need to recreate the tables.")

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
        
        # Remove assigned_to columns
        cur.execute("ALTER TABLE contacts DROP COLUMN IF EXISTS assigned_to")
        cur.execute("ALTER TABLE companies DROP COLUMN IF EXISTS assigned_to")
        print("✓ Removed assigned_to columns from contacts and companies tables")
        
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
