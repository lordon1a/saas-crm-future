"""
Run Contact Timeline Migration
Creates contact_notes and contact_activity_logs tables
"""
import sqlite3
import os

def run_migration():
    """Execute the contact timeline migration"""
    db_path = 'whatsapp_crm.db'
    
    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Read migration SQL
        with open('migrations_contact_timeline.sql', 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        # Execute migration
        print("Running contact timeline migration...")
        cursor.executescript(migration_sql)
        conn.commit()
        
        # Verify tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('contact_notes', 'contact_activity_logs')")
        tables = cursor.fetchall()
        
        if len(tables) == 2:
            print("✅ Migration successful!")
            print("   - contact_notes table created")
            print("   - contact_activity_logs table created")
            
            # Count existing activity logs
            cursor.execute("SELECT COUNT(*) FROM contact_activity_logs")
            count = cursor.fetchone()[0]
            print(f"   - {count} activity logs initialized")
            
            return True
        else:
            print("❌ Migration failed: Tables not created")
            return False
            
    except Exception as e:
        print(f"❌ Migration error: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    success = run_migration()
    exit(0 if success else 1)
