"""
Add DocGen tables for document generation
"""
import logging

logger = logging.getLogger(__name__)

def upgrade(conn, cur):
    """Create doc_templates and generated_documents tables"""
    
    # Check if doc_templates table exists
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_name='doc_templates'
    """)
    
    if not cur.fetchone():
        logger.info("Running migration: create doc_templates table...")
        cur.execute("""
            CREATE TABLE doc_templates (
                id SERIAL PRIMARY KEY,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                name VARCHAR(200) NOT NULL,
                description TEXT,
                file_path VARCHAR(500) NOT NULL,
                file_type VARCHAR(10) NOT NULL,
                object_type VARCHAR(100),
                field_map JSONB,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                version INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE INDEX idx_doc_templates_workspace ON doc_templates(workspace_id)
        """)
        cur.execute("""
            CREATE INDEX idx_doc_templates_active ON doc_templates(is_active)
        """)
        conn.commit()
        logger.info("✓ Created doc_templates table")
    
    # Check if generated_documents table exists
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_name='generated_documents'
    """)
    
    if not cur.fetchone():
        logger.info("Running migration: create generated_documents table...")
        cur.execute("""
            CREATE TABLE generated_documents (
                id SERIAL PRIMARY KEY,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                template_id INTEGER NOT NULL REFERENCES doc_templates(id) ON DELETE CASCADE,
                record_id INTEGER NOT NULL,
                record_type VARCHAR(100),
                output_path VARCHAR(500),
                output_type VARCHAR(10),
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                error_msg TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE INDEX idx_generated_doc_workspace ON generated_documents(workspace_id)
        """)
        cur.execute("""
            CREATE INDEX idx_generated_doc_template ON generated_documents(template_id)
        """)
        cur.execute("""
            CREATE INDEX idx_generated_doc_record ON generated_documents(workspace_id, record_type, record_id)
        """)
        cur.execute("""
            CREATE INDEX idx_generated_doc_status ON generated_documents(workspace_id, status, created_at)
        """)
        conn.commit()
        logger.info("✓ Created generated_documents table")
