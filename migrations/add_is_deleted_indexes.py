"""
Migration: Add indexes to is_deleted columns for performance optimization
Run with: python -c "from migrations.add_is_deleted_indexes import upgrade; upgrade()"
"""

def upgrade():
    """Add indexes to is_deleted columns in deals, companies, and contacts tables"""
    from app import app, db
    from sqlalchemy import text
    
    with app.app_context():
        try:
            # Add index on deals.is_deleted
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_deals_is_deleted 
                ON deals(is_deleted)
            """))
            print("✅ Added index to deals.is_deleted")
            
            # Add index on companies.is_deleted
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_companies_is_deleted 
                ON companies(is_deleted)
            """))
            print("✅ Added index to companies.is_deleted")
            
            # Add index on contacts.is_deleted
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_contacts_is_deleted 
                ON contacts(is_deleted)
            """))
            print("✅ Added index to contacts.is_deleted")
            
            db.session.commit()
            print("✅ Successfully added is_deleted indexes to all tables")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error adding is_deleted indexes: {str(e)}")
            raise

def downgrade():
    """Remove indexes from is_deleted columns"""
    from app import app, db
    from sqlalchemy import text
    
    with app.app_context():
        try:
            # Drop indexes
            db.session.execute(text("DROP INDEX IF EXISTS idx_deals_is_deleted"))
            db.session.execute(text("DROP INDEX IF EXISTS idx_companies_is_deleted"))
            db.session.execute(text("DROP INDEX IF EXISTS idx_contacts_is_deleted"))
            
            db.session.commit()
            print("✅ Successfully removed is_deleted indexes from all tables")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error removing is_deleted indexes: {str(e)}")
            raise

if __name__ == '__main__':
    upgrade()
