"""
View CRM Data
Display database contents in a readable format
"""
from app import app
from models import db
from models_crm import Company, Contact, Deal, Pipeline, DealStage, Activity
from sqlalchemy import func

def view_crm_data():
    """Display CRM data"""
    with app.app_context():
        print("\n" + "="*80)
        print("📊 CRM DATABASE OVERVIEW")
        print("="*80)
        
        # ============================================================================
        # COMPANIES
        # ============================================================================
        
        print("\n🏢 COMPANIES")
        print("-" * 80)
        companies = Company.query.all()
        
        for company in companies:
            contact_count = Contact.query.filter_by(company_id=company.id).count()
            deal_count = Deal.query.filter_by(company_id=company.id).count()
            total_deal_value = db.session.query(func.sum(Deal.value)).filter_by(company_id=company.id).scalar() or 0
            
            print(f"\n📌 {company.name}")
            print(f"   Industry: {company.industry} | Size: {company.size}")
            print(f"   Website: {company.website}")
            print(f"   📞 {company.phone}")
            print(f"   👥 {contact_count} contacts | 💰 {deal_count} deals (${total_deal_value:,.0f})")
            
            # Show contacts
            contacts = Contact.query.filter_by(company_id=company.id).all()
            if contacts:
                print(f"   Contacts:")
                for contact in contacts:
                    role_emoji = "👑" if contact.role == "Decision Maker" else "⭐" if contact.role == "Champion" else "📊" if contact.role == "Influencer" else "👤"
                    print(f"      {role_emoji} {contact.first_name} {contact.last_name} - {contact.job_title}")
                    print(f"         {contact.email} | {contact.phone} | Lead Score: {contact.lead_score}")
            
            # Show deals
            deals = Deal.query.filter_by(company_id=company.id).all()
            if deals:
                print(f"   Deals:")
                for deal in deals:
                    status_emoji = "✅" if deal.status == "won" else "❌" if deal.status == "lost" else "🔄"
                    print(f"      {status_emoji} {deal.name} - ${deal.value:,.0f} ({deal.stage.name})")
        
        # ============================================================================
        # PIPELINE SUMMARY
        # ============================================================================
        
        print("\n\n💰 PIPELINE SUMMARY")
        print("-" * 80)
        
        pipeline = Pipeline.query.first()
        stages = DealStage.query.filter_by(pipeline_id=pipeline.id).order_by(DealStage.order).all()
        
        total_value = 0
        total_weighted = 0
        
        for stage in stages:
            deals = Deal.query.filter_by(stage_id=stage.id, status='open').all()
            stage_value = sum(d.value for d in deals)
            weighted_value = sum(d.get_weighted_value() for d in deals)
            
            total_value += stage_value
            total_weighted += weighted_value
            
            if deals:
                print(f"\n📊 {stage.name} (Probability: {stage.probability*100:.0f}%)")
                print(f"   Deals: {len(deals)} | Total: ${stage_value:,.0f} | Weighted: ${weighted_value:,.0f}")
                for deal in deals:
                    print(f"      • {deal.name} - ${deal.value:,.0f} ({deal.company.name})")
        
        print(f"\n{'='*80}")
        print(f"📈 TOTAL PIPELINE: ${total_value:,.0f}")
        print(f"💵 WEIGHTED FORECAST: ${total_weighted:,.0f}")
        print(f"{'='*80}")
        
        # Won/Lost deals
        won_deals = Deal.query.filter_by(status='won').all()
        lost_deals = Deal.query.filter_by(status='lost').all()
        
        if won_deals:
            won_value = sum(d.value for d in won_deals)
            print(f"\n✅ WON DEALS: {len(won_deals)} deals worth ${won_value:,.0f}")
            for deal in won_deals:
                print(f"   • {deal.name} - ${deal.value:,.0f} ({deal.company.name})")
        
        if lost_deals:
            lost_value = sum(d.value for d in lost_deals)
            print(f"\n❌ LOST DEALS: {len(lost_deals)} deals worth ${lost_value:,.0f}")
        
        # ============================================================================
        # ACTIVITIES
        # ============================================================================
        
        print("\n\n📝 RECENT ACTIVITIES")
        print("-" * 80)
        
        activities = Activity.query.order_by(Activity.created_at.desc()).limit(10).all()
        
        for activity in activities:
            type_emoji = {
                'system': '⚙️',
                'email': '📧',
                'call': '📞',
                'meeting': '🤝',
                'note': '📝',
                'whatsapp': '💬'
            }.get(activity.activity_type, '📌')
            
            entity = ""
            if activity.contact_id:
                contact = Contact.query.get(activity.contact_id)
                entity = f"{contact.first_name} {contact.last_name}"
            elif activity.company_id:
                company = Company.query.get(activity.company_id)
                entity = company.name
            elif activity.deal_id:
                deal = Deal.query.get(activity.deal_id)
                entity = deal.name
            
            print(f"{type_emoji} {activity.subject}")
            print(f"   {entity} | {activity.created_at.strftime('%Y-%m-%d %H:%M')}")
        
        # ============================================================================
        # STATISTICS
        # ============================================================================
        
        print("\n\n📊 STATISTICS")
        print("-" * 80)
        
        total_companies = Company.query.count()
        total_contacts = Contact.query.count()
        total_deals = Deal.query.count()
        total_activities = Activity.query.count()
        
        avg_lead_score = db.session.query(func.avg(Contact.lead_score)).scalar() or 0
        
        print(f"Companies: {total_companies}")
        print(f"Contacts: {total_contacts}")
        print(f"Deals: {total_deals}")
        print(f"Activities: {total_activities}")
        print(f"Average Lead Score: {avg_lead_score:.1f}")
        
        # Industry breakdown
        print(f"\n📊 By Industry:")
        industries = db.session.query(
            Company.industry, 
            func.count(Company.id)
        ).group_by(Company.industry).all()
        
        for industry, count in industries:
            print(f"   {industry}: {count} companies")
        
        # Company size breakdown
        print(f"\n📊 By Company Size:")
        sizes = db.session.query(
            Company.size, 
            func.count(Company.id)
        ).group_by(Company.size).all()
        
        for size, count in sizes:
            print(f"   {size}: {count} companies")
        
        print("\n" + "="*80)
        print()

if __name__ == '__main__':
    view_crm_data()
