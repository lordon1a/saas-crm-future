"""
Migration: Add onboarding_progress table
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import db

def upgrade():
    """Create onboarding_progress table"""
    db.engine.execute("""
        CREATE TABLE IF NOT EXISTS onboarding_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL UNIQUE,
            channel_connected BOOLEAN DEFAULT 0,
            first_contact_added BOOLEAN DEFAULT 0,
            first_deal_created BOOLEAN DEFAULT 0,
            team_member_invited BOOLEAN DEFAULT 0,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
        )
    """)
    print("✅ onboarding_progress table created")

if __name__ == '__main__':
    upgrade()
