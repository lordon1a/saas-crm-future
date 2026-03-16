"""
Migration script for CRM Phase 1 - All Core Models
Creates all Phase 1 tables:
- Companies, Contacts, Custom Fields
- Pipelines, Deal Stages, Deals
- Tasks, Milestones, Task Dependencies, Task Comments, Task Attachments
- Activities
- Documents, Document Versions, Document Templates
"""
from app import app
from models import db
from models_crm import (
    Company, Contact, CustomField, CustomFieldValue,
    Pipeline, DealStage, Deal,
    Task, TaskDependency, Milestone, TaskComment, TaskAttachment,
    Activity,
    Document, DocumentVersion, DocumentTemplate
)

def migrate():
    with app.app_context():
        print("=" * 70)
        print("CRM PHASE 1 MIGRATION - Core Data Models")
        print("=" * 70)
        
        # Create all tables
        db.create_all()
        
        print("\n✓ All Phase 1 tables created successfully!")
        print("\nCreated tables:")
        print("  📊 Company & Contact Management:")
        print("     - companies")
        print("     - contacts")
        print("     - custom_fields")
        print("     - custom_field_values")
        print("\n  💼 Pipeline & Deal Management:")
        print("     - pipelines")
        print("     - deal_stages")
        print("     - deals")
        print("\n  ✅ Task & Project Management:")
        print("     - tasks")
        print("     - task_dependencies")
        print("     - milestones")
        print("     - task_comments")
        print("     - task_attachments")
        print("\n  📝 Activity Timeline:")
        print("     - activities")
        print("\n  📄 Document Management:")
        print("     - documents")
        print("     - document_versions")
        print("     - document_templates")
        
        # Create default pipelines for existing workspaces
        from models import Workspace
        workspaces = Workspace.query.all()
        
        print(f"\n\nInitializing default pipelines for {len(workspaces)} workspace(s)...")
        
        for workspace in workspaces:
            # Check if workspace already has a pipeline
            existing_pipeline = Pipeline.query.filter_by(workspace_id=workspace.id).first()
            if existing_pipeline:
                print(f"  ⊙ '{workspace.company_name}' already has a pipeline")
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
            
            print(f"  ✓ Created default pipeline for '{workspace.company_name}'")
        
        db.session.commit()
        
        print("\n" + "=" * 70)
        print("✓ PHASE 1 MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print("\nNext steps:")
        print("  1. Verify tables in database")
        print("  2. Test creating companies, contacts, and deals")
        print("  3. Proceed to Phase 2 implementation")
        print()

if __name__ == '__main__':
    migrate()
