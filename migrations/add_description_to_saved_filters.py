"""
Migration: Add description column to saved_filters table
Run with: python -c "from migrations.add_description_to_saved_filters import upgrade; upgrade()"
"""

def upgrade():
    """Add description column to saved_filters"""
    from app import app, db
    from sqlalchemy import text, inspect
    
    with app.app_context():
        try:
            # Check if column already exists
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('saved_filters')]
            
            if 'description' in columns:
                print("ℹ️  description column already exists in saved_filters table")
                return
            
            # Add description column (nullable TEXT field)
            # SQLite doesn't support IF NOT EXISTS, so we check first
            db.session.execute(text("""
                ALTER TABLE saved_filters 
                ADD COLUMN description TEXT
            """))
            
            db.session.commit()
            print("✅ Successfully added description column to saved_filters table")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error adding description column: {str(e)}")
            raise

def downgrade():
    """Remove description column from saved_filters"""
    from app import app, db
    from sqlalchemy import text
    
    with app.app_context():
        try:
            # Drop column
            db.session.execute(text("""
                ALTER TABLE saved_filters 
                DROP COLUMN IF EXISTS description
            """))
            
            db.session.commit()
            print("✅ Successfully removed description column from saved_filters table")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error removing description column: {str(e)}")
            raise

if __name__ == '__main__':
    upgrade()
