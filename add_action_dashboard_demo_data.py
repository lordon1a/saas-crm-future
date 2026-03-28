"""
Add demo data for action dashboard testing.
Creates:
- Overdue tasks (urgent priority)
- Tasks due today (high priority)
- High-score stale contacts (high priority)
- Medium-score stale contacts (medium priority)
- Deals with approaching close dates (high priority)
- Deals with stale stages (medium priority)
"""

from app import app, db
from models_crm import Contact, Deal, Task, DealStage, Pipeline
from datetime import datetime, timedelta

def add_demo_action_data():
    with app.app_context():
        # IMPORTANT: Change this to YOUR workspace_id
        # Check your Flask logs to see which workspace_id you're using
        workspace_id = 5  # YOUR workspace_id from the debug logs
        user_id = 5  # YOUR user_id from the debug logs
        
        print(f"🔄 Adding action dashboard demo data for workspace_id={workspace_id}, user_id={user_id}...")
        
        # 1. Create overdue tasks (URGENT - Priority Score: 100)
        print("\n📌 Creating overdue tasks...")
        overdue_task_1 = Task(
            workspace_id=workspace_id,
            title="Ahmet Yılmaz ile görüşme yap",
            description="Teklif sunumu için acil görüşme gerekli",
            status="pending",
            priority="high",
            due_date=datetime.utcnow() - timedelta(days=3),
            created_at=datetime.utcnow() - timedelta(days=5)
        )
        
        overdue_task_2 = Task(
            workspace_id=workspace_id,
            title="Sözleşme imzalat",
            description="ABC Şirketi sözleşmesi bekliyor",
            status="pending",
            priority="urgent",
            due_date=datetime.utcnow() - timedelta(days=1),
            created_at=datetime.utcnow() - timedelta(days=3)
        )
        
        db.session.add_all([overdue_task_1, overdue_task_2])
        print(f"  ✓ 2 overdue task eklendi (3 gün ve 1 gün gecikmiş)")
        
        # 2. Create tasks due today (HIGH - Priority Score: 90)
        print("\n📌 Creating tasks due today...")
        today_task = Task(
            workspace_id=workspace_id,
            title="Fatma Demir'e demo yap",
            description="Ürün demosu bugün saat 14:00'te",
            status="pending",
            priority="high",
            due_date=datetime.utcnow(),
            created_at=datetime.utcnow() - timedelta(days=2)
        )
        
        db.session.add(today_task)
        print(f"  ✓ 1 task bugün için eklendi")
        
        # 3. Create high-score stale contacts (HIGH - Priority Score: 90)
        print("\n👤 Creating high-score stale contacts...")
        stale_contact_1 = Contact(
            workspace_id=workspace_id,
            first_name="Mehmet",
            last_name="Kaya",
            email="mehmet.kaya@example.com",
            phone="+905551234567",
            lead_score=85,  # High score (>= 80)
            last_activity_at=datetime.utcnow() - timedelta(days=10),  # 10 days stale
            lifecycle_stage="qualified_lead",
            is_deleted=False,
            created_at=datetime.utcnow() - timedelta(days=30)
        )
        
        stale_contact_2 = Contact(
            workspace_id=workspace_id,
            first_name="Zeynep",
            last_name="Şahin",
            email="zeynep.sahin@example.com",
            phone="+905559876543",
            lead_score=90,  # High score
            last_activity_at=datetime.utcnow() - timedelta(days=8),  # 8 days stale
            lifecycle_stage="qualified_lead",
            is_deleted=False,
            created_at=datetime.utcnow() - timedelta(days=25)
        )
        
        db.session.add_all([stale_contact_1, stale_contact_2])
        print(f"  ✓ 2 high-score stale contact eklendi (lead_score: 85, 90)")
        
        # 4. Create medium-score stale contacts (MEDIUM - Priority Score: 70)
        print("\n👤 Creating medium-score stale contacts...")
        medium_contact_1 = Contact(
            workspace_id=workspace_id,
            first_name="Can",
            last_name="Özdemir",
            email="can.ozdemir@example.com",
            phone="+905557654321",
            lead_score=65,  # Medium score (>= 60)
            last_activity_at=datetime.utcnow() - timedelta(days=15),  # 15 days stale
            lifecycle_stage="lead",
            is_deleted=False,
            created_at=datetime.utcnow() - timedelta(days=40)
        )
        
        medium_contact_2 = Contact(
            workspace_id=workspace_id,
            first_name="Ayşe",
            last_name="Yıldız",
            email="ayse.yildiz@example.com",
            phone="+905558765432",
            lead_score=70,  # Medium score
            last_activity_at=datetime.utcnow() - timedelta(days=12),  # 12 days stale
            lifecycle_stage="lead",
            is_deleted=False,
            created_at=datetime.utcnow() - timedelta(days=35)
        )
        
        db.session.add_all([medium_contact_1, medium_contact_2])
        print(f"  ✓ 2 medium-score stale contact eklendi (lead_score: 65, 70)")
        
        # 5. Create deals with approaching close dates (HIGH - Priority Score: 95)
        print("\n💼 Creating deals with approaching close dates...")
        
        # Get first pipeline, stage, and company
        from models_crm import Company
        pipeline = Pipeline.query.filter_by(workspace_id=workspace_id).first()
        company = Company.query.filter_by(workspace_id=workspace_id, is_deleted=False).first()
        
        if pipeline and company:
            stage = DealStage.query.filter_by(pipeline_id=pipeline.id).first()
            
            if stage:
                closing_deal_1 = Deal(
                    workspace_id=workspace_id,
                    name="XYZ Şirketi - Yıllık Lisans",
                    company_id=company.id,
                    pipeline_id=pipeline.id,
                    stage_id=stage.id,
                    value=50000,
                    status="open",
                    expected_close_date=datetime.utcnow().date() + timedelta(days=3),  # 3 days until close
                    stage_entered_at=datetime.utcnow() - timedelta(days=5),
                    last_activity_at=datetime.utcnow() - timedelta(days=2),
                    owner_id=user_id,
                    is_deleted=False,
                    created_at=datetime.utcnow() - timedelta(days=20)
                )
                
                closing_deal_2 = Deal(
                    workspace_id=workspace_id,
                    name="DEF A.Ş. - Kurumsal Paket",
                    company_id=company.id,
                    pipeline_id=pipeline.id,
                    stage_id=stage.id,
                    value=75000,
                    status="open",
                    expected_close_date=datetime.utcnow().date() + timedelta(days=5),  # 5 days until close
                    stage_entered_at=datetime.utcnow() - timedelta(days=10),
                    last_activity_at=datetime.utcnow() - timedelta(days=1),
                    owner_id=user_id,
                    is_deleted=False,
                    created_at=datetime.utcnow() - timedelta(days=30)
                )
                
                db.session.add_all([closing_deal_1, closing_deal_2])
                print(f"  ✓ 2 deal eklendi (3 ve 5 gün içinde kapanacak)")
        
        # 6. Create deals with stale stages (MEDIUM - Priority Score: 75)
        print("\n💼 Creating deals with stale stages...")
        if pipeline and stage and company:
            stale_deal = Deal(
                workspace_id=workspace_id,
                name="GHI Ltd. - Danışmanlık",
                company_id=company.id,
                pipeline_id=pipeline.id,
                stage_id=stage.id,
                value=30000,
                status="open",
                expected_close_date=datetime.utcnow().date() + timedelta(days=30),
                stage_entered_at=datetime.utcnow() - timedelta(days=25),  # 25 days in same stage
                last_activity_at=datetime.utcnow() - timedelta(days=15),
                owner_id=user_id,
                is_deleted=False,
                created_at=datetime.utcnow() - timedelta(days=45)
            )
            
            db.session.add(stale_deal)
            print(f"  ✓ 1 stale deal eklendi (25 gündür aynı stage'de)")
        
        # Commit all changes
        db.session.commit()
        
        print("\n✅ Demo data başarıyla eklendi!")
        print("\n📊 Beklenen action item'lar:")
        print("  • 2 Urgent (overdue tasks) - Priority Score: 100")
        print("  • 1 High (task due today) - Priority Score: 90")
        print("  • 2 High (high-score stale contacts) - Priority Score: 90")
        print("  • 2 High (deals closing soon) - Priority Score: 95")
        print("  • 2 Medium (medium-score stale contacts) - Priority Score: 70")
        print("  • 1 Medium (stale deal) - Priority Score: 75")
        print("\n🔔 Topbar'daki bell icon'a tıklayarak action item'ları görebilirsin!")

if __name__ == "__main__":
    add_demo_action_data()
