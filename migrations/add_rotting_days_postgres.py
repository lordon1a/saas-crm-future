"""
Migration: Add rotting_days column to deal_stages table (PostgreSQL)
Run this script on Render to update the production database schema
"""
import psycopg2
import os
import sys

def migrate():
    """Add rotting_days column to deal_stages table"""
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)
    
    # Fix for Render's postgres:// URL (psycopg2 requires postgresql://)
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        print("Connected to database successfully")
        
        # Check if column already exists
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='deal_stages' AND column_name='rotting_days'
        """)
        
        if cur.fetchone():
            print("✓ rotting_days column already exists - skipping")
        else:
            # Add rotting_days column
            cur.execute("""
                ALTER TABLE deal_stages 
                ADD COLUMN rotting_days INTEGER DEFAULT NULL
            """)
            conn.commit()
            print("✓ Added rotting_days column to deal_stages table")
        
        # Check if is_active column exists (from same migration)
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='deal_stages' AND column_name='is_active'
        """)
        
        if cur.fetchone():
            print("✓ is_active column already exists - skipping")
        else:
            # Add is_active column
            cur.execute("""
                ALTER TABLE deal_stages 
                ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL
            """)
            conn.commit()
            print("✓ Added is_active column to deal_stages table")
        
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
    """Remove rotting_days column from deal_stages table"""
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
        
        # Remove rotting_days column
        cur.execute("""
            ALTER TABLE deal_stages 
            DROP COLUMN IF EXISTS rotting_days
        """)
        
        # Remove is_active column
        cur.execute("""
            ALTER TABLE deal_stages 
            DROP COLUMN IF EXISTS is_active
        """)
        
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
