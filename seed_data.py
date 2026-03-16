"""
Seed data script for WhatsApp CRM MVP
Creates initial admin user and sample quick replies
"""
import sys
import os
from datetime import datetime, timedelta

# Flask uygulamasını import et
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

# Flask app oluştur
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///whatsapp_crm.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

# Database'i import et
from models import db, User, QuickReply, Workspace, Customer, Conversation, Message, MessageTemplate
from models_crm import Company, Contact, CustomerUser, Pipeline, DealStage, Deal, Milestone, Task, Document, DocumentVersion
db.init_app(app)

from services.auth_manager import AuthManager

def seed_database():
    with app.app_context():
        # Tabloları oluştur
        db.create_all()
        
        print("Starting database seeding...")
        
        # Create workspace
        workspace = Workspace.query.first()
        if not workspace:
            workspace = Workspace(company_name='Demo Company')
            db.session.add(workspace)
            db.session.flush()
            print(f"✓ Created workspace: {workspace.company_name}")
        else:
            print(f"⚠ Workspace already exists: {workspace.company_name}")
        
        # Create admin user
        admin = User.query.filter_by(email='admin@example.com').first()
        if not admin:
            admin = User(
                workspace_id=workspace.id,
                name='Admin User',
                email='admin@example.com',
                password_hash=AuthManager.hash_password('admin123'),
                role='admin'
            )
            db.session.add(admin)
            print(f"✓ Created admin user: {admin.email}")
        else:
            print(f"⚠ Admin user already exists")
        
        # Create agent user
        agent = User.query.filter_by(email='agent@example.com').first()
        if not agent:
            agent = User(
                workspace_id=workspace.id,
                name='Agent User',
                email='agent@example.com',
                password_hash=AuthManager.hash_password('agent123'),
                role='agent'
            )
            db.session.add(agent)
            print(f"✓ Created agent user: {agent.email}")
        else:
            print(f"⚠ Agent user already exists")
        
        # Create sample customers
        sample_customers = [
            {'phone': '+905551234567', 'name': 'Ayşe Yılmaz'},
            {'phone': '+905559876543', 'name': 'Mehmet Demir'},
            {'phone': '+905553334444', 'name': 'Fatma Kaya'},
        ]
        
        for cust_data in sample_customers:
            existing = Customer.query.filter_by(
                workspace_id=workspace.id,
                phone_number=cust_data['phone']
            ).first()
            if not existing:
                customer = Customer(
                    workspace_id=workspace.id,
                    phone_number=cust_data['phone'],
                    profile_name=cust_data['name']
                )
                db.session.add(customer)
                print(f"✓ Created customer: {cust_data['name']}")
            else:
                print(f"⚠ Customer already exists: {cust_data['name']}")
        
        db.session.commit()

        # Create demo inbox conversations/messages
        inbox_demo_rows = [
            {
                'phone': '+905551234567',
                'status': 'open',
                'tag': 'yeni_siparis',
                'customer_message': 'Merhaba, siparişim ne zaman kargoya verilir?',
                'agent_message': 'Merhaba! Siparişinizi kontrol ediyorum, bugün içinde kargoya çıkacak.',
                'minutes_ago': 25,
                'is_read': False
            },
            {
                'phone': '+905559876543',
                'status': 'pending',
                'tag': 'odeme_bekliyor',
                'customer_message': 'Ödeme adımında hata alıyorum, yardımcı olur musunuz?',
                'agent_message': 'Tabii, ödeme linkini yeniliyorum. 2 dakika içinde tekrar deneyebilir misiniz?',
                'minutes_ago': 140,
                'is_read': True
            },
            {
                'phone': '+905553334444',
                'status': 'open',
                'tag': 'kargo_sorunu',
                'customer_message': 'Kargom takipte takıldı görünüyor.',
                'agent_message': 'Anladım, kargo firmasıyla iletişime geçip sizi bilgilendireceğim.',
                'minutes_ago': 55,
                'is_read': False
            }
        ]

        demo_conv_count = 0
        for idx, row in enumerate(inbox_demo_rows):
            customer = Customer.query.filter_by(
                workspace_id=workspace.id,
                phone_number=row['phone']
            ).first()

            if not customer:
                continue

            existing_conv = Conversation.query.filter_by(
                workspace_id=workspace.id,
                customer_id=customer.id
            ).first()

            if existing_conv:
                continue

            created_at = datetime.utcnow() - timedelta(minutes=row['minutes_ago'])

            conversation = Conversation(
                workspace_id=workspace.id,
                customer_id=customer.id,
                status=row['status'],
                tags=row['tag'],
                assigned_to=admin.id,
                notes='Demo inbox conversation',
                last_message_at=created_at
            )
            db.session.add(conversation)
            db.session.flush()

            customer_msg = Message(
                conversation_id=conversation.id,
                sender_type='customer',
                sender_id=None,
                message_body=row['customer_message'],
                meta_message_id=f'seed-customer-{conversation.id}-{idx}',
                is_read=row['is_read'],
                created_at=created_at
            )
            db.session.add(customer_msg)

            agent_msg = Message(
                conversation_id=conversation.id,
                sender_type='agent',
                sender_id=admin.id,
                message_body=row['agent_message'],
                meta_message_id=f'seed-agent-{conversation.id}-{idx}',
                is_read=True,
                created_at=created_at + timedelta(minutes=2)
            )
            db.session.add(agent_msg)

            conversation.last_message_at = agent_msg.created_at
            demo_conv_count += 1

        db.session.commit()
        print(f"✓ Demo inbox conversations ready: {demo_conv_count}")

        # Create ready-to-use customer portal demo data
        demo_company = Company.query.filter_by(
            workspace_id=workspace.id,
            name='Portal Demo Company'
        ).first()
        if not demo_company:
            demo_company = Company(
                workspace_id=workspace.id,
                name='Portal Demo Company',
                industry='Technology',
                size='11-50',
                website='https://portal-demo.local',
                phone='+90 212 555 9988',
                address='Istanbul'
            )
            db.session.add(demo_company)
            db.session.flush()
            print('✓ Created portal demo company')
        else:
            print('⚠ Portal demo company already exists')

        portal_customer = Customer.query.filter_by(
            workspace_id=workspace.id,
            phone_number='+905556667788'
        ).first()
        if not portal_customer:
            portal_customer = Customer(
                workspace_id=workspace.id,
                phone_number='+905556667788',
                profile_name='Portal User',
                email='portal@example.com',
                company=demo_company.name,
                job_title='Project Lead'
            )
            db.session.add(portal_customer)
            db.session.flush()
            print('✓ Created portal demo customer')
        else:
            print('⚠ Portal demo customer already exists')

        portal_contact = Contact.query.filter_by(
            workspace_id=workspace.id,
            email='portal@example.com'
        ).first()
        if not portal_contact:
            portal_contact = Contact(
                workspace_id=workspace.id,
                company_id=demo_company.id,
                first_name='Portal',
                last_name='User',
                email='portal@example.com',
                phone='+905556667788',
                role='Decision Maker',
                job_title='Project Lead',
                lead_score=85,
                customer_id=portal_customer.id
            )
            db.session.add(portal_contact)
            db.session.flush()
            print('✓ Created portal demo contact')
        else:
            print('⚠ Portal demo contact already exists')

        portal_user = CustomerUser.query.filter_by(email='portal@example.com').first()
        if not portal_user:
            portal_user = CustomerUser(
                workspace_id=workspace.id,
                company_id=demo_company.id,
                contact_id=portal_contact.id,
                email='portal@example.com',
                full_name='Portal Demo User',
                password_hash=AuthManager.hash_password('portal123'),
                is_active=True,
            )
            db.session.add(portal_user)
            print('✓ Created portal demo login user')
        else:
            if portal_user.workspace_id != workspace.id:
                portal_user.workspace_id = workspace.id
            if portal_user.company_id != demo_company.id:
                portal_user.company_id = demo_company.id
            if not portal_user.contact_id:
                portal_user.contact_id = portal_contact.id
            portal_user.is_active = True
            portal_user.password_hash = AuthManager.hash_password('portal123')
            print('⚠ Portal demo login user already exists (updated password to portal123)')

        demo_pipeline = Pipeline.query.filter_by(workspace_id=workspace.id, is_default=True).first()
        if not demo_pipeline:
            demo_pipeline = Pipeline.query.filter_by(workspace_id=workspace.id).first()

        if not demo_pipeline:
            demo_pipeline = Pipeline(
                workspace_id=workspace.id,
                name='Sales Pipeline',
                is_default=True,
            )
            db.session.add(demo_pipeline)
            db.session.flush()

            default_stages = [
                ('Lead', 1, 0.1),
                ('Qualified', 2, 0.3),
                ('Proposal', 3, 0.6),
                ('Negotiation', 4, 0.8),
                ('Closed Won', 5, 1.0),
            ]
            for name, order, probability in default_stages:
                db.session.add(DealStage(
                    pipeline_id=demo_pipeline.id,
                    name=name,
                    order=order,
                    probability=probability,
                ))
            db.session.flush()
            print('✓ Created default pipeline and stages for portal demo')

        stages = DealStage.query.filter_by(pipeline_id=demo_pipeline.id).order_by(DealStage.order.asc()).all()
        proposal_stage = next((stage for stage in stages if 'proposal' in (stage.name or '').lower()), None)
        if not proposal_stage and stages:
            proposal_stage = stages[min(2, len(stages) - 1)]

        portal_deal = Deal.query.filter_by(
            workspace_id=workspace.id,
            company_id=demo_company.id,
            name='Portal Implementation Package'
        ).first()
        if not portal_deal and proposal_stage:
            portal_deal = Deal(
                workspace_id=workspace.id,
                name='Portal Implementation Package',
                company_id=demo_company.id,
                pipeline_id=demo_pipeline.id,
                stage_id=proposal_stage.id,
                value=150000,
                expected_close_date=(datetime.utcnow() + timedelta(days=21)).date(),
                owner_id=admin.id,
                status='open',
            )
            db.session.add(portal_deal)
            db.session.flush()
            print('✓ Created portal demo deal')
        elif portal_deal:
            if proposal_stage:
                portal_deal.stage_id = proposal_stage.id
            portal_deal.status = 'open'
            if not portal_deal.owner_id:
                portal_deal.owner_id = admin.id
            print('⚠ Portal demo deal already exists (normalized to open/proposal stage)')

        demo_milestone = Milestone.query.filter_by(
            workspace_id=workspace.id,
            company_id=demo_company.id,
            name='Portal Onboarding'
        ).first()
        if not demo_milestone:
            demo_milestone = Milestone(
                workspace_id=workspace.id,
                company_id=demo_company.id,
                name='Portal Onboarding',
                due_date=datetime.utcnow() + timedelta(days=14),
                status='active'
            )
            db.session.add(demo_milestone)
            db.session.flush()
            print('✓ Created portal demo milestone')
        else:
            print('⚠ Portal demo milestone already exists')

        demo_tasks = [
            {
                'title': 'Kickoff Meeting Completed',
                'description': 'Project kickoff and requirement alignment completed.',
                'status': 'completed',
                'due_days': -1,
            },
            {
                'title': 'Data Import Preparation',
                'description': 'Preparing source data and mapping fields for import.',
                'status': 'in_progress',
                'due_days': 3,
            },
            {
                'title': 'Portal UAT Review',
                'description': 'Customer review and feedback on customer portal screens.',
                'status': 'not_started',
                'due_days': 7,
            },
        ]

        for task_data in demo_tasks:
            existing_task = Task.query.filter_by(
                workspace_id=workspace.id,
                company_id=demo_company.id,
                title=task_data['title']
            ).first()

            if existing_task:
                print(f"⚠ Portal demo task already exists: {task_data['title']}")
                continue

            due_date = datetime.utcnow() + timedelta(days=task_data['due_days'])
            completed_at = datetime.utcnow() if task_data['status'] == 'completed' else None

            task = Task(
                workspace_id=workspace.id,
                company_id=demo_company.id,
                milestone_id=demo_milestone.id,
                assignee_id=admin.id,
                title=task_data['title'],
                description=task_data['description'],
                status=task_data['status'],
                priority='medium',
                due_date=due_date,
                is_customer_facing=True,
                completed_at=completed_at
            )
            db.session.add(task)
            print(f"✓ Created portal demo task: {task_data['title']}")

        portal_conversation = Conversation.query.filter_by(
            workspace_id=workspace.id,
            customer_id=portal_customer.id
        ).first()

        if not portal_conversation:
            base_time = datetime.utcnow() - timedelta(minutes=40)
            portal_conversation = Conversation(
                workspace_id=workspace.id,
                customer_id=portal_customer.id,
                status='open',
                tags='portal_demo',
                assigned_to=admin.id,
                notes='Portal demo conversation',
                last_message_at=base_time
            )
            db.session.add(portal_conversation)
            db.session.flush()

            customer_message = Message(
                conversation_id=portal_conversation.id,
                sender_type='customer',
                sender_id=None,
                message_body='Merhaba, onboarding sürecinde sıradaki adım nedir?',
                meta_message_id=f'portal-seed-customer-{portal_conversation.id}',
                is_read=False,
                created_at=base_time
            )
            agent_message = Message(
                conversation_id=portal_conversation.id,
                sender_type='agent',
                sender_id=admin.id,
                message_body='Merhaba! Sıradaki adım veri içe aktarma kontrolü, bugün başlatıyoruz.',
                meta_message_id=f'portal-seed-agent-{portal_conversation.id}',
                is_read=True,
                created_at=base_time + timedelta(minutes=4)
            )

            db.session.add(customer_message)
            db.session.add(agent_message)
            portal_conversation.last_message_at = agent_message.created_at
            print('✓ Created portal demo conversation and messages')
        else:
            print('⚠ Portal demo conversation already exists')

        uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', f'workspace_{workspace.id}')
        os.makedirs(uploads_dir, exist_ok=True)

        demo_doc_path = os.path.join(uploads_dir, 'portal_onboarding_guide.txt')
        if not os.path.exists(demo_doc_path):
            with open(demo_doc_path, 'w', encoding='utf-8') as doc_file:
                doc_file.write(
                    'Portal Onboarding Guide\\n\\n'
                    '1) Kickoff meeting\\n'
                    '2) Data mapping\\n'
                    '3) UAT and sign-off\\n'
                )

        demo_document = Document.query.filter_by(
            workspace_id=workspace.id,
            company_id=demo_company.id,
            name='Portal Onboarding Guide'
        ).first()

        if not demo_document:
            demo_document = Document(
                workspace_id=workspace.id,
                name='Portal Onboarding Guide',
                category='general',
                company_id=demo_company.id,
                deal_id=None,
                uploaded_by=admin.id,
                is_customer_visible=True,
                current_version_id=None,
            )
            db.session.add(demo_document)
            db.session.flush()
            print('✓ Created portal demo document')
        else:
            demo_document.is_customer_visible = True
            print('⚠ Portal demo document already exists')

        demo_version = DocumentVersion.query.filter_by(
            document_id=demo_document.id,
            version_number=1
        ).first()
        if not demo_version:
            demo_version = DocumentVersion(
                document_id=demo_document.id,
                version_number=1,
                file_path=demo_doc_path,
                file_size=os.path.getsize(demo_doc_path),
                mime_type='text/plain',
                uploaded_by=admin.id,
            )
            db.session.add(demo_version)
            db.session.flush()
            demo_document.current_version_id = demo_version.id
            print('✓ Created portal demo document version')
        else:
            if not os.path.exists(demo_version.file_path):
                demo_version.file_path = demo_doc_path
                demo_version.file_size = os.path.getsize(demo_doc_path)
            if not demo_document.current_version_id:
                demo_document.current_version_id = demo_version.id
            print('⚠ Portal demo document version already exists')

        proposal_doc_path = os.path.join(uploads_dir, 'portal_project_proposal.txt')
        if not os.path.exists(proposal_doc_path):
            with open(proposal_doc_path, 'w', encoding='utf-8') as proposal_file:
                proposal_file.write(
                    'Portal Project Proposal\n\n'
                    '- Scope: Customer portal rollout\n'
                    '- Timeline: 3 weeks\n'
                    '- Budget: 150000 TRY\n\n'
                    'Please approve this proposal from portal documents screen.\n'
                )

        proposal_document = Document.query.filter_by(
            workspace_id=workspace.id,
            company_id=demo_company.id,
            name='Portal Project Proposal'
        ).first()

        if not proposal_document:
            proposal_document = Document(
                workspace_id=workspace.id,
                name='Portal Project Proposal',
                category='proposal',
                company_id=demo_company.id,
                deal_id=portal_deal.id if portal_deal else None,
                uploaded_by=admin.id,
                is_customer_visible=True,
                current_version_id=None,
            )
            db.session.add(proposal_document)
            db.session.flush()
            print('✓ Created portal proposal document (approvable)')
        else:
            proposal_document.category = 'proposal'
            proposal_document.is_customer_visible = True
            if portal_deal and not proposal_document.deal_id:
                proposal_document.deal_id = portal_deal.id
            print('⚠ Portal proposal document already exists')

        proposal_version = DocumentVersion.query.filter_by(
            document_id=proposal_document.id,
            version_number=1
        ).first()
        if not proposal_version:
            proposal_version = DocumentVersion(
                document_id=proposal_document.id,
                version_number=1,
                file_path=proposal_doc_path,
                file_size=os.path.getsize(proposal_doc_path),
                mime_type='text/plain',
                uploaded_by=admin.id,
            )
            db.session.add(proposal_version)
            db.session.flush()
            proposal_document.current_version_id = proposal_version.id
            print('✓ Created proposal document version')
        else:
            if not os.path.exists(proposal_version.file_path):
                proposal_version.file_path = proposal_doc_path
                proposal_version.file_size = os.path.getsize(proposal_doc_path)
            if not proposal_document.current_version_id:
                proposal_document.current_version_id = proposal_version.id
            print('⚠ Proposal document version already exists')

        db.session.commit()
        print('✓ Portal demo data ready')
        
        # Create message templates
        templates_data = [
            {
                'name': 'Sipariş Onayı',
                'body': 'Merhaba! Siparişiniz başarıyla alındı. Sipariş numaranız: #{{order_id}}. En kısa sürede kargoya verilecektir.',
                'category': 'utility',
                'language': 'tr'
            },
            {
                'name': 'Kargo Bildirimi',
                'body': 'Siparişiniz kargoya verildi! Takip numaranız: {{tracking_code}}. Kargo firması: {{cargo_company}}',
                'category': 'utility',
                'language': 'tr'
            },
            {
                'name': 'Ödeme Hatırlatma',
                'body': 'Merhaba, siparişiniz için ödeme bekliyoruz. Toplam tutar: {{amount}} TL. IBAN: TR00 0000 0000 0000 0000 0000 00',
                'category': 'marketing',
                'language': 'tr'
            },
            {
                'name': 'Kampanya Duyurusu',
                'body': '🎉 Özel kampanya! {{campaign_name}} - %{{discount}} indirim fırsatını kaçırmayın! Detaylar: {{link}}',
                'category': 'marketing',
                'language': 'tr'
            },
            {
                'name': 'Destek Talebi Alındı',
                'body': 'Destek talebiniz alındı. Ticket numaranız: #{{ticket_id}}. En kısa sürede size dönüş yapacağız.',
                'category': 'utility',
                'language': 'tr'
            }
        ]
        
        for tmpl_data in templates_data:
            existing = MessageTemplate.query.filter_by(
                workspace_id=workspace.id,
                name=tmpl_data['name']
            ).first()
            if not existing:
                template = MessageTemplate(
                    workspace_id=workspace.id,
                    name=tmpl_data['name'],
                    body=tmpl_data['body'],
                    category=tmpl_data['category'],
                    language=tmpl_data['language'],
                    created_by=admin.id
                )
                db.session.add(template)
                print(f"✓ Created message template: {tmpl_data['name']}")
            else:
                print(f"⚠ Message template already exists: {tmpl_data['name']}")
        
        db.session.commit()
        
        # Create quick replies
        quick_replies_data = [
            {
                'title': 'Hoş Geldiniz',
                'body': 'Merhaba! Size nasıl yardımcı olabilirim?'
            },
            {
                'title': 'IBAN Bilgisi',
                'body': 'IBAN Numaramız: TR00 0000 0000 0000 0000 0000 00'
            },
            {
                'title': 'Çalışma Saatleri',
                'body': 'Çalışma saatlerimiz: Hafta içi 09:00-18:00'
            },
            {
                'title': 'Kargo Takibi',
                'body': 'Kargo takip numaranızı paylaşır mısınız? Hemen kontrol edeyim.'
            },
            {
                'title': 'Teşekkür',
                'body': 'Bizi tercih ettiğiniz için teşekkür ederiz! İyi günler dileriz.'
            }
        ]
        
        for qr_data in quick_replies_data:
            existing = QuickReply.query.filter_by(
                workspace_id=workspace.id,
                title=qr_data['title']
            ).first()
            if not existing:
                qr = QuickReply(
                    workspace_id=workspace.id,
                    title=qr_data['title'],
                    body=qr_data['body']
                )
                db.session.add(qr)
                print(f"✓ Created quick reply: {qr_data['title']}")
            else:
                print(f"⚠ Quick reply already exists: {qr_data['title']}")
        
        db.session.commit()
        print("\n✅ Database seeding completed!")
        print("\nDefault credentials:")
        print("  Admin: admin@example.com / admin123")
        print("  Agent: agent@example.com / agent123")
        print("  Portal: portal@example.com / portal123")

if __name__ == '__main__':
    seed_database()
