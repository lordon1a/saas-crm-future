from app import app, db
from models_crm import AISettings

with app.app_context():
    # Deactivate Gemini and Anthropic
    AISettings.query.filter_by(workspace_id=1, provider='gemini').update({'is_active': False})
    AISettings.query.filter_by(workspace_id=1, provider='anthropic').update({'is_active': False})
    db.session.commit()
    
    print("Gemini and Anthropic deactivated")
    
    # Show current settings
    all_settings = AISettings.query.filter_by(workspace_id=1).all()
    for s in all_settings:
        print(f'Provider: {s.provider}, Has Key: {bool(s.api_key_encrypted)}, Active: {s.is_active}')
