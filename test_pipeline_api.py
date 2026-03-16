"""
Test script for Pipeline API
Creates test company and deals
"""
from app import app
from models import db
from models_crm import Company, Deal, Pipeline, DealStage
from services.pipeline_service import PipelineService

def test_pipeline_api():
    with app.app_context():
        print("=" * 70)
        print("TESTING PIPELINE API")
        print("=" * 70)
        
        # Get first workspace and user
        from models import Workspace, User
        workspace = Workspace.query.first()
        user = User.query.filter_by(workspace_id=workspace.id).first()
        
        if not workspace or not user:
            print("❌ No workspace or user found")
            return
        
        print(f"\n✓ Using workspace: {workspace.company_name}")
        print(f"✓ Using user: {user.name}")
        
        # Create test company
        company = Company(
            workspace_id=workspace.id,
            name="Acme Pharmaceuticals",
            industry="Pharmaceutical",
            size="51-200",
            website="https://acmepharma.example.com",
            phone="+1-555-0123"
        )
        db.session.add(company)
        db.session.flush()
        print(f"\n✓ Created test company: {company.name} (ID: {company.id})")
        
        # Get default pipeline
        pipeline = Pipeline.query.filter_by(
            workspace_id=workspace.id,
            is_default=True
        ).first()
        
        if not pipeline:
            print("❌ No default pipeline found")
            return
        
        print(f"✓ Using pipeline: {pipeline.name} (ID: {pipeline.id})")
        print(f"  Stages: {', '.join([s.name for s in pipeline.stages])}")
        
        # Create test deals
        deals_data = [
            {
                'name': 'Q1 2026 Contract - Acme Pharma',
                'company_id': company.id,
                'pipeline_id': pipeline.id,
                'owner_id': user.id,
                'value': 150000,
                'expected_close_date': '2026-06-30'
            },
            {
                'name': 'API Integration Project',
                'company_id': company.id,
                'pipeline_id': pipeline.id,
                'owner_id': user.id,
                'value': 75000,
                'expected_close_date': '2026-05-15'
            },
            {
                'name': 'Compliance Audit Support',
                'company_id': company.id,
                'pipeline_id': pipeline.id,
                'owner_id': user.id,
                'value': 50000,
                'expected_close_date': '2026-04-30'
            }
        ]
        
        print(f"\n✓ Creating {len(deals_data)} test deals...")
        created_deals = []
        
        for deal_data in deals_data:
            from datetime import datetime
            deal_data['expected_close_date'] = datetime.fromisoformat(deal_data['expected_close_date']).date()
            deal = PipelineService.create_deal(workspace.id, deal_data)
            created_deals.append(deal)
            print(f"  ✓ {deal.name} - ${deal.value:,.0f} (Stage: {deal.stage.name})")
        
        db.session.commit()
        
        # Test moving a deal to next stage
        print(f"\n✓ Testing stage transition...")
        deal_to_move = created_deals[0]
        second_stage = DealStage.query.filter_by(
            pipeline_id=pipeline.id,
            order=2
        ).first()
        
        PipelineService.move_deal_to_stage(
            workspace.id,
            deal_to_move.id,
            second_stage.id,
            user.id
        )
        print(f"  ✓ Moved '{deal_to_move.name}' to '{second_stage.name}'")
        
        # Test forecast calculation
        print(f"\n✓ Calculating sales forecast...")
        forecast = PipelineService.calculate_forecast(workspace.id, pipeline.id)
        print(f"  Total Forecast: ${forecast['total_forecast']:,.2f}")
        print(f"  Total Deals: {forecast['total_deals']}")
        print(f"\n  By Stage:")
        for stage in forecast['by_stage']:
            print(f"    {stage['stage_name']}: {stage['deal_count']} deals, "
                  f"${stage['total_value']:,.0f} total, "
                  f"${stage['weighted_value']:,.2f} weighted")
        
        # Test closing a deal
        print(f"\n✓ Testing deal closure...")
        deal_to_close = created_deals[2]
        PipelineService.close_deal(
            workspace.id,
            deal_to_close.id,
            'won',
            'Customer signed contract after successful demo',
            user.id
        )
        print(f"  ✓ Closed '{deal_to_close.name}' as WON")
        
        print("\n" + "=" * 70)
        print("✓ ALL TESTS PASSED!")
        print("=" * 70)
        print("\nAPI Endpoints available:")
        print("  GET    /api/v1/pipelines")
        print("  GET    /api/v1/pipelines/{id}")
        print("  GET    /api/v1/deals")
        print("  GET    /api/v1/deals/{id}")
        print("  POST   /api/v1/deals")
        print("  PATCH  /api/v1/deals/{id}")
        print("  PATCH  /api/v1/deals/{id}/stage")
        print("  POST   /api/v1/deals/{id}/close")
        print("  DELETE /api/v1/deals/{id}")
        print("  GET    /api/v1/deals/forecast")
        print("\nTest data created:")
        print(f"  Company: {company.name} (ID: {company.id})")
        print(f"  Deals: {len(created_deals)} deals created")
        print()

if __name__ == '__main__':
    test_pipeline_api()
