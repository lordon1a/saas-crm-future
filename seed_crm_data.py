"""
Seed CRM Data
Populates database with realistic company, contact, and deal data
"""
from app import app
from models import db, User, Workspace, Customer, Conversation, Message
from models_crm import Company, Contact, Deal, Pipeline, DealStage, Activity
from datetime import datetime, timedelta
import random

def seed_crm_data():
    """Seed realistic CRM data"""
    with app.app_context():
        print("🌱 Seeding CRM data...")
        
        # Get first workspace and user
        workspace = Workspace.query.first()
        user = User.query.first()
        
        if not workspace or not user:
            print("❌ No workspace or user found. Please run the app first.")
            return
        
        print(f"✓ Using workspace: {workspace.company_name}")
        print(f"✓ Using user: {user.email}")
        
        # Get default pipeline
        pipeline = Pipeline.query.filter_by(workspace_id=workspace.id).first()
        if not pipeline:
            print("❌ No pipeline found")
            return
        
        stages = DealStage.query.filter_by(pipeline_id=pipeline.id).order_by(DealStage.order).all()
        print(f"✓ Pipeline: {pipeline.name} with {len(stages)} stages")
        
        # ============================================================================
        # COMPANIES
        # ============================================================================
        
        companies_data = [
            {
                'name': 'TechCorp Solutions',
                'industry': 'Technology',
                'size': '201-500',
                'website': 'https://techcorp.com',
                'phone': '+90 212 555 0101',
                'address': 'Maslak, Istanbul, Turkey'
            },
            {
                'name': 'HealthPlus Pharmaceuticals',
                'industry': 'Healthcare',
                'size': '51-200',
                'website': 'https://healthplus.com',
                'phone': '+90 212 555 0202',
                'address': 'Levent, Istanbul, Turkey'
            },
            {
                'name': 'FinanceHub Bank',
                'industry': 'Finance',
                'size': '500+',
                'website': 'https://financehub.com',
                'phone': '+90 212 555 0303',
                'address': 'Sisli, Istanbul, Turkey'
            },
            {
                'name': 'RetailMax Group',
                'industry': 'Retail',
                'size': '11-50',
                'website': 'https://retailmax.com',
                'phone': '+90 212 555 0404',
                'address': 'Kadikoy, Istanbul, Turkey'
            },
            {
                'name': 'ManufacturePro Industries',
                'industry': 'Manufacturing',
                'size': '201-500',
                'website': 'https://manufacturepro.com',
                'phone': '+90 212 555 0505',
                'address': 'Gebze, Kocaeli, Turkey'
            }
        ]
        
        companies = []
        print("\n📊 Creating companies...")
        for data in companies_data:
            company = Company(
                workspace_id=workspace.id,
                name=data['name'],
                industry=data['industry'],
                size=data['size'],
                website=data['website'],
                phone=data['phone'],
                address=data['address']
            )
            db.session.add(company)
            companies.append(company)
            print(f"  ✓ {data['name']} ({data['industry']})")
        
        db.session.flush()

        # ============================================================================
        # CONTACTS
        # ============================================================================
        
        contacts_data = [
            # TechCorp Solutions
            {'company_idx': 0, 'first_name': 'Mehmet', 'last_name': 'Yilmaz', 'email': 'mehmet.yilmaz@techcorp.com', 'phone': '+90 532 111 0001', 'role': 'Decision Maker', 'job_title': 'CEO'},
            {'company_idx': 0, 'first_name': 'Ayse', 'last_name': 'Demir', 'email': 'ayse.demir@techcorp.com', 'phone': '+90 532 111 0002', 'role': 'Influencer', 'job_title': 'CTO'},
            {'company_idx': 0, 'first_name': 'Can', 'last_name': 'Ozturk', 'email': 'can.ozturk@techcorp.com', 'phone': '+90 532 111 0003', 'role': 'User', 'job_title': 'Senior Developer'},
            
            # HealthPlus Pharmaceuticals
            {'company_idx': 1, 'first_name': 'Zeynep', 'last_name': 'Kaya', 'email': 'zeynep.kaya@healthplus.com', 'phone': '+90 532 222 0001', 'role': 'Decision Maker', 'job_title': 'Managing Director'},
            {'company_idx': 1, 'first_name': 'Ahmet', 'last_name': 'Celik', 'email': 'ahmet.celik@healthplus.com', 'phone': '+90 532 222 0002', 'role': 'Champion', 'job_title': 'Head of IT'},
            {'company_idx': 1, 'first_name': 'Elif', 'last_name': 'Arslan', 'email': 'elif.arslan@healthplus.com', 'phone': '+90 532 222 0003', 'role': 'Influencer', 'job_title': 'Compliance Officer'},
            
            # FinanceHub Bank
            {'company_idx': 2, 'first_name': 'Burak', 'last_name': 'Sahin', 'email': 'burak.sahin@financehub.com', 'phone': '+90 532 333 0001', 'role': 'Decision Maker', 'job_title': 'VP of Technology'},
            {'company_idx': 2, 'first_name': 'Selin', 'last_name': 'Yildiz', 'email': 'selin.yildiz@financehub.com', 'phone': '+90 532 333 0002', 'role': 'Influencer', 'job_title': 'IT Manager'},
            
            # RetailMax Group
            {'company_idx': 3, 'first_name': 'Emre', 'last_name': 'Koc', 'email': 'emre.koc@retailmax.com', 'phone': '+90 532 444 0001', 'role': 'Decision Maker', 'job_title': 'Owner'},
            {'company_idx': 3, 'first_name': 'Deniz', 'last_name': 'Acar', 'email': 'deniz.acar@retailmax.com', 'phone': '+90 532 444 0002', 'role': 'User', 'job_title': 'Operations Manager'},
            
            # ManufacturePro Industries
            {'company_idx': 4, 'first_name': 'Cem', 'last_name': 'Polat', 'email': 'cem.polat@manufacturepro.com', 'phone': '+90 532 555 0001', 'role': 'Decision Maker', 'job_title': 'General Manager'},
            {'company_idx': 4, 'first_name': 'Gizem', 'last_name': 'Erdogan', 'email': 'gizem.erdogan@manufacturepro.com', 'phone': '+90 532 555 0002', 'role': 'Influencer', 'job_title': 'Production Director'},
        ]
        
        contacts = []
        print("\n👥 Creating contacts...")
        for data in contacts_data:
            # Calculate lead score
            score = 0
            if data['email']: score += 20
            if data['phone']: score += 10
            score += 15  # has company
            if data['role'] in ['Decision Maker', 'Influencer', 'Champion']:
                score += 25
            if data['job_title']: score += 10
            
            # Create WhatsApp Customer first (if has phone)
            customer = None
            if data['phone']:
                # Check if customer already exists
                customer = Customer.query.filter_by(
                    workspace_id=workspace.id,
                    phone_number=data['phone']
                ).first()
                
                if not customer:
                    customer = Customer(
                        workspace_id=workspace.id,
                        phone_number=data['phone'],
                        profile_name=f"{data['first_name']} {data['last_name']}",
                        email=data['email'],
                        company=companies[data['company_idx']].name,
                        job_title=data['job_title']
                    )
                    db.session.add(customer)
                    db.session.flush()
            
            contact = Contact(
                workspace_id=workspace.id,
                company_id=companies[data['company_idx']].id,
                first_name=data['first_name'],
                last_name=data['last_name'],
                email=data['email'],
                phone=data['phone'],
                role=data['role'],
                job_title=data['job_title'],
                lead_score=score,
                customer_id=customer.id if customer else None
            )
            db.session.add(contact)
            contacts.append(contact)
            print(f"  ✓ {data['first_name']} {data['last_name']} - {data['job_title']} at {companies[data['company_idx']].name} (Score: {score})")
        
        db.session.flush()

        # ============================================================================
        # WHATSAPP INBOX CONVERSATIONS
        # ============================================================================

        print("\n💬 Creating inbox conversations...")
        conversation_templates = [
            {
                'status': 'open',
                'tag': 'yeni_siparis',
                'customer_message': 'Merhaba, entegrasyon sürecinde ilk adımlar neler olacak?',
                'agent_message': 'Merhaba! İlk adım teknik kickoff toplantısı, ardından erişimleri tanımlıyoruz.',
                'minutes_ago': 30,
                'is_read': False
            },
            {
                'status': 'pending',
                'tag': 'odeme_bekliyor',
                'customer_message': 'Sözleşme sonrası ödeme planını paylaşabilir misiniz?',
                'agent_message': 'Tabii, ödeme planını bugün içinde mail olarak ve buradan paylaşacağım.',
                'minutes_ago': 170,
                'is_read': True
            },
            {
                'status': 'open',
                'tag': 'kargo_sorunu',
                'customer_message': 'Demo ortamına erişimde gecikme yaşıyoruz.',
                'agent_message': 'Kontrol ediyorum, kısa süre içinde erişimi aktif edeceğim.',
                'minutes_ago': 75,
                'is_read': False
            }
        ]

        seeded_conversations = 0
        linked_contacts = [c for c in contacts if c.customer_id]

        for idx, contact in enumerate(linked_contacts[:8]):
            existing_conv = Conversation.query.filter_by(
                workspace_id=workspace.id,
                customer_id=contact.customer_id
            ).first()

            if existing_conv:
                continue

            template = conversation_templates[idx % len(conversation_templates)]
            created_at = datetime.utcnow() - timedelta(minutes=template['minutes_ago'] + (idx * 7))

            conversation = Conversation(
                workspace_id=workspace.id,
                customer_id=contact.customer_id,
                status=template['status'],
                tags=template['tag'],
                assigned_to=user.id,
                notes=f"CRM demo conversation for {contact.full_name}",
                last_message_at=created_at
            )
            db.session.add(conversation)
            db.session.flush()

            customer_msg = Message(
                conversation_id=conversation.id,
                sender_type='customer',
                sender_id=None,
                message_body=template['customer_message'],
                meta_message_id=f'crm-seed-customer-{conversation.id}-{idx}',
                is_read=template['is_read'],
                created_at=created_at
            )

            agent_msg = Message(
                conversation_id=conversation.id,
                sender_type='agent',
                sender_id=user.id,
                message_body=template['agent_message'],
                meta_message_id=f'crm-seed-agent-{conversation.id}-{idx}',
                is_read=True,
                created_at=created_at + timedelta(minutes=3)
            )

            db.session.add(customer_msg)
            db.session.add(agent_msg)
            conversation.last_message_at = agent_msg.created_at
            seeded_conversations += 1

        print(f"  ✓ Created {seeded_conversations} inbox conversations")
        
        # ============================================================================
        # DEALS
        # ============================================================================
        
        deals_data = [
            {
                'company_idx': 0,
                'name': 'Enterprise CRM Implementation',
                'value': 250000,
                'stage_idx': 2,  # Proposal
                'expected_close': datetime.now() + timedelta(days=45),
                'status': 'open'
            },
            {
                'company_idx': 1,
                'name': 'Compliance Management System',
                'value': 180000,
                'stage_idx': 3,  # Negotiation
                'expected_close': datetime.now() + timedelta(days=30),
                'status': 'open'
            },
            {
                'company_idx': 2,
                'name': 'Banking Integration Platform',
                'value': 500000,
                'stage_idx': 1,  # Qualified
                'expected_close': datetime.now() + timedelta(days=90),
                'status': 'open'
            },
            {
                'company_idx': 3,
                'name': 'Retail POS System',
                'value': 75000,
                'stage_idx': 4,  # Closed Won
                'expected_close': datetime.now() - timedelta(days=5),
                'status': 'won'
            },
            {
                'company_idx': 4,
                'name': 'Manufacturing ERP Solution',
                'value': 320000,
                'stage_idx': 0,  # Lead
                'expected_close': datetime.now() + timedelta(days=120),
                'status': 'open'
            },
            {
                'company_idx': 0,
                'name': 'Mobile App Development',
                'value': 120000,
                'stage_idx': 1,  # Qualified
                'expected_close': datetime.now() + timedelta(days=60),
                'status': 'open'
            },
            {
                'company_idx': 1,
                'name': 'Data Analytics Dashboard',
                'value': 95000,
                'stage_idx': 0,  # Lead
                'expected_close': datetime.now() + timedelta(days=75),
                'status': 'open'
            },
        ]
        
        deals = []
        print("\n💰 Creating deals...")
        for data in deals_data:
            deal = Deal(
                workspace_id=workspace.id,
                name=data['name'],
                company_id=companies[data['company_idx']].id,
                pipeline_id=pipeline.id,
                stage_id=stages[data['stage_idx']].id,
                value=data['value'],
                expected_close_date=data['expected_close'].date(),
                owner_id=user.id,
                status=data['status']
            )
            if data['status'] == 'won':
                deal.closed_at = datetime.now() - timedelta(days=5)
                deal.win_loss_reason = 'Customer signed contract after successful demo'
            
            db.session.add(deal)
            deals.append(deal)
            
            stage_name = stages[data['stage_idx']].name
            status_emoji = '✅' if data['status'] == 'won' else '🔄'
            print(f"  {status_emoji} {data['name']} - ${data['value']:,} ({stage_name}) - {companies[data['company_idx']].name}")
        
        db.session.flush()
        
        # ============================================================================
        # ACTIVITIES
        # ============================================================================
        
        print("\n📝 Creating activities...")
        activity_count = 0
        
        # Activities for each deal
        for deal in deals:
            # Deal created activity
            activity = Activity(
                workspace_id=workspace.id,
                activity_type='system',
                deal_id=deal.id,
                company_id=deal.company_id,
                user_id=user.id,
                subject=f'Deal created: {deal.name}',
                body=f'Deal "{deal.name}" was created with value ${deal.value:,}',
                created_at=datetime.now() - timedelta(days=random.randint(10, 60))
            )
            db.session.add(activity)
            activity_count += 1
            
            # Some deals have notes
            if random.random() > 0.5:
                activity = Activity(
                    workspace_id=workspace.id,
                    activity_type='note',
                    deal_id=deal.id,
                    company_id=deal.company_id,
                    user_id=user.id,
                    subject='Meeting notes',
                    body='Had a productive meeting with the decision makers. They are interested in our solution.',
                    created_at=datetime.now() - timedelta(days=random.randint(1, 30))
                )
                db.session.add(activity)
                activity_count += 1
        
        # Activities for contacts
        for contact in contacts[:5]:  # First 5 contacts
            activity = Activity(
                workspace_id=workspace.id,
                activity_type='email',
                contact_id=contact.id,
                company_id=contact.company_id,
                user_id=user.id,
                subject=f'Introduction email sent to {contact.first_name}',
                body=f'Sent introduction email to {contact.first_name} {contact.last_name}',
                created_at=datetime.now() - timedelta(days=random.randint(5, 45))
            )
            db.session.add(activity)
            activity_count += 1
        
        print(f"  ✓ Created {activity_count} activities")
        
        # ============================================================================
        # COMMIT
        # ============================================================================
        
        db.session.commit()
        
        print("\n" + "="*70)
        print("✅ CRM DATA SEEDED SUCCESSFULLY!")
        print("="*70)
        print(f"\n📊 Summary:")
        print(f"  Companies: {len(companies)}")
        print(f"  Contacts: {len(contacts)}")
        print(f"  Deals: {len(deals)}")
        print(f"  Activities: {activity_count}")
        print(f"  Inbox Conversations: {seeded_conversations}")
        print(f"\n💰 Total Pipeline Value: ${sum(d.value for d in deals if d.status == 'open'):,}")
        print(f"💵 Won Deals Value: ${sum(d.value for d in deals if d.status == 'won'):,}")
        print(f"\n🌐 Visit: http://localhost:5000/companies")
        print(f"🌐 Visit: http://localhost:5000/contacts")
        print(f"🌐 Visit: http://localhost:5000/pipeline")
        print()

if __name__ == '__main__':
    seed_crm_data()
