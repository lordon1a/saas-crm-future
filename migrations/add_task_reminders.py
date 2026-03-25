"""
Migration: Add reminder fields to tasks table
Adds reminder_enabled, reminder_minutes_before, reminder_sent, reminder_method columns
"""
import logging

logger = logging.getLogger(__name__)


def upgrade():
    """Add reminder columns to tasks table"""
    try:
        # Import here to avoid circular imports
        from models import db
        
        with db.engine.connect() as conn:
            # Check if columns already exist (PostgreSQL)
            result = conn.execute(db.text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='tasks' AND column_name='reminder_enabled'
            """))
            
            if result.fetchone():
                logger.info("Reminder columns already exist, skipping migration")
                return
            
            # Add reminder columns
            conn.execute(db.text("""
                ALTER TABLE tasks 
                ADD COLUMN reminder_enabled BOOLEAN DEFAULT FALSE NOT NULL
            """))
            conn.execute(db.text("""
                ALTER TABLE tasks 
                ADD COLUMN reminder_minutes_before INTEGER DEFAULT 60
            """))
            conn.execute(db.text("""
                ALTER TABLE tasks 
                ADD COLUMN reminder_sent BOOLEAN DEFAULT FALSE NOT NULL
            """))
            conn.execute(db.text("""
                ALTER TABLE tasks 
                ADD COLUMN reminder_method VARCHAR(20) DEFAULT 'whatsapp'
            """))
            
            conn.commit()
            logger.info("Successfully added reminder columns to tasks table")
            
    except Exception as e:
        logger.error(f"Error adding reminder columns: {str(e)}")
        raise


def downgrade():
    """Remove reminder columns from tasks table"""
    try:
        from models import db
        
        with db.engine.connect() as conn:
            conn.execute(db.text("""
                ALTER TABLE tasks 
                DROP COLUMN IF EXISTS reminder_enabled,
                DROP COLUMN IF EXISTS reminder_minutes_before,
                DROP COLUMN IF EXISTS reminder_sent,
                DROP COLUMN IF EXISTS reminder_method
            """))
            
            conn.commit()
            logger.info("Successfully removed reminder columns from tasks table")
            
    except Exception as e:
        logger.error(f"Error removing reminder columns: {str(e)}")
        raise


if __name__ == '__main__':
    print("Running task reminders migration...")
    upgrade()
    print("Migration completed successfully!")
