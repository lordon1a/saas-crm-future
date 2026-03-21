"""Add last_activity_at column to contacts table in SQLite"""
import sqlite3
import os

db_path = os.path.join('instance', 'whatsapp_crm.db')

if not os.path.exists(db_path):
    print(f"❌ Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Check if column exists
    cursor.execute("PRAGMA table_info(contacts)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'last_activity_at' in columns:
        print("✓ last_activity_at column already exists")
    else:
        print("Adding last_activity_at column...")
        cursor.execute("""
            ALTER TABLE contacts 
            ADD COLUMN last_activity_at TIMESTAMP
        """)
        conn.commit()
        print("✓ Added last_activity_at column")
        
        # Create index
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_contacts_last_activity_at 
            ON contacts(last_activity_at)
        """)
        conn.commit()
        print("✓ Created index on last_activity_at")
    
    cursor.close()
    conn.close()
    print("\n✅ Migration completed successfully!")
    
except Exception as e:
    print(f"\n❌ Migration failed: {str(e)}")
    conn.rollback()
    conn.close()
    exit(1)
