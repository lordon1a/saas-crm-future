"""
Add action dashboard tables and indexes

This migration creates tables for the daily action dashboard feature:
- dismissed_actions: Tracks dismissed action items (24h expiry)
- dashboard_settings: Workspace-level priority thresholds
- widget_engagements: Analytics tracking for action bell interactions

Also adds performance indexes on existing tables for action queries.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from sqlalchemy import text

def upgrade():
    """Create action dashboard tables and indexes"""
    with app.app_context():
        # Check if we're using SQLite or PostgreSQL
        is_sqlite = str(app.config.get('SQLALCHEMY_DATABASE_URI', '')).startswith('sqlite')
        
        if is_sqlite:
            # SQLite syntax
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS dismissed_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    action_id VARCHAR(100) NOT NULL,
                    dismissed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                )
            """))
            
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS dashboard_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER NOT NULL UNIQUE REFERENCES workspaces(id) ON DELETE CASCADE,
                    high_score_threshold INTEGER NOT NULL DEFAULT 70,
                    medium_score_threshold INTEGER NOT NULL DEFAULT 50,
                    high_score_staleness_days INTEGER NOT NULL DEFAULT 3,
                    medium_score_staleness_days INTEGER NOT NULL DEFAULT 7,
                    deal_close_warning_days INTEGER NOT NULL DEFAULT 7,
                    deal_stage_stale_days INTEGER NOT NULL DEFAULT 14,
                    deal_negotiation_stale_days INTEGER NOT NULL DEFAULT 5,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS widget_engagements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    event_type VARCHAR(50) NOT NULL,
                    action_id VARCHAR(100),
                    action_type VARCHAR(50),
                    priority VARCHAR(20),
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
        else:
            # PostgreSQL syntax
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS dismissed_actions (
                    id SERIAL PRIMARY KEY,
                    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    action_id VARCHAR(100) NOT NULL,
                    dismissed_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    expires_at TIMESTAMP NOT NULL
                )
            """))
            
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS dashboard_settings (
                    id SERIAL PRIMARY KEY,
                    workspace_id INTEGER NOT NULL UNIQUE REFERENCES workspaces(id) ON DELETE CASCADE,
                    high_score_threshold INTEGER NOT NULL DEFAULT 70,
                    medium_score_threshold INTEGER NOT NULL DEFAULT 50,
                    high_score_staleness_days INTEGER NOT NULL DEFAULT 3,
                    medium_score_staleness_days INTEGER NOT NULL DEFAULT 7,
                    deal_close_warning_days INTEGER NOT NULL DEFAULT 7,
                    deal_stage_stale_days INTEGER NOT NULL DEFAULT 14,
                    deal_negotiation_stale_days INTEGER NOT NULL DEFAULT 5,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """))
            
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS widget_engagements (
                    id SERIAL PRIMARY KEY,
                    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    event_type VARCHAR(50) NOT NULL,
                    action_id VARCHAR(100),
                    action_type VARCHAR(50),
                    priority VARCHAR(20),
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """))
        
        # Indexes for dismissed_actions
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_dismissed_workspace_id 
            ON dismissed_actions(workspace_id)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_dismissed_user_id 
            ON dismissed_actions(user_id)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_dismissed_action_id 
            ON dismissed_actions(action_id)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_dismissed_at 
            ON dismissed_actions(dismissed_at)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_dismissed_expires 
            ON dismissed_actions(expires_at)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_dismissed_workspace_user 
            ON dismissed_actions(workspace_id, user_id)
        """))
        
        # Indexes for dashboard_settings
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_dashboard_settings_workspace 
            ON dashboard_settings(workspace_id)
        """))
        
        # Indexes for widget_engagements
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_engagement_workspace_id 
            ON widget_engagements(workspace_id)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_engagement_user_id 
            ON widget_engagements(user_id)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_engagement_event_type 
            ON widget_engagements(event_type)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_engagement_action_id 
            ON widget_engagements(action_id)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_engagement_created 
            ON widget_engagements(created_at)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_engagement_workspace_user 
            ON widget_engagements(workspace_id, user_id)
        """))
        
        # Performance indexes on existing tables for action queries
        
        # Optimize contact queries for staleness (lead_score + last_activity_at)
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_contact_lead_score_activity 
            ON contacts(workspace_id, lead_score, last_activity_at) 
            WHERE is_deleted = FALSE
        """))
        
        # Optimize deal queries for close date
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_deal_close_date 
            ON deals(workspace_id, expected_close_date, status) 
            WHERE is_deleted = FALSE
        """))
        
        # Optimize deal queries for stage staleness
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_deal_stage_entered 
            ON deals(workspace_id, stage_entered_at, status) 
            WHERE is_deleted = FALSE
        """))
        
        # Optimize task queries for due date
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_task_due_date 
            ON tasks(workspace_id, due_date, status)
        """))
        
        db.session.commit()
        print("✅ Action dashboard tables and indexes created successfully")


def downgrade():
    """Drop action dashboard tables and indexes"""
    with app.app_context():
        # Drop indexes on existing tables
        db.session.execute(text("DROP INDEX IF EXISTS idx_task_due_date"))
        db.session.execute(text("DROP INDEX IF EXISTS idx_deal_stage_entered"))
        db.session.execute(text("DROP INDEX IF EXISTS idx_deal_close_date"))
        db.session.execute(text("DROP INDEX IF EXISTS idx_contact_lead_score_activity"))
        
        # Drop widget_engagements indexes and table
        db.session.execute(text("DROP INDEX IF EXISTS idx_engagement_workspace_user"))
        db.session.execute(text("DROP INDEX IF EXISTS idx_engagement_created"))
        db.session.execute(text("DROP INDEX IF EXISTS idx_engagement_action_id"))
        db.session.execute(text("DROP INDEX IF EXISTS idx_engagement_event_type"))
        db.session.execute(text("DROP INDEX IF EXISTS idx_engagement_user_id"))
        db.session.execute(text("DROP INDEX IF EXISTS idx_engagement_workspace_id"))
        db.session.execute(text("DROP TABLE IF EXISTS widget_engagements"))
        
        # Drop dashboard_settings indexes and table
        db.session.execute(text("DROP INDEX IF EXISTS idx_dashboard_settings_workspace"))
        db.session.execute(text("DROP TABLE IF EXISTS dashboard_settings"))
        
        # Drop dismissed_actions indexes and table
        db.session.execute(text("DROP INDEX IF EXISTS idx_dismissed_workspace_user"))
        db.session.execute(text("DROP INDEX IF EXISTS idx_dismissed_expires"))
        db.session.execute(text("DROP INDEX IF EXISTS idx_dismissed_at"))
        db.session.execute(text("DROP INDEX IF EXISTS idx_dismissed_action_id"))
        db.session.execute(text("DROP INDEX IF EXISTS idx_dismissed_user_id"))
        db.session.execute(text("DROP INDEX IF EXISTS idx_dismissed_workspace_id"))
        db.session.execute(text("DROP TABLE IF EXISTS dismissed_actions"))
        
        db.session.commit()
        print("✅ Action dashboard tables and indexes dropped successfully")


if __name__ == '__main__':
    upgrade()
