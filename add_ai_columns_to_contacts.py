"""
SQLite için contacts tablosuna AI kolonlarını ekleyen script
"""
import sqlite3
import os

# Database path
db_path = 'instance/whatsapp_crm.db'

if not os.path.exists(db_path):
    print(f"❌ Database file not found: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Check existing columns
cur.execute("PRAGMA table_info(contacts)")
existing_columns = {row[1] for row in cur.fetchall()}

print(f"Existing columns in contacts table: {len(existing_columns)}")

# AI columns to add
ai_columns = {
    'ai_insight': 'TEXT DEFAULT NULL',
    'ai_scored_at': 'TIMESTAMP DEFAULT NULL'
}

added = []
skipped = []

for col_name, col_def in ai_columns.items():
    if col_name in existing_columns:
        print(f"⏭️  Column '{col_name}' already exists, skipping")
        skipped.append(col_name)
    else:
        try:
            cur.execute(f"ALTER TABLE contacts ADD COLUMN {col_name} {col_def}")
            print(f"✅ Added column: {col_name}")
            added.append(col_name)
        except Exception as e:
            print(f"❌ Error adding {col_name}: {e}")

if added:
    conn.commit()
    print(f"\n✅ Successfully added {len(added)} columns: {', '.join(added)}")
else:
    print(f"\n⏭️  No new columns added. All {len(skipped)} columns already exist.")

conn.close()
print("\n✓ Migration completed!")
