"""
Migration: Add Google Drive Attachments Table
"""
from app import app, db
from sqlalchemy import text

def migrate():
    with app.app_context():
        print("🔄 Creating drive_attachments table...")
        
        # Create drive_attachments table
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS drive_attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL,
                drive_file_id VARCHAR(200) NOT NULL,
                file_name VARCHAR(500) NOT NULL,
                mime_type VARCHAR(100),
                file_size BIGINT,
                thumbnail_url VARCHAR(1000),
                web_view_link VARCHAR(1000),
                entity_type VARCHAR(50) NOT NULL,
                entity_id INTEGER NOT NULL,
                attached_by INTEGER,
                attached_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                FOREIGN KEY (attached_by) REFERENCES users(id)
            )
        """))
        
        # Create indexes
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_drive_attachments_workspace 
            ON drive_attachments(workspace_id)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_drive_attachments_file 
            ON drive_attachments(drive_file_id)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_drive_attachments_entity 
            ON drive_attachments(entity_type, entity_id)
        """))
        
        db.session.commit()
        print("✅ Migration complete!")

if __name__ == '__main__':
    migrate()
