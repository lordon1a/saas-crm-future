from app import app
from models import db
from sqlalchemy import text

def migrate():
    with app.app_context():
        # Check if columns exist and add them if they don't
        columns_to_add = [
            ('company', 'VARCHAR(100)'),
            ('job_title', 'VARCHAR(100)'),
            ('labels', 'VARCHAR(255)')
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                db.session.execute(text(f"ALTER TABLE customers ADD COLUMN {col_name} {col_type}"))
                print(f"Added column {col_name}")
            except Exception as e:
                print(f"Column {col_name} might already exist or error occurred: {e}")
        
        db.session.commit()
        print("Migration completed.")

if __name__ == "__main__":
    migrate()
