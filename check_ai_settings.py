from app import app, db
from models_crm import AISettings

with app.app_context():
    all_settings = AISettings.query.all()
    print(f'Total records: {len(all_settings)}')
    for s in all_settings:
        print(f'ID: {s.id}, Workspace: {s.workspace_id}, Provider: {s.provider}, Has Key: {bool(s.api_key_encrypted)}, Active: {s.is_active}')
