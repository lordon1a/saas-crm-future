"""
Migration: Add display_order column to contacts and companies tables
Run this script to update the database schema for drag-and-drop ordering
"""
import sqlite3
import os
import sys

def migrate():
    """Add display_order column to contacts and companies tables"""
    database_url = os.environ.get('DATABASE_URL')
    
    # Determine if using PostgreSQL or SQLite
    if database_url:
        # PostgreSQL (production)
        try:
            import psycopg2
        except ImportError:
            print("ERROR: psycopg2 not installed. Install with: pip install psycopg2-binary")
            sys.exit(1)
            
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        try:
            conn = psycopg2.connect(database_url)
            cur = conn.cursor()
            print("Connected to PostgreSQL database successfully")
            
            # Check and add display_order to contacts table
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='contacts' AND column_name='display_order'
            """)
            
            if cur.fetchone():
                print("✓ contacts.display_order column already exists - skipping")
            else:
                cur.execute("""
                    ALTER TABLE contacts 
                    ADD COLUMN display_order INTEGER DEFAULT 0 NOT NULL
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS ix_contacts_display_order 
                    ON contacts(display_order)
                """)
                conn.commit()
                print("✓ Added display_order column to contacts table")
                
                # Backfill existing contacts with sequential display_order
                cur.execute("""
                    WITH numbered AS (
                        SELECT id, ROW_NUMBER() OVER (PARTITION BY workspace_id ORDER BY id) - 1 AS row_num
                        FROM contacts
                    )
                    UPDATE contacts
                    SET display_order = numbered.row_num
                    FROM numbered
                    WHERE contacts.id = numbered.id
                """)
                conn.commit()
                print("✓ Backfilled display_order for existing contacts")
            
            # Check and add display_order to companies table
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='companies' AND column_name='display_order'
            """)
            
            if cur.fetchone():
                print("✓ companies.display_order column already exists - skipping")
            else:
                cur.execute("""
                    ALTER TABLE companies 
                    ADD COLUMN display_order INTEGER DEFAULT 0 NOT NULL
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS ix_companies_display_order 
                    ON companies(display_order)
                """)
                conn.commit()
                print("✓ Added display_order column to companies table")
                
                # Backfill existing companies with sequential display_order
                cur.execute("""
                    WITH numbered AS (
                        SELECT id, ROW_NUMBER() OVER (PARTITION BY workspace_id ORDER BY id) - 1 AS row_num
                        FROM companies
                    )
                    UPDATE companies
                    SET display_order = numbered.row_num
                    FROM numbered
                    WHERE companies.id = numbered.id
                """)
                conn.commit()
                print("✓ Backfilled display_order for existing companies")
            
            cur.close()
            conn.close()
            print("\n✓ Migration completed successfully")
            
        except Exception as e:
            print(f"\n✗ Migration failed: {str(e)}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            sys.exit(1)
    else:
        # SQLite (local development)
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'whatsapp_crm.db')
        
        if not os.path.exists(db_path):
            print(f"ERROR: Database file not found at {db_path}")
            sys.exit(1)
        
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            print(f"Connected to SQLite database at {db_path}")
            
            # Check and add display_order to contacts table
            cur.execute("PRAGMA table_info(contacts)")
            columns = [col[1] for col in cur.fetchall()]
            
            if 'display_order' in columns:
                print("✓ contacts.display_order column already exists - skipping")
            else:
                cur.execute("""
                    ALTER TABLE contacts 
                    ADD COLUMN display_order INTEGER DEFAULT 0 NOT NULL
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS ix_contacts_display_order 
                    ON contacts(display_order)
                """)
                conn.commit()
                print("✓ Added display_order column to contacts table")
                
                # Backfill existing contacts with sequential display_order
                cur.execute("""
                    SELECT id, workspace_id FROM contacts ORDER BY workspace_id, id
                """)
                contacts = cur.fetchall()
                
                workspace_counters = {}
                for contact_id, workspace_id in contacts:
                    if workspace_id not in workspace_counters:
                        workspace_counters[workspace_id] = 0
                    cur.execute("""
                        UPDATE contacts SET display_order = ? WHERE id = ?
                    """, (workspace_counters[workspace_id], contact_id))
                    workspace_counters[workspace_id] += 1
                
                conn.commit()
                print("✓ Backfilled display_order for existing contacts")
            
            # Check and add display_order to companies table
            cur.execute("PRAGMA table_info(companies)")
            columns = [col[1] for col in cur.fetchall()]
            
            if 'display_order' in columns:
                print("✓ companies.display_order column already exists - skipping")
            else:
                cur.execute("""
                    ALTER TABLE companies 
                    ADD COLUMN display_order INTEGER DEFAULT 0 NOT NULL
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS ix_companies_display_order 
                    ON companies(display_order)
                """)
                conn.commit()
                print("✓ Added display_order column to companies table")
                
                # Backfill existing companies with sequential display_order
                cur.execute("""
                    SELECT id, workspace_id FROM companies ORDER BY workspace_id, id
                """)
                companies = cur.fetchall()
                
                workspace_counters = {}
                for company_id, workspace_id in companies:
                    if workspace_id not in workspace_counters:
                        workspace_counters[workspace_id] = 0
                    cur.execute("""
                        UPDATE companies SET display_order = ? WHERE id = ?
                    """, (workspace_counters[workspace_id], company_id))
                    workspace_counters[workspace_id] += 1
                
                conn.commit()
                print("✓ Backfilled display_order for existing companies")
            
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
    """Remove display_order column from contacts and companies tables"""
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        # PostgreSQL
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        try:
            conn = psycopg2.connect(database_url)
            cur = conn.cursor()
            print("Connected to PostgreSQL database successfully")
            
            cur.execute("DROP INDEX IF EXISTS ix_contacts_display_order")
            cur.execute("ALTER TABLE contacts DROP COLUMN IF EXISTS display_order")
            cur.execute("DROP INDEX IF EXISTS ix_companies_display_order")
            cur.execute("ALTER TABLE companies DROP COLUMN IF EXISTS display_order")
            
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
    else:
        # SQLite
        print("ERROR: Downgrade not supported for SQLite (column drop requires table recreation)")
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'downgrade':
        downgrade()
    else:
        migrate()
