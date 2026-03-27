from datetime import datetime
from models import db
from models_crm import OnboardingProgress
import logging

logger = logging.getLogger(__name__)

class OnboardingService:
    @staticmethod
    def complete_step(workspace_id, step_key):
        """
        Marks an onboarding step as complete for a given workspace.
        Available step keys: channel_connected, first_contact_added, first_deal_created, team_member_invited
        """
        try:
            progress = OnboardingProgress.query.filter_by(workspace_id=workspace_id).first()
            if not progress:
                progress = OnboardingProgress(workspace_id=workspace_id)
                db.session.add(progress)
            
            # If step is already complete, no need to do anything
            if getattr(progress, step_key, False):
                return True
            
            # Set the step to True
            setattr(progress, step_key, True)
            
            # Check if all steps are complete
            if progress.is_complete and not progress.completed_at:
                progress.completed_at = datetime.utcnow()
            
            db.session.commit()
            logger.info(f"Onboarding step '{step_key}' marked as complete for workspace {workspace_id}")
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update onboarding progress for workspace {workspace_id}, step '{step_key}': {e}")
            return False

    @staticmethod
    def get_progress(workspace_id):
        """Returns the onboarding progress for a workspace."""
        progress = OnboardingProgress.query.filter_by(workspace_id=workspace_id).first()
        if not progress:
            progress = OnboardingProgress(workspace_id=workspace_id)
            db.session.add(progress)
            db.session.commit()
        return progress
