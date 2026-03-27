"""
Add is_first_login column to users table
This migration adds a boolean field to track if a user is logging in for the first time
"""
import sqlite3
import os

def upgrade():
    """Add is_first_login column to users table"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'whatsapp_crm.db')
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'is_first_login' in columns:
            print("✅ is_first_login column already exists in users table")
            return True
        
        # Add is_first_login column
        cursor.execute("""
            ALTER TABLE users ADD COLUMN is_first_login BOOLEAN DEFAULT 1 NOT NULL
        """)
        conn.commit()
        print("✅ is_first_login column added to users table")
        return True
    except Exception as e:
        conn.rollback()
        print(f"❌ Error adding is_first_login column: {e}")
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    upgrade()
