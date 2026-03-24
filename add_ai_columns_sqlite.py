"""
Add AI columns to SQLite database - run this once
"""
import sqlite3
import os

if not os.path.exists('crm.db'):
    print("❌ crm.db not found. Start the app first to create the database.")
    exit(1)

conn = sqlite3.connect('crm.db')
cur = conn.cursor()

print("Adding AI columns to SQLite...")

# Get existing columns
def get_columns(table):
    cur.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]

# Deals table
deals_cols = get_columns('deals')
print(f"\nDeals table has {len(deals_cols)} columns")

if 'ai_score' not in deals_cols:
    cur.execute("ALTER TABLE deals ADD COLUMN ai_score INTEGER")
    print("✓ Added deals.ai_score")
else:
    print("  deals.ai_score exists")

if 'ai_score_label' not in deals_cols:
    cur.execute("ALTER TABLE deals ADD COLUMN ai_score_label VARCHAR(20)")
    print("✓ Added deals.ai_score_label")
else:
    print("  deals.ai_score_label exists")

if 'ai_insight' not in deals_cols:
    cur.execute("ALTER TABLE deals ADD COLUMN ai_insight TEXT")
    print("✓ Added deals.ai_insight")
else:
    print("  deals.ai_insight exists")

if 'ai_scored_at' not in deals_cols:
    cur.execute("ALTER TABLE deals ADD COLUMN ai_scored_at TIMESTAMP")
    print("✓ Added deals.ai_scored_at")
else:
    print("  deals.ai_scored_at exists")

# Contacts table
contacts_cols = get_columns('contacts')
print(f"\nContacts table has {len(contacts_cols)} columns")

if 'ai_insight' not in contacts_cols:
    cur.execute("ALTER TABLE contacts ADD COLUMN ai_insight TEXT")
    print("✓ Added contacts.ai_insight")
else:
    print("  contacts.ai_insight exists")

if 'ai_scored_at' not in contacts_cols:
    cur.execute("ALTER TABLE contacts ADD COLUMN ai_scored_at TIMESTAMP")
    print("✓ Added contacts.ai_scored_at")
else:
    print("  contacts.ai_scored_at exists")

# Conversations table
conversations_cols = get_columns('conversations')
print(f"\nConversations table has {len(conversations_cols)} columns")

if 'ai_summary' not in conversations_cols:
    cur.execute("ALTER TABLE conversations ADD COLUMN ai_summary TEXT")
    print("✓ Added conversations.ai_summary")
else:
    print("  conversations.ai_summary exists")

if 'ai_summary_at' not in conversations_cols:
    cur.execute("ALTER TABLE conversations ADD COLUMN ai_summary_at TIMESTAMP")
    print("✓ Added conversations.ai_summary_at")
else:
    print("  conversations.ai_summary_at exists")

if 'ai_sentiment' not in conversations_cols:
    cur.execute("ALTER TABLE conversations ADD COLUMN ai_sentiment VARCHAR(20)")
    print("✓ Added conversations.ai_sentiment")
else:
    print("  conversations.ai_sentiment exists")

if 'ai_sentiment_score' not in conversations_cols:
    cur.execute("ALTER TABLE conversations ADD COLUMN ai_sentiment_score REAL")
    print("✓ Added conversations.ai_sentiment_score")
else:
    print("  conversations.ai_sentiment_score exists")

conn.commit()
conn.close()

print("\n✅ Done! Restart the app to clear schema mismatch warnings.")
