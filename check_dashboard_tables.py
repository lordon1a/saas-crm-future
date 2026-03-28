from app import app, db
from sqlalchemy import inspect

with app.app_context():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    print("Checking dashboard tables:")
    print(f"  dashboard_settings: {'✓' if 'dashboard_settings' in tables else '✗'}")
    print(f"  dismissed_actions: {'✓' if 'dismissed_actions' in tables else '✗'}")
    print(f"  widget_engagement: {'✓' if 'widget_engagement' in tables else '✗'}")
    
    if 'dashboard_settings' not in tables:
        print("\n⚠️  Tables missing! Running migration...")
        from migrations.add_action_dashboard_tables import upgrade
        upgrade()
        print("✓ Migration completed")
