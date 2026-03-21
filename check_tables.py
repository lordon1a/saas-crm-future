import sqlite3
import os

db_path = 'instance/whatsapp_crm.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Check for filter tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%filter%' ORDER BY name")
tables = cur.fetchall()

print("Filter-related tables:")
for table in tables:
    print(f"  ✓ {table[0]}")
    
    # Get column count
    cur.execute(f"PRAGMA table_info({table[0]})")
    columns = cur.fetchall()
    print(f"    Columns: {len(columns)}")

# Check indexes on contacts
print("\nIndexes on contacts table:")
cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='contacts' AND name LIKE 'idx_contact%'")
indexes = cur.fetchall()
for idx in indexes:
    print(f"  ✓ {idx[0]}")

# Check indexes on companies
print("\nIndexes on companies table:")
cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='companies' AND name LIKE 'idx_company%'")
indexes = cur.fetchall()
for idx in indexes:
    print(f"  ✓ {idx[0]}")

conn.close()
print("\n✓ Migration verification completed")
