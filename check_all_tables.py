from app import app, db
from sqlalchemy import inspect

with app.app_context():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    print("All tables in database:")
    for table in sorted(tables):
        if 'widget' in table.lower() or 'engagement' in table.lower() or 'dashboard' in table.lower() or 'dismissed' in table.lower():
            print(f"  ✓ {table}")
    
    print("\nSearching for widget/engagement tables:")
    widget_tables = [t for t in tables if 'widget' in t.lower() or 'engagement' in t.lower()]
    print(f"  Found: {widget_tables}")
