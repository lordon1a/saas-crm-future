from app import app
from models import db
from models_crm import OnboardingProgress

with app.app_context():
    # Test workspace_id = 1
    progress = OnboardingProgress.query.filter_by(workspace_id=1).first()
    
    if not progress:
        print("Creating new onboarding progress...")
        progress = OnboardingProgress(workspace_id=1)
        db.session.add(progress)
        db.session.commit()
        print("Created!")
    
    print(f"Progress: {progress.completion_percent}%")
    print(f"Channel connected: {progress.channel_connected}")
    print(f"First contact added: {progress.first_contact_added}")
    print(f"First deal created: {progress.first_deal_created}")
    print(f"Team member invited: {progress.team_member_invited}")
    print(f"Is complete: {progress.is_complete}")
