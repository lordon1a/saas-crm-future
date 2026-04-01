"""
Add Meeting Links and Meeting Bookings tables
Migration: add_meeting_links
"""

from migration_base import *


def upgrade():
    """Create meeting_links and meeting_bookings tables"""
    
    # Meeting Links table
    conn = engine.connect()
    trans = conn.begin()
    
    try:
        # Create meeting_links table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS meeting_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                slug VARCHAR(100) NOT NULL UNIQUE,
                title VARCHAR(200) NOT NULL,
                duration_minutes INTEGER DEFAULT 30,
                buffer_minutes INTEGER DEFAULT 0,
                max_days_ahead INTEGER DEFAULT 60,
                availability_json TEXT,
                location VARCHAR(255),
                description TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspaces (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """))
        
        # Create meeting_bookings table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS meeting_bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_link_id INTEGER NOT NULL,
                workspace_id INTEGER NOT NULL,
                contact_id INTEGER,
                booker_name VARCHAR(200) NOT NULL,
                booker_email VARCHAR(255) NOT NULL,
                booker_notes TEXT,
                start_time DATETIME NOT NULL,
                end_time DATETIME NOT NULL,
                status VARCHAR(20) DEFAULT 'confirmed',
                google_calendar_event_id VARCHAR(255),
                zoom_meeting_url VARCHAR(500),
                confirmation_token VARCHAR(100) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (meeting_link_id) REFERENCES meeting_links (id),
                FOREIGN KEY (workspace_id) REFERENCES workspaces (id),
                FOREIGN KEY (contact_id) REFERENCES contacts (id)
            )
        """))
        
        # Create indexes
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_meeting_links_slug ON meeting_links(slug)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_meeting_links_user ON meeting_links(user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_meeting_bookings_link ON meeting_bookings(meeting_link_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_meeting_bookings_token ON meeting_bookings(confirmation_token)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_meeting_bookings_email ON meeting_bookings(booker_email)"))
        
        trans.commit()
        print("Migration add_meeting_links completed successfully")
        
    except Exception as e:
        trans.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


def downgrade():
    """Drop meeting_links and meeting_bookings tables"""
    conn = engine.connect()
    trans = conn.begin()
    
    try:
        conn.execute(text("DROP TABLE IF EXISTS meeting_bookings"))
        conn.execute(text("DROP TABLE IF EXISTS meeting_links"))
        trans.commit()
        print("Migration add_meeting_links rolled back successfully")
    except Exception as e:
        trans.rollback()
        print(f"Rollback failed: {e}")
        raise
    finally:
        conn.close()
