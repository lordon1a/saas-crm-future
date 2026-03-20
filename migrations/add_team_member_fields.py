"""
Migration: Add team member fields to User and create TeamInvitation table
Run this script to add team member management functionality
"""
import sqlite3
import os
import sys

def migrate():
    """Add team member fields to User and create TeamInvitation table"""
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
        
        # Check existing columns in users table
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        
        print("\nAdding new columns to users table...")
        
        # Add is_active column
        if 'is_active' not in columns:
            cursor.execute("""
                ALTER TABLE users 
                ADD COLUMN is_active BOOLEAN DEFAULT 1 NOT NULL
            """)
            print("✓ Added is_active column to users")
        else:
            print("✓ is_active column already exists")
        
        # Add created_at column
        if 'created_at' not in columns:
            cursor.execute("""
                ALTER TABLE users 
                ADD COLUMN created_at TIMESTAMP
            """)
            # Update existing rows with current timestamp
            cursor.execute("""
                UPDATE users 
                SET created_at = CURRENT_TIMESTAMP 
                WHERE created_at IS NULL
            """)
            print("✓ Added created_at column to users")
        else:
            print("✓ created_at column already exists")
        
        # Add last_login column
        if 'last_login' not in columns:
            cursor.execute("""
                ALTER TABLE users 
                ADD COLUMN last_login TIMESTAMP
            """)
            print("✓ Added last_login column to users")
        else:
            print("✓ last_login column already exists")
        
        # Add deleted_at column
        if 'deleted_at' not in columns:
            cursor.execute("""
                ALTER TABLE users 
                ADD COLUMN deleted_at TIMESTAMP
            """)
            print("✓ Added deleted_at column to users")
        else:
            print("✓ deleted_at column already exists")
        
        # Update existing users to have role='owner' if they have role='agent'
        cursor.execute("""
            UPDATE users 
            SET role = 'owner' 
            WHERE role = 'agent'
        """)
        affected_rows = cursor.rowcount
        if affected_rows > 0:
            print(f"✓ Updated {affected_rows} existing users from 'agent' to 'owner' role")
        
        # Check if team_invitations table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='team_invitations'
        """)
        
        if not cursor.fetchone():
            # Create team_invitations table
            cursor.execute("""
                CREATE TABLE team_invitations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER NOT NULL,
                    inviter_id INTEGER NOT NULL,
                    invitee_email VARCHAR(120) NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    token VARCHAR(36) UNIQUE NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    accepted_at TIMESTAMP,
                    FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                    FOREIGN KEY (inviter_id) REFERENCES users(id)
                )
            """)
            print("✓ Created team_invitations table")
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX idx_team_invitations_workspace_id 
                ON team_invitations(workspace_id)
            """)
            cursor.execute("""
                CREATE INDEX idx_team_invitations_invitee_email 
                ON team_invitations(invitee_email)
            """)
            cursor.execute("""
                CREATE INDEX idx_team_invitations_token 
                ON team_invitations(token)
            """)
            cursor.execute("""
                CREATE INDEX idx_team_invitations_status 
                ON team_invitations(status)
            """)
            cursor.execute("""
                CREATE INDEX idx_team_invitations_expires_at 
                ON team_invitations(expires_at)
            """)
            
            # Create unique constraint index
            cursor.execute("""
                CREATE UNIQUE INDEX uix_workspace_email_pending 
                ON team_invitations(workspace_id, invitee_email, status)
            """)
            print("✓ Created indexes on team_invitations table")
        else:
            print("✓ team_invitations table already exists")
        
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
        
        # Add new columns to users table
        print("\nAdding new columns to users table...")
        
        # Check and add is_active column
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='is_active'
        """)
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE users 
                ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL
            """)
            conn.commit()
            print("✓ Added is_active column to users")
        else:
            print("✓ is_active column already exists")
        
        # Check and add created_at column
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='created_at'
        """)
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE users 
                ADD COLUMN created_at TIMESTAMP DEFAULT NOW() NOT NULL
            """)
            conn.commit()
            print("✓ Added created_at column to users")
        else:
            print("✓ created_at column already exists")
        
        # Check and add last_login column
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='last_login'
        """)
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE users 
                ADD COLUMN last_login TIMESTAMP
            """)
            conn.commit()
            print("✓ Added last_login column to users")
        else:
            print("✓ last_login column already exists")
        
        # Check and add deleted_at column
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='deleted_at'
        """)
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE users 
                ADD COLUMN deleted_at TIMESTAMP
            """)
            conn.commit()
            print("✓ Added deleted_at column to users")
        else:
            print("✓ deleted_at column already exists")
        
        # Update existing users to have role='owner' if they have role='agent'
        cur.execute("""
            UPDATE users 
            SET role = 'owner' 
            WHERE role = 'agent'
        """)
        affected_rows = cur.rowcount
        conn.commit()
        if affected_rows > 0:
            print(f"✓ Updated {affected_rows} existing users from 'agent' to 'owner' role")
        
        # Check if team_invitations table exists
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name='team_invitations'
        """)
        
        if not cur.fetchone():
            # Create team_invitations table
            cur.execute("""
                CREATE TABLE team_invitations (
                    id SERIAL PRIMARY KEY,
                    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                    inviter_id INTEGER NOT NULL REFERENCES users(id),
                    invitee_email VARCHAR(120) NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    token VARCHAR(36) UNIQUE NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                    accepted_at TIMESTAMP,
                    CONSTRAINT uix_workspace_email_pending UNIQUE (workspace_id, invitee_email, status)
                )
            """)
            conn.commit()
            print("✓ Created team_invitations table")
            
            # Create indexes
            cur.execute("""
                CREATE INDEX idx_team_invitations_workspace_id ON team_invitations(workspace_id)
            """)
            cur.execute("""
                CREATE INDEX idx_team_invitations_invitee_email ON team_invitations(invitee_email)
            """)
            cur.execute("""
                CREATE INDEX idx_team_invitations_token ON team_invitations(token)
            """)
            cur.execute("""
                CREATE INDEX idx_team_invitations_status ON team_invitations(status)
            """)
            cur.execute("""
                CREATE INDEX idx_team_invitations_expires_at ON team_invitations(expires_at)
            """)
            conn.commit()
            print("✓ Created indexes on team_invitations table")
        else:
            print("✓ team_invitations table already exists")
        
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
    """Remove team member fields and TeamInvitation table"""
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
        
        # Drop team_invitations table
        cursor.execute("DROP TABLE IF EXISTS team_invitations")
        print("✓ Dropped team_invitations table")
        
        # Note: SQLite doesn't support DROP COLUMN, would need to recreate table
        print("⚠ Note: SQLite doesn't support DROP COLUMN. User table columns remain.")
        
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
        
        # Drop team_invitations table
        cur.execute("DROP TABLE IF EXISTS team_invitations CASCADE")
        print("✓ Dropped team_invitations table")
        
        # Remove columns from users table
        cur.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_active")
        cur.execute("ALTER TABLE users DROP COLUMN IF EXISTS created_at")
        cur.execute("ALTER TABLE users DROP COLUMN IF EXISTS last_login")
        cur.execute("ALTER TABLE users DROP COLUMN IF EXISTS deleted_at")
        print("✓ Removed team member columns from users table")
        
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
