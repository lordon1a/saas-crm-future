"""
Migration: Add email column to companies table
"""

def upgrade(db):
    """Add email column to companies table."""
    from flask import current_app
    
    # Check if we're using PostgreSQL or SQLite
    database_uri = str(current_app.config.get('SQLALCHEMY_DATABASE_URI', ''))
    
    with db.engine.connect() as conn:
        if 'sqlite' in database_uri:
            # SQLite doesn't support IF NOT EXISTS in ALTER TABLE
            # Check if column exists first
            result = conn.execute(db.text("PRAGMA table_info(companies)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'email' not in columns:
                conn.execute(db.text("""
                    ALTER TABLE companies 
                    ADD COLUMN email VARCHAR(255)
                """))
                conn.commit()
                print("✅ Added email column to companies table (SQLite)")
            else:
                print("✅ Email column already exists in companies table")
        else:
            # PostgreSQL
            conn.execute(db.text("""
                ALTER TABLE companies 
                ADD COLUMN IF NOT EXISTS email VARCHAR(255)
            """))
            conn.commit()
            print("✅ Added email column to companies table (PostgreSQL)")

def downgrade(db):
    """Remove email column from companies table."""
    from flask import current_app
    
    database_uri = str(current_app.config.get('SQLALCHEMY_DATABASE_URI', ''))
    
    with db.engine.connect() as conn:
        if 'sqlite' in database_uri:
            # SQLite doesn't support DROP COLUMN easily
            print("⚠️  SQLite doesn't support DROP COLUMN - manual migration needed")
        else:
            conn.execute(db.text("""
                ALTER TABLE companies 
                DROP COLUMN IF EXISTS email
            """))
            conn.commit()
            print("✅ Removed email column from companies table")
