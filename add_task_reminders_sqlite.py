"""
SQLite Migration: Add reminder fields to tasks table
Run this with: python add_task_reminders_sqlite.py
"""
import sqlite3
import os

DB_PATH = 'instance/whatsapp_crm.db'  # SQLite database file

def upgrade():
    """Add reminder columns to tasks table"""
    if not os.path.exists(DB_PATH):
        print(f"Database file {DB_PATH} not found!")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(tasks)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'reminder_enabled' in columns:
            print("Reminder columns already exist, skipping migration")
            return
        
        # Add reminder columns one by one (SQLite doesn't support multiple ADD COLUMN)
        print("Adding reminder_enabled column...")
        cursor.execute("""
            ALTER TABLE tasks 
            ADD COLUMN reminder_enabled BOOLEAN DEFAULT 0 NOT NULL
        """)
        
        print("Adding reminder_minutes_before column...")
        cursor.execute("""
            ALTER TABLE tasks 
            ADD COLUMN reminder_minutes_before INTEGER DEFAULT 60
        """)
        
        print("Adding reminder_sent column...")
        cursor.execute("""
            ALTER TABLE tasks 
            ADD COLUMN reminder_sent BOOLEAN DEFAULT 0 NOT NULL
        """)
        
        print("Adding reminder_method column...")
        cursor.execute("""
            ALTER TABLE tasks 
            ADD COLUMN reminder_method VARCHAR(20) DEFAULT 'whatsapp'
        """)
        
        conn.commit()
        print("✅ Successfully added reminder columns to tasks table")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error adding reminder columns: {str(e)}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    print("Running task reminders migration for SQLite...")
    upgrade()
    print("Migration completed!")
