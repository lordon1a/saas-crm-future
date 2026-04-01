"""
Add customizable dashboard widgets table

This migration creates the dashboard_widgets table for Feature 1.3:
- Allows users to customize which analytics widgets they see on their dashboard
- Supports multiple widget types: kpi_card, bar_chart, funnel, pie_chart, 
  leaderboard, activity_feed, goal_progress, heatmap
- Stores widget position and size for grid layout
- Stores widget-specific configuration in config_json

Widget types and config_json examples:
- kpi_card: {"metric": "total_revenue", "period": "this_month", "pipeline_id": null}
- bar_chart: {"metric": "revenue_by_month", "period": "last_6_months", "pipeline_id": null}
- leaderboard: {"metric": "won_deals", "period": "this_month", "limit": 10}
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from sqlalchemy import text

def upgrade():
    """Create dashboard_widgets table and indexes"""
    with app.app_context():
        # Check if we're using SQLite or PostgreSQL
        is_sqlite = str(app.config.get('SQLALCHEMY_DATABASE_URI', '')).startswith('sqlite')
        
        if is_sqlite:
            # SQLite syntax
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS dashboard_widgets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    widget_type VARCHAR(50) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    config_json TEXT,
                    pos_x INTEGER NOT NULL DEFAULT 0,
                    pos_y INTEGER NOT NULL DEFAULT 0,
                    width INTEGER NOT NULL DEFAULT 4,
                    height INTEGER NOT NULL DEFAULT 3,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
        else:
            # PostgreSQL syntax
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS dashboard_widgets (
                    id SERIAL PRIMARY KEY,
                    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    widget_type VARCHAR(50) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    config_json TEXT,
                    pos_x INTEGER NOT NULL DEFAULT 0,
                    pos_y INTEGER NOT NULL DEFAULT 0,
                    width INTEGER NOT NULL DEFAULT 4,
                    height INTEGER NOT NULL DEFAULT 3,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """))
        
        # Indexes for dashboard_widgets
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_dashboard_widgets_workspace_id 
            ON dashboard_widgets(workspace_id)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_dashboard_widgets_user_id 
            ON dashboard_widgets(user_id)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_dashboard_widgets_workspace_user 
            ON dashboard_widgets(workspace_id, user_id)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_dashboard_widgets_widget_type 
            ON dashboard_widgets(widget_type)
        """))
        
        # Composite index for grid layout positioning
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_dashboard_widgets_grid_position 
            ON dashboard_widgets(workspace_id, user_id, pos_x, pos_y)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_dashboard_widgets_created 
            ON dashboard_widgets(created_at)
        """))
        
        db.session.commit()
        print("[OK] Dashboard widgets table and indexes created successfully")


def downgrade():
    """Drop dashboard_widgets table and indexes"""
    with app.app_context():
        # Drop indexes
        db.session.execute(text("DROP INDEX IF EXISTS idx_dashboard_widgets_created"))
        db.session.execute(text("DROP INDEX IF EXISTS idx_dashboard_widgets_grid_position"))
        db.session.execute(text("DROP INDEX IF EXISTS idx_dashboard_widgets_widget_type"))
        db.session.execute(text("DROP INDEX IF EXISTS idx_dashboard_widgets_workspace_user"))
        db.session.execute(text("DROP INDEX IF EXISTS idx_dashboard_widgets_user_id"))
        db.session.execute(text("DROP INDEX IF EXISTS idx_dashboard_widgets_workspace_id"))
        
        # Drop table
        db.session.execute(text("DROP TABLE IF EXISTS dashboard_widgets"))
        
        db.session.commit()
        print("[OK] Dashboard widgets table and indexes dropped successfully")


if __name__ == '__main__':
    upgrade()
