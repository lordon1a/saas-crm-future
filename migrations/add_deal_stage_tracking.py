"""
Migration: Add stage tracking and rotting features to deals
Date: 2026-03-18
"""
import sqlite3
import os
from datetime import datetime

def migrate():
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'whatsapp_crm.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(deals)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Add stage_entered_at column if not exists
        if 'stage_entered_at' not in columns:
            # SQLite doesn't support CURRENT_TIMESTAMP in ALTER TABLE
            # So we add the column as nullable first, then update it
            cursor.execute("""
                ALTER TABLE deals 
                ADD COLUMN stage_entered_at TIMESTAMP
            """)
            print("✓ Added stage_entered_at column")
            
            # Update existing deals to set stage_entered_at to created_at
            cursor.execute("""
                UPDATE deals 
                SET stage_entered_at = created_at 
                WHERE stage_entered_at IS NULL
            """)
            print("✓ Backfilled stage_entered_at with created_at values")
            
            # Create index for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_deals_stage_entered_at 
                ON deals(stage_entered_at)
            """)
            print("✓ Created index on stage_entered_at")
        else:
            print("- stage_entered_at column already exists")
        
        conn.commit()
        print("\n✓ Migration completed successfully")
        print("\nNote: New deals will automatically get stage_entered_at set by the application code.")
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Migration failed: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

