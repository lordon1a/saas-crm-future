"""
Migration script - messages tablosuna is_read sütunu ekler
SQLite ve PostgreSQL desteklidir
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///whatsapp_crm.db')

if DATABASE_URL.startswith('sqlite'):
    import sqlite3
    # SQLite dosya yolu
    db_path = DATABASE_URL.replace('sqlite:///', '')
    if not db_path.startswith('/'):
        db_path = os.path.join(os.getcwd(), db_path)
    # instance klasörünü de kontrol et
    instance_path = os.path.join(os.getcwd(), 'instance', db_path.split('/')[-1].split('\\')[-1])
    
    paths_to_try = [db_path, instance_path]
    
    for path in paths_to_try:
        if os.path.exists(path):
            print(f"Found DB at: {path}")
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            
            # Sütunun var olup olmadığını kontrol et
            cursor.execute("PRAGMA table_info(messages)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'is_read' not in columns:
                cursor.execute("ALTER TABLE messages ADD COLUMN is_read BOOLEAN DEFAULT 0 NOT NULL")
                conn.commit()
                print("✅ is_read column added to messages table!")
            else:
                print("ℹ️  is_read column already exists.")
            
            conn.close()
            break
    else:
        print("❌ SQLite database file not found. Searched:")
        for p in paths_to_try:
            print(f"  - {p}")
        sys.exit(1)

else:
    # PostgreSQL
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name='messages' AND column_name='is_read'
        """)
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute("ALTER TABLE messages ADD COLUMN is_read BOOLEAN DEFAULT FALSE NOT NULL")
            conn.commit()
            print("✅ is_read column added to messages table!")
        else:
            print("ℹ️  is_read column already exists.")
        
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

print("Migration completed.")
