"""
Create default pipeline for workspaces that don't have one
Run this script to ensure all workspaces have at least one pipeline
"""
from app import app
from models import db
from models_crm import Pipeline, DealStage
from sqlalchemy import text

def create_default_pipeline():
    with app.app_context():
        # Get all workspaces
        workspaces = db.session.execute(text("SELECT id FROM workspaces")).fetchall()
        
        for workspace in workspaces:
            workspace_id = workspace[0]
            
            # Check if workspace already has a pipeline
            existing = Pipeline.query.filter_by(workspace_id=workspace_id).first()
            if existing:
                print(f"Workspace {workspace_id} already has a pipeline")
                continue
            
            # Create default pipeline
            pipeline = Pipeline(
                workspace_id=workspace_id,
                name='Sales Pipeline',
                is_default=True
            )
            db.session.add(pipeline)
            db.session.flush()
            
            # Create default stages
            stages = [
                {'name': 'Lead', 'order': 1, 'probability': 10, 'rotting_days': 7},
                {'name': 'Qualified', 'order': 2, 'probability': 25, 'rotting_days': 7},
                {'name': 'Proposal', 'order': 3, 'probability': 50, 'rotting_days': 14},
                {'name': 'Negotiation', 'order': 4, 'probability': 75, 'rotting_days': 14},
                {'name': 'Closed Won', 'order': 5, 'probability': 100, 'rotting_days': None},
                {'name': 'Closed Lost', 'order': 6, 'probability': 0, 'rotting_days': None}
            ]
            
            for stage_data in stages:
                stage = DealStage(
                    pipeline_id=pipeline.id,
                    name=stage_data['name'],
                    order=stage_data['order'],
                    probability=stage_data['probability'],
                    rotting_days=stage_data['rotting_days'],
                    is_active=True
                )
                db.session.add(stage)
            
            db.session.commit()
            print(f"Created default pipeline for workspace {workspace_id}")

if __name__ == '__main__':
    create_default_pipeline()
    print("Done!")
