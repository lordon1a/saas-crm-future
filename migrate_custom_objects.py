"""
Migration script: add singular_label, plural_label, icon_color to custom_objects table.
Run once: python migrate_custom_objects.py
"""
from app import app, db
from sqlalchemy import text, inspect

with app.app_context():
    inspector = inspect(db.engine)
    
    # Check if table exists at all
    all_tables = inspector.get_table_names()
    print("Tables found:", [t for t in all_tables if 'custom' in t or 'entity' in t])
    
    if 'custom_objects' not in all_tables:
        print("custom_objects table missing - running db.create_all()")
        db.create_all()
        print("db.create_all() done")
    else:
        existing_cols = [c['name'] for c in inspector.get_columns('custom_objects')]
        print("Existing columns:", existing_cols)
        
        new_cols = [
            ('singular_label', 'VARCHAR(100)'),
            ('plural_label',   'VARCHAR(100)'),
            ('icon_color',     'VARCHAR(20)'),
        ]
        
        with db.engine.connect() as conn:
            for col_name, col_type in new_cols:
                if col_name not in existing_cols:
                    sql = f'ALTER TABLE custom_objects ADD COLUMN {col_name} {col_type}'
                    conn.execute(text(sql))
                    print(f'  + Added column: {col_name}')
                else:
                    print(f'  = Already exists: {col_name}')
            conn.commit()
    
    # Ensure other tables also exist
    db.create_all()
    
    # Final test
    from models_crm import CustomObject
    count = CustomObject.query.count()
    print(f'\nTest query OK — custom_objects rows: {count}')
    print('Migration complete!')
