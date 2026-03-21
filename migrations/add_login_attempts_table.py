"""
Migration: Add login_attempts table for brute-force protection
Created: 2026-03-22
"""

def upgrade(conn, cur):
    """Add login_attempts table"""
    
    # Check if login_attempts table exists
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_name='login_attempts'
    """)
    
    if not cur.fetchone():
        print("Creating login_attempts table...")
        cur.execute("""
            CREATE TABLE login_attempts (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                ip_address VARCHAR(50),
                attempted_at TIMESTAMP DEFAULT NOW() NOT NULL,
                success BOOLEAN DEFAULT FALSE NOT NULL,
                user_agent VARCHAR(500)
            )
        """)
        
        # Create indexes for performance
        cur.execute("""
            CREATE INDEX idx_login_attempt_email ON login_attempts(email)
        """)
        cur.execute("""
            CREATE INDEX idx_login_attempt_ip_address ON login_attempts(ip_address)
        """)
        cur.execute("""
            CREATE INDEX idx_login_attempt_attempted_at ON login_attempts(attempted_at)
        """)
        cur.execute("""
            CREATE INDEX idx_login_attempt_success ON login_attempts(success)
        """)
        cur.execute("""
            CREATE INDEX idx_login_attempt_email_time ON login_attempts(email, attempted_at)
        """)
        cur.execute("""
            CREATE INDEX idx_login_attempt_ip_time ON login_attempts(ip_address, attempted_at)
        """)
        cur.execute("""
            CREATE INDEX idx_login_attempt_success_time ON login_attempts(success, attempted_at)
        """)
        
        conn.commit()
        print("✓ Created login_attempts table with indexes")
    else:
        print("✓ login_attempts table already exists")


def downgrade(conn, cur):
    """Remove login_attempts table"""
    cur.execute("DROP TABLE IF EXISTS login_attempts CASCADE")
    conn.commit()
    print("✓ Dropped login_attempts table")
