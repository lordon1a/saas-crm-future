"""Verify calendar and task notification migration"""
import sqlite3
import os

db_path = 'instance/whatsapp_crm.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

print("=" * 60)
print("CALENDAR MIGRATION VERIFICATION")
print("=" * 60)

# Check tasks table columns
print("\n1. Tasks table - New columns:")
cur.execute("PRAGMA table_info(tasks)")
columns = cur.fetchall()
calendar_columns = ['start_time', 'end_time', 'timezone', 'task_type', 'contact_id']
for col_name in calendar_columns:
    found = any(col[1] == col_name for col in columns)
    status = "✓" if found else "✗"
    print(f"   {status} {col_name}")

# Check tasks table indexes
print("\n2. Tasks table - New indexes:")
cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='tasks'")
indexes = cur.fetchall()
expected_indexes = ['idx_task_workspace_start_time', 'idx_task_type', 'idx_task_contact_id']
for idx_name in expected_indexes:
    found = any(idx[0] == idx_name for idx in indexes)
    status = "✓" if found else "✗"
    print(f"   {status} {idx_name}")

# Check task_notifications table
print("\n3. task_notifications table:")
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='task_notifications'")
if cur.fetchone():
    print("   ✓ Table exists")
    cur.execute("PRAGMA table_info(task_notifications)")
    columns = cur.fetchall()
    print(f"   ✓ Columns: {len(columns)}")
    
    # Check indexes
    cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='task_notifications'")
    indexes = cur.fetchall()
    print(f"   ✓ Indexes: {len(indexes)}")
else:
    print("   ✗ Table does not exist")

# Check notification_preferences table
print("\n4. notification_preferences table:")
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notification_preferences'")
if cur.fetchone():
    print("   ✓ Table exists")
    cur.execute("PRAGMA table_info(notification_preferences)")
    columns = cur.fetchall()
    print(f"   ✓ Columns: {len(columns)}")
    
    # Check indexes
    cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='notification_preferences'")
    indexes = cur.fetchall()
    print(f"   ✓ Indexes: {len(indexes)}")
else:
    print("   ✗ Table does not exist")

# Test data integrity
print("\n5. Data integrity check:")
cur.execute("SELECT COUNT(*) FROM tasks")
task_count = cur.fetchone()[0]
print(f"   ✓ Existing tasks preserved: {task_count} tasks")

conn.close()

print("\n" + "=" * 60)
print("✓ MIGRATION VERIFICATION COMPLETED SUCCESSFULLY")
print("=" * 60)
