"""
Message tablosuna media_type ve media_url sütunlarını ekler.
Mevcut veritabanında bu sütunlar yoksa eklenir.
"""
import sqlite3
import os
from dotenv import load_dotenv
load_dotenv()

def migrate_sqlite():
    db_path = os.getenv('DATABASE_URL', 'sqlite:///whatsapp_crm.db').replace('sqlite:///', '')
    if not db_path:
        return
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(__file__), db_path)
    if not os.path.isfile(db_path):
        print('SQLite file not found:', db_path)
        return
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(messages)")
    cols = [r[1] for r in cur.fetchall()]
    if 'media_type' not in cols:
        cur.execute('ALTER TABLE messages ADD COLUMN media_type VARCHAR(20)')
        print('Added media_type.')
    if 'media_url' not in cols:
        cur.execute('ALTER TABLE messages ADD COLUMN media_url VARCHAR(500)')
        print('Added media_url.')
    conn.commit()
    conn.close()
    print('Migration done.')

if __name__ == '__main__':
    migrate_sqlite()
