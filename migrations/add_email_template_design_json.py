"""
Add design_json and editor_type columns to email_templates table
Migration: add_email_template_design_json
"""

from migration_base import *


def upgrade():
    """Add design_json and editor_type columns to email_templates"""
    
    conn = engine.connect()
    trans = conn.begin()
    
    try:
        # Add design_json column (Unlayer exportDesign() output)
        conn.execute(text("""
            ALTER TABLE email_templates 
            ADD COLUMN design_json TEXT
        """))
        
        # Add editor_type column ('html' or 'visual')
        conn.execute(text("""
            ALTER TABLE email_templates 
            ADD COLUMN editor_type VARCHAR(20) DEFAULT 'html'
        """))
        
        trans.commit()
        print("Migration add_email_template_design_json completed successfully")
        
    except Exception as e:
        trans.rollback()
        # Check if column already exists
        if 'duplicate column name' in str(e).lower():
            print("Columns already exist, migration skipped")
        else:
            print(f"Migration failed: {e}")
            raise
    finally:
        conn.close()


def downgrade():
    """Remove design_json and editor_type columns from email_templates"""
    conn = engine.connect()
    trans = conn.begin()
    
    try:
        # SQLite doesn't support DROP COLUMN directly in older versions
        # For SQLite, we would need to recreate the table
        # But for PostgreSQL/Render deployment, this should work
        conn.execute(text("ALTER TABLE email_templates DROP COLUMN IF EXISTS design_json"))
        conn.execute(text("ALTER TABLE email_templates DROP COLUMN IF EXISTS editor_type"))
        
        trans.commit()
        print("Migration add_email_template_design_json rolled back successfully")
    except Exception as e:
        trans.rollback()
        print(f"Rollback failed: {e}")
        raise
    finally:
        conn.close()
