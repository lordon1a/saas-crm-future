"""
Migration: Add probability (Integer), rotting_days, is_active columns to deal_stages table
Run this script to update existing database schema
"""
import sqlite3
import os

def migrate():
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'whatsapp_crm.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(deal_stages)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Add rotting_days column if not exists
        if 'rotting_days' not in columns:
            cursor.execute("ALTER TABLE deal_stages ADD COLUMN rotting_days INTEGER")
            print("✓ Added rotting_days column")
        else:
            print("- rotting_days column already exists")
        
        # Add is_active column if not exists
        if 'is_active' not in columns:
            cursor.execute("ALTER TABLE deal_stages ADD COLUMN is_active BOOLEAN DEFAULT 1 NOT NULL")
            print("✓ Added is_active column")
        else:
            print("- is_active column already exists")
        
        # Note: SQLite doesn't support ALTER COLUMN TYPE directly
        # probability column type change from FLOAT to INTEGER requires table recreation
        # For now, we'll keep existing probability values and convert them
        if 'probability' in columns:
            # Update existing probability values from 0.0-1.0 to 0-100
            cursor.execute("UPDATE deal_stages SET probability = probability * 100 WHERE probability <= 1.0")
            print("✓ Converted probability values from 0.0-1.0 to 0-100 range")
        
        conn.commit()
        print("\n✓ Migration completed successfully")
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Migration failed: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
