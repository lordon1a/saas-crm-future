"""
Migration: Add calendar and task management features
Adds calendar fields to tasks table, creates task_notifications and notification_preferences tables
"""
import sqlite3
import os
import sys

def migrate():
    """Add calendar and task management features"""
    database_url = os.environ.get('DATABASE_URL')
    
    # Use SQLite for local development
    if not database_url:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'whatsapp_crm.db')
        if not os.path.exists(db_path):
            print(f"Database not found at {db_path}")
            sys.exit(1)
        return migrate_sqlite(db_path)
    
    # Use PostgreSQL for production
    return migrate_postgres(database_url)

def migrate_sqlite(db_path):
    """SQLite migration"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Connected to SQLite database successfully")
        
        # Check existing columns in tasks table
        cursor.execute("PRAGMA table_info(tasks)")
        columns = [col[1] for col in cursor.fetchall()]
        
        print("\nAdding calendar columns to tasks table...")
        
        # Add start_time column
        if 'start_time' not in columns:
            cursor.execute("""
                ALTER TABLE tasks 
                ADD COLUMN start_time TIMESTAMP
            """)
            print("✓ Added start_time column to tasks")
        else:
            print("✓ start_time column already exists")
        
        # Add end_time column
        if 'end_time' not in columns:
            cursor.execute("""
                ALTER TABLE tasks 
                ADD COLUMN end_time TIMESTAMP
            """)
            print("✓ Added end_time column to tasks")
        else:
            print("✓ end_time column already exists")
        
        # Add timezone column
        if 'timezone' not in columns:
            cursor.execute("""
                ALTER TABLE tasks 
                ADD COLUMN timezone VARCHAR(50) DEFAULT 'UTC' NOT NULL
            """)
            print("✓ Added timezone column to tasks")
        else:
            print("✓ timezone column already exists")
        
        # Add task_type column
        if 'task_type' not in columns:
            cursor.execute("""
                ALTER TABLE tasks 
                ADD COLUMN task_type VARCHAR(50) DEFAULT 'task' NOT NULL
            """)
            print("✓ Added task_type column to tasks")
        else:
            print("✓ task_type column already exists")
        
        # Add contact_id column
        if 'contact_id' not in columns:
            cursor.execute("""
                ALTER TABLE tasks 
                ADD COLUMN contact_id INTEGER
            """)
            print("✓ Added contact_id column to tasks")
        else:
            print("✓ contact_id column already exists")
        
        # Create indexes on tasks table
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_workspace_start_time 
                ON tasks(workspace_id, start_time)
            """)
            print("✓ Created index on (workspace_id, start_time)")
        except Exception as e:
            print(f"⚠ Index on (workspace_id, start_time) may already exist: {e}")
        
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_type 
                ON tasks(task_type)
            """)
            print("✓ Created index on task_type")
        except Exception as e:
            print(f"⚠ Index on task_type may already exist: {e}")
        
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_contact_id 
                ON tasks(contact_id)
            """)
            print("✓ Created index on contact_id")
        except Exception as e:
            print(f"⚠ Index on contact_id may already exist: {e}")
        
        # Check if task_notifications table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='task_notifications'
        """)
        
        if not cursor.fetchone():
            print("\nCreating task_notifications table...")
            cursor.execute("""
                CREATE TABLE task_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER NOT NULL,
                    task_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    notify_at TIMESTAMP NOT NULL,
                    message VARCHAR(500) NOT NULL,
                    notification_type VARCHAR(50) DEFAULT 'task_reminder' NOT NULL,
                    is_sent BOOLEAN DEFAULT 0 NOT NULL,
                    sent_at TIMESTAMP,
                    is_read BOOLEAN DEFAULT 0 NOT NULL,
                    read_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            print("✓ Created task_notifications table")
            
            # Create indexes on task_notifications
            cursor.execute("""
                CREATE INDEX idx_notification_workspace_id 
                ON task_notifications(workspace_id)
            """)
            cursor.execute("""
                CREATE INDEX idx_notification_task_id 
                ON task_notifications(task_id)
            """)
            cursor.execute("""
                CREATE INDEX idx_notification_user_id 
                ON task_notifications(user_id)
            """)
            cursor.execute("""
                CREATE INDEX idx_notification_notify_at 
                ON task_notifications(notify_at)
            """)
            cursor.execute("""
                CREATE INDEX idx_notification_pending 
                ON task_notifications(is_sent, notify_at)
            """)
            cursor.execute("""
                CREATE INDEX idx_notification_user_unread 
                ON task_notifications(user_id, is_read)
            """)
            cursor.execute("""
                CREATE INDEX idx_notification_workspace_user 
                ON task_notifications(workspace_id, user_id)
            """)
            print("✓ Created indexes on task_notifications table")
        else:
            print("✓ task_notifications table already exists")
        
        # Check if notification_preferences table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='notification_preferences'
        """)
        
        if not cursor.fetchone():
            print("\nCreating notification_preferences table...")
            cursor.execute("""
                CREATE TABLE notification_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    task_reminder_enabled BOOLEAN DEFAULT 1 NOT NULL,
                    task_overdue_enabled BOOLEAN DEFAULT 1 NOT NULL,
                    task_assigned_enabled BOOLEAN DEFAULT 1 NOT NULL,
                    task_updated_enabled BOOLEAN DEFAULT 0 NOT NULL,
                    reminder_minutes_before INTEGER DEFAULT 15 NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    UNIQUE (workspace_id, user_id)
                )
            """)
            print("✓ Created notification_preferences table")
            
            # Create indexes on notification_preferences
            cursor.execute("""
                CREATE INDEX idx_notification_pref_workspace_id 
                ON notification_preferences(workspace_id)
            """)
            cursor.execute("""
                CREATE INDEX idx_notification_pref_user_id 
                ON notification_preferences(user_id)
            """)
            print("✓ Created indexes on notification_preferences table")
        else:
            print("✓ notification_preferences table already exists")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\n✓ SQLite migration completed successfully")
        
    except Exception as e:
        print(f"\n✗ Migration failed: {str(e)}")
        conn.rollback()
        conn.close()
        sys.exit(1)

def migrate_postgres(database_url):
    """PostgreSQL migration"""
    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed. Install with: pip install psycopg2-binary")
        sys.exit(1)
    
    # Fix for Render's postgres:// URL
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        print("Connected to PostgreSQL database successfully")
        
        print("\nAdding calendar columns to tasks table...")
        
        # Check and add start_time column
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='tasks' AND column_name='start_time'
        """)
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE tasks 
                ADD COLUMN start_time TIMESTAMP
            """)
            conn.commit()
            print("✓ Added start_time column to tasks")
        else:
            print("✓ start_time column already exists")
        
        # Check and add end_time column
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='tasks' AND column_name='end_time'
        """)
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE tasks 
                ADD COLUMN end_time TIMESTAMP
            """)
            conn.commit()
            print("✓ Added end_time column to tasks")
        else:
            print("✓ end_time column already exists")
        
        # Check and add timezone column
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='tasks' AND column_name='timezone'
        """)
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE tasks 
                ADD COLUMN timezone VARCHAR(50) DEFAULT 'UTC' NOT NULL
            """)
            conn.commit()
            print("✓ Added timezone column to tasks")
        else:
            print("✓ timezone column already exists")
        
        # Check and add task_type column
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='tasks' AND column_name='task_type'
        """)
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE tasks 
                ADD COLUMN task_type VARCHAR(50) DEFAULT 'task' NOT NULL
            """)
            conn.commit()
            print("✓ Added task_type column to tasks")
        else:
            print("✓ task_type column already exists")
        
        # Check and add contact_id column
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='tasks' AND column_name='contact_id'
        """)
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE tasks 
                ADD COLUMN contact_id INTEGER REFERENCES contacts(id)
            """)
            conn.commit()
            print("✓ Added contact_id column to tasks")
        else:
            print("✓ contact_id column already exists")
        
        # Create indexes on tasks table
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_workspace_start_time 
            ON tasks(workspace_id, start_time)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_type 
            ON tasks(task_type)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_contact_id 
            ON tasks(contact_id)
        """)
        conn.commit()
        print("✓ Created indexes on tasks table")
        
        # Check if task_notifications table exists
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name='task_notifications'
        """)
        
        if not cur.fetchone():
            print("\nCreating task_notifications table...")
            cur.execute("""
                CREATE TABLE task_notifications (
                    id SERIAL PRIMARY KEY,
                    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    notify_at TIMESTAMP NOT NULL,
                    message VARCHAR(500) NOT NULL,
                    notification_type VARCHAR(50) DEFAULT 'task_reminder' NOT NULL,
                    is_sent BOOLEAN DEFAULT FALSE NOT NULL,
                    sent_at TIMESTAMP,
                    is_read BOOLEAN DEFAULT FALSE NOT NULL,
                    read_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW() NOT NULL
                )
            """)
            conn.commit()
            print("✓ Created task_notifications table")
            
            # Create indexes on task_notifications
            cur.execute("""
                CREATE INDEX idx_notification_workspace_id 
                ON task_notifications(workspace_id)
            """)
            cur.execute("""
                CREATE INDEX idx_notification_task_id 
                ON task_notifications(task_id)
            """)
            cur.execute("""
                CREATE INDEX idx_notification_user_id 
                ON task_notifications(user_id)
            """)
            cur.execute("""
                CREATE INDEX idx_notification_notify_at 
                ON task_notifications(notify_at)
            """)
            cur.execute("""
                CREATE INDEX idx_notification_pending 
                ON task_notifications(is_sent, notify_at)
            """)
            cur.execute("""
                CREATE INDEX idx_notification_user_unread 
                ON task_notifications(user_id, is_read)
            """)
            cur.execute("""
                CREATE INDEX idx_notification_workspace_user 
                ON task_notifications(workspace_id, user_id)
            """)
            conn.commit()
            print("✓ Created indexes on task_notifications table")
        else:
            print("✓ task_notifications table already exists")
        
        # Check if notification_preferences table exists
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name='notification_preferences'
        """)
        
        if not cur.fetchone():
            print("\nCreating notification_preferences table...")
            cur.execute("""
                CREATE TABLE notification_preferences (
                    id SERIAL PRIMARY KEY,
                    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    task_reminder_enabled BOOLEAN DEFAULT TRUE NOT NULL,
                    task_overdue_enabled BOOLEAN DEFAULT TRUE NOT NULL,
                    task_assigned_enabled BOOLEAN DEFAULT TRUE NOT NULL,
                    task_updated_enabled BOOLEAN DEFAULT FALSE NOT NULL,
                    reminder_minutes_before INTEGER DEFAULT 15 NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
                    UNIQUE (workspace_id, user_id)
                )
            """)
            conn.commit()
            print("✓ Created notification_preferences table")
            
            # Create indexes on notification_preferences
            cur.execute("""
                CREATE INDEX idx_notification_pref_workspace_id 
                ON notification_preferences(workspace_id)
            """)
            cur.execute("""
                CREATE INDEX idx_notification_pref_user_id 
                ON notification_preferences(user_id)
            """)
            conn.commit()
            print("✓ Created indexes on notification_preferences table")
        else:
            print("✓ notification_preferences table already exists")
        
        cur.close()
        conn.close()
        
        print("\n✓ PostgreSQL migration completed successfully")
        
    except Exception as e:
        print(f"\n✗ Migration failed: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        sys.exit(1)

def downgrade():
    """Remove calendar and task management features"""
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'whatsapp_crm.db')
        if not os.path.exists(db_path):
            print(f"Database not found at {db_path}")
            sys.exit(1)
        return downgrade_sqlite(db_path)
    
    return downgrade_postgres(database_url)

def downgrade_sqlite(db_path):
    """SQLite downgrade - Note: SQLite doesn't support DROP COLUMN"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Connected to SQLite database successfully")
        
        # Drop notification_preferences table
        cursor.execute("DROP TABLE IF EXISTS notification_preferences")
        print("✓ Dropped notification_preferences table")
        
        # Drop task_notifications table
        cursor.execute("DROP TABLE IF EXISTS task_notifications")
        print("✓ Dropped task_notifications table")
        
        print("⚠ Note: SQLite doesn't support DROP COLUMN. Calendar columns will remain in tasks table.")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✓ SQLite downgrade completed")
        
    except Exception as e:
        print(f"✗ Downgrade failed: {str(e)}")
        conn.rollback()
        conn.close()
        sys.exit(1)

def downgrade_postgres(database_url):
    """PostgreSQL downgrade"""
    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed")
        sys.exit(1)
    
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        print("Connected to PostgreSQL database successfully")
        
        # Drop notification_preferences table
        cur.execute("DROP TABLE IF EXISTS notification_preferences CASCADE")
        print("✓ Dropped notification_preferences table")
        
        # Drop task_notifications table
        cur.execute("DROP TABLE IF EXISTS task_notifications CASCADE")
        print("✓ Dropped task_notifications table")
        
        # Remove columns from tasks table
        cur.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS start_time")
        cur.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS end_time")
        cur.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS timezone")
        cur.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS task_type")
        cur.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS contact_id")
        print("✓ Removed calendar columns from tasks table")
        
        conn.commit()
        cur.close()
        conn.close()
        
        print("✓ PostgreSQL downgrade completed successfully")
        
    except Exception as e:
        print(f"✗ Downgrade failed: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'downgrade':
        downgrade()
    else:
        migrate()
