"""
Migration script for CRM Pipeline & Deal Management
Creates tables: pipelines, deal_stages, deals, companies, contacts, custom_fields, custom_field_values
"""
from app import app
from models import db
from models_crm import Pipeline, DealStage, Deal, Company, Contact, CustomField, CustomFieldValue

def migrate():
    with app.app_context():
        print("Creating CRM Pipeline & Deal Management tables...")
        
        # Create tables
        db.create_all()
        
        print("✓ Tables created successfully!")
        print("  - companies")
        print("  - contacts")
        print("  - custom_fields")
        print("  - custom_field_values")
        print("  - pipelines")
        print("  - deal_stages")
        print("  - deals")
        
        # Create default pipeline for existing workspaces
        from models import Workspace
        workspaces = Workspace.query.all()
        
        for workspace in workspaces:
            # Check if workspace already has a pipeline
            existing_pipeline = Pipeline.query.filter_by(workspace_id=workspace.id).first()
            if existing_pipeline:
                print(f"  ⊙ Workspace '{workspace.company_name}' already has a pipeline")
                continue
            
            # Create default sales pipeline
            pipeline = Pipeline(
                workspace_id=workspace.id,
                name='Sales Pipeline',
                is_default=True
            )
            db.session.add(pipeline)
            db.session.flush()  # Get pipeline.id
            
            # Create default stages
            stages = [
                {'name': 'Lead', 'order': 1, 'probability': 0.1},
                {'name': 'Qualified', 'order': 2, 'probability': 0.3},
                {'name': 'Proposal', 'order': 3, 'probability': 0.5},
                {'name': 'Negotiation', 'order': 4, 'probability': 0.7},
                {'name': 'Closed Won', 'order': 5, 'probability': 1.0},
                {'name': 'Closed Lost', 'order': 6, 'probability': 0.0},
            ]
            
            for stage_data in stages:
                stage = DealStage(
                    pipeline_id=pipeline.id,
                    name=stage_data['name'],
                    order=stage_data['order'],
                    probability=stage_data['probability']
                )
                db.session.add(stage)
            
            print(f"  ✓ Created default pipeline for workspace '{workspace.company_name}'")
        
        db.session.commit()
        print("\n✓ Migration completed successfully!")

if __name__ == '__main__':
    migrate()
