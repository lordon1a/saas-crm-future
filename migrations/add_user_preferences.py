import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'whatsapp_crm.db')

COLUMNS = [
    ("avatar_url",              "VARCHAR(255)"),
    ("timezone",                "VARCHAR(100) DEFAULT 'auto'"),
    ("date_format",             "VARCHAR(20)  DEFAULT 'DD/MM/YYYY'"),
    ("language",                "VARCHAR(10)  DEFAULT 'tr'"),
    ("currency",                "VARCHAR(10)  DEFAULT 'TRY'"),
    ("pref_activity_after_win", "BOOLEAN      DEFAULT 0"),
    ("pref_detail_deal",        "BOOLEAN      DEFAULT 1"),
    ("pref_detail_contact",     "BOOLEAN      DEFAULT 1"),
    ("pref_detail_org",         "BOOLEAN      DEFAULT 1"),
    ("pref_us_phone",           "BOOLEAN      DEFAULT 0"),
    ("pref_email_new_tab",      "BOOLEAN      DEFAULT 0"),
    ("pref_win_celebration",    "BOOLEAN      DEFAULT 1"),
    ("pref_auto_labels",        "BOOLEAN      DEFAULT 0"),
]

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(users)")
existing = {row[1] for row in cursor.fetchall()}

added = []
for col_name, col_def in COLUMNS:
    if col_name not in existing:
        cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
        added.append(col_name)
        print(f"  + Added column: {col_name}")
    else:
        print(f"  ~ Skipped (exists): {col_name}")

conn.commit()
conn.close()
print(f"\nDone. {len(added)} column(s) added.")
