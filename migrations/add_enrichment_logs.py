"""
Migration: add_enrichment_logs
Mesajlardan otomatik contact güncellemelerini loglar.
"""
from app import app, db
from sqlalchemy import text

def upgrade():
    """EnrichmentLog tablosunu oluştur."""
    with app.app_context():
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS enrichment_logs (
                id SERIAL PRIMARY KEY,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                source VARCHAR(50),
                field_name VARCHAR(50),
                old_value VARCHAR(200),
                new_value VARCHAR(200),
                confidence FLOAT,
                raw_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_enrichment_logs_workspace 
            ON enrichment_logs(workspace_id);
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_enrichment_logs_contact 
            ON enrichment_logs(contact_id);
        """))
        
        db.session.commit()
        print("✅ enrichment_logs table created")

def downgrade():
    """Geri al."""
    with app.app_context():
        db.session.execute(text("DROP TABLE IF EXISTS enrichment_logs CASCADE;"))
        db.session.commit()
        print("✅ enrichment_logs table dropped")

if __name__ == '__main__':
    upgrade()
