"""
Add ai_settings table for per-workspace AI API key storage
"""
import logging

logger = logging.getLogger(__name__)

def upgrade(conn, cur):
    """Create ai_settings table for encrypted AI API keys per workspace"""
    
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_name='ai_settings'
    """)
    
    if not cur.fetchone():
        logger.info("Running migration: create ai_settings table...")
        cur.execute("""
            CREATE TABLE ai_settings (
                id SERIAL PRIMARY KEY,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                provider VARCHAR(30) NOT NULL DEFAULT 'gemini',
                api_key_encrypted TEXT,
                model_name VARCHAR(100),
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_ai_settings_workspace_provider UNIQUE (workspace_id, provider)
            )
        """)
        cur.execute("""
            CREATE INDEX idx_ai_settings_workspace ON ai_settings(workspace_id)
        """)
        cur.execute("""
            CREATE INDEX idx_ai_settings_active ON ai_settings(workspace_id, is_active)
        """)
        conn.commit()
        logger.info("Created ai_settings table")
