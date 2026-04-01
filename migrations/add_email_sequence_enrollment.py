"""
Migration: add_email_sequence_enrollment
Email sequence enrollment tracking for automated email sequences.

Creates email_sequence_enrollments table to track contact enrollment
in email sequences with status, progress, and scheduling information.

Run with: python -c "from migrations.add_email_sequence_enrollment import upgrade; upgrade()"
"""


def upgrade():
    """Create email_sequence_enrollments table with indexes"""
    from app import app, db
    from sqlalchemy import text

    with app.app_context():
        try:
            # Create email_sequence_enrollments table
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS email_sequence_enrollments (
                    id SERIAL PRIMARY KEY,
                    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                    sequence_id INTEGER NOT NULL REFERENCES email_sequences(id) ON DELETE CASCADE,
                    contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                    enrolled_by INTEGER NOT NULL REFERENCES users(id),
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    current_step_index INTEGER NOT NULL DEFAULT 0,
                    next_send_at TIMESTAMP,
                    stopped_reason VARCHAR(255),
                    enrolled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uix_enrollment_contact_sequence UNIQUE (sequence_id, contact_id),
                    CONSTRAINT chk_enrollment_status CHECK (status IN ('active', 'paused', 'completed', 'stopped'))
                )
            """))

            # Indexes for query performance
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_enrollments_workspace_id
                ON email_sequence_enrollments(workspace_id)
            """))

            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_enrollments_sequence_id
                ON email_sequence_enrollments(sequence_id)
            """))

            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_enrollments_contact_id
                ON email_sequence_enrollments(contact_id)
            """))

            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_enrollments_status
                ON email_sequence_enrollments(status)
            """))

            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_enrollments_next_send_at
                ON email_sequence_enrollments(next_send_at)
            """))

            # Composite index for common query patterns (active enrollments by sequence)
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_enrollments_sequence_status
                ON email_sequence_enrollments(sequence_id, status)
            """))

            # Composite index for processing queue (active enrollments ready to send)
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_enrollments_active_queue
                ON email_sequence_enrollments(status, next_send_at)
            """))

            db.session.commit()
            print("[OK] Successfully created email_sequence_enrollments table")

        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Error creating email_sequence_enrollments table: {str(e)}")
            raise


def downgrade():
    """Remove email_sequence_enrollments table"""
    from app import app, db
    from sqlalchemy import text

    with app.app_context():
        try:
            db.session.execute(text("DROP TABLE IF EXISTS email_sequence_enrollments CASCADE"))
            db.session.commit()
            print("[OK] Successfully removed email_sequence_enrollments table")
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Error removing email_sequence_enrollments table: {str(e)}")
            raise


if __name__ == '__main__':
    upgrade()
