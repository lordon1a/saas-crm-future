"""
Migration script V2 - Adds tags to conversations and private_notes to customers
SQLite and PostgreSQL supported
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///whatsapp_crm.db')

if DATABASE_URL.startswith('sqlite'):
    import sqlite3
    db_path = DATABASE_URL.replace('sqlite:///', '')
    if not db_path.startswith('/'):
        db_path = os.path.join(os.getcwd(), db_path)
    instance_path = os.path.join(os.getcwd(), 'instance', db_path.split('/')[-1].split('\\')[-1])
    
    paths_to_try = [db_path, instance_path]
    
    for path in paths_to_try:
        if os.path.exists(path):
            print(f"Found DB at: {path}")
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            
            # Check conversations table
            cursor.execute("PRAGMA table_info(conversations)")
            conv_cols = [row[1] for row in cursor.fetchall()]
            
            if 'tags' not in conv_cols:
                cursor.execute("ALTER TABLE conversations ADD COLUMN tags VARCHAR(255)")
                print("✅ tags column added to conversations table")
            else:
                print("ℹ️ tags column already exists in conversations")
                
            # Check customers table
            cursor.execute("PRAGMA table_info(customers)")
            cust_cols = [row[1] for row in cursor.fetchall()]
            
            if 'private_notes' not in cust_cols:
                cursor.execute("ALTER TABLE customers ADD COLUMN private_notes TEXT")
                print("✅ private_notes column added to customers table")
            else:
                print("ℹ️ private_notes column already exists in customers")
            
            conn.commit()
            conn.close()
            break
    else:
        print("❌ SQLite database file not found.")
        sys.exit(1)

else:
    # PostgreSQL
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Check conversations
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='conversations' AND column_name='tags'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE conversations ADD COLUMN tags VARCHAR(255)")
            print("✅ tags column added to conversations")
            
        # Check customers
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='customers' AND column_name='private_notes'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE customers ADD COLUMN private_notes TEXT")
            print("✅ private_notes column added to customers")
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

print("Migration V2 completed.")
