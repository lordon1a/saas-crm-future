"""
Migration: Add is_starred column to contacts table
Run with: python -c "from migrations.add_is_starred_to_contacts import upgrade; upgrade()"
"""

def upgrade():
    """Add is_starred column to contacts"""
    from app import app, db
    from sqlalchemy import text
    
    with app.app_context():
        try:
            # Add is_starred column with default False
            db.session.execute(text("""
                ALTER TABLE contacts 
                ADD COLUMN IF NOT EXISTS is_starred BOOLEAN DEFAULT FALSE NOT NULL
            """))
            
            # Create index on is_starred for faster queries
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_contacts_is_starred 
                ON contacts(is_starred)
            """))
            
            db.session.commit()
            print("✅ Successfully added is_starred column to contacts table")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error adding is_starred column: {str(e)}")
            raise

def downgrade():
    """Remove is_starred column from contacts"""
    from app import app, db
    from sqlalchemy import text
    
    with app.app_context():
        try:
            # Drop index first
            db.session.execute(text("""
                DROP INDEX IF EXISTS idx_contacts_is_starred
            """))
            
            # Drop column
            db.session.execute(text("""
                ALTER TABLE contacts 
                DROP COLUMN IF EXISTS is_starred
            """))
            
            db.session.commit()
            print("✅ Successfully removed is_starred column from contacts table")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error removing is_starred column: {str(e)}")
            raise

if __name__ == '__main__':
    upgrade()
