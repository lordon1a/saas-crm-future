"""
Migration: Add is_first_login column to users table
This column tracks if user needs to see setup guide on first login
"""
from models import db

def upgrade():
    """Add is_first_login column to users table"""
    try:
        # Add is_first_login column with default True
        db.session.execute("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS is_first_login BOOLEAN DEFAULT TRUE NOT NULL
        """)
        db.session.commit()
        print("✓ Added is_first_login column to users table")
    except Exception as e:
        db.session.rollback()
        print(f"✗ Error adding is_first_login column: {e}")
        raise

def downgrade():
    """Remove is_first_login column from users table"""
    try:
        db.session.execute("""
            ALTER TABLE users 
            DROP COLUMN IF EXISTS is_first_login
        """)
        db.session.commit()
        print("✓ Removed is_first_login column from users table")
    except Exception as e:
        db.session.rollback()
        print(f"✗ Error removing is_first_login column: {e}")
        raise

if __name__ == '__main__':
    print("Running migration: add_is_first_login")
    upgrade()
    print("Migration completed successfully")
