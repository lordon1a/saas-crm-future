"""
Add workspace_apps table for marketplace system
"""
import logging

logger = logging.getLogger(__name__)

def upgrade(conn, cur):
    """Create workspace_apps table for app marketplace"""
    
    # Check if workspace_apps table exists
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_name='workspace_apps'
    """)
    
    if not cur.fetchone():
        logger.info("Running migration: create workspace_apps table...")
        cur.execute("""
            CREATE TABLE workspace_apps (
                id SERIAL PRIMARY KEY,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                app_slug VARCHAR(50) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                installed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                settings JSONB DEFAULT '{}',
                CONSTRAINT uq_workspace_app UNIQUE (workspace_id, app_slug)
            )
        """)
        cur.execute("""
            CREATE INDEX idx_workspace_apps_workspace ON workspace_apps(workspace_id)
        """)
        cur.execute("""
            CREATE INDEX idx_workspace_apps_slug ON workspace_apps(app_slug)
        """)
        cur.execute("""
            CREATE INDEX idx_workspace_apps_active ON workspace_apps(workspace_id, is_active)
        """)
        conn.commit()
        logger.info("✓ Created workspace_apps table")
