"""
Comprehensive Demo Data Seeder for Admin Account
Creates realistic sample data for all CRM features
"""
from app import app, db
from models import User, Workspace, Customer, Conversation, Message, QuickReply, MessageTemplate, Note
from models_crm import (
    Company, Contact, Pipeline, DealStage, Deal, Task, Milestone, 
    Activity, CustomField, CustomFieldValue
)
from models_automation import AutomationRule, AutoReply
from datetime import datetime, timedelta
import random
import logging

logger = logging.getLogger(__name__)

def seed_demo_data():
    with app.app_context():
        logger.info("Starting demo data seed...")
        
        # Get admin user and workspace
        admin_user = User.query.filter_by(email='admin@example.com').first()
        if not admin_user:
            logger.error("Admin user not found!")
            return
        
        workspace_id = admin_user.workspace_id
        user_id = admin_user.id
        
        logger.info(f"Found admin user: {admin_user.email}, workspace: {workspace_id}")
        
        # Check if demo data already exists
        existing_companies = Company.query.filter_by(workspace_id=workspace_id).count()
        if existing_companies > 0:
            logger.info(f"Demo data already exists ({existing_companies} companies found), skipping...")
            return
        
        logger.info("Creating demo data...")
        
        # 1. COMPANIES
        logger.info("Creating companies...")
        companies_data = [
            {"name": "Acme Corporation", "industry": "Technology", "size": "201-500", "website": "https://acme.com", "phone": "+90 212 555 0101"},
            {"name": "TechStart Inc", "industry": "Software", "size": "11-50", "website": "https://techstart.io", "phone": "+90 212 555 0102"},
            {"name": "Global Retail Ltd", "industry": "Retail", "size": "500+", "website": "https://globalretail.com", "phone": "+90 212 555 0103"},
            {"name": "FinanceHub", "industry": "Finance", "size": "51-200", "website": "https://financehub.com", "phone": "+90 212 555 0104"},
            {"name": "HealthCare Plus", "industry": "Healthcare", "size": "201-500", "website": "https://healthcareplus.com", "phone": "+90 212 555 0105"},
        ]
        
        companies = []
        for comp_data in companies_data:
            company = Company(workspace_id=workspace_id, **comp_data)
            db.session.add(company)
            companies.append(company)
        db.session.flush()
        logger.info(f"Created {len(companies)} companies")
        
        # 2. CONTACTS
        logger.info("Creating contacts...")
        contacts_data = [
            {"first_name": "Ahmet", "last_name": "Yılmaz", "email": "ahmet@acme.com", "phone": "+90 532 111 2233", "whatsapp_phone": "+905321112233", "job_title": "CEO", "role": "Decision Maker", "company_id": companies[0].id},
            {"first_name": "Ayşe", "last_name": "Demir", "email": "ayse@acme.com", "phone": "+90 532 222 3344", "whatsapp_phone": "+905322223344", "job_title": "CTO", "role": "Champion", "company_id": companies[0].id},
            {"first_name": "Mehmet", "last_name": "Kaya", "email": "mehmet@techstart.io", "phone": "+90 532 333 4455", "whatsapp_phone": "+905323334455", "job_title": "Founder", "role": "Decision Maker", "company_id": companies[1].id},
            {"first_name": "Fatma", "last_name": "Şahin", "email": "fatma@globalretail.com", "phone": "+90 532 444 5566", "whatsapp_phone": "+905324445566", "job_title": "Procurement Manager", "role": "Influencer", "company_id": companies[2].id},
            {"first_name": "Ali", "last_name": "Öztürk", "email": "ali@financehub.com", "phone": "+90 532 555 6677", "whatsapp_phone": "+905325556677", "job_title": "CFO", "role": "Decision Maker", "company_id": companies[3].id},
            {"first_name": "Zeynep", "last_name": "Arslan", "email": "zeynep@healthcareplus.com", "phone": "+90 532 666 7788", "whatsapp_phone": "+905326667788", "job_title": "Operations Director", "role": "Champion", "company_id": companies[4].id},
        ]
        
        contacts = []
        for contact_data in contacts_data:
            contact = Contact(workspace_id=workspace_id, **contact_data)
            db.session.add(contact)
            contacts.append(contact)
        db.session.flush()
        logger.info(f"Created {len(contacts)} contacts")
        
        # 3. PIPELINE & STAGES
        logger.info("Creating sales pipeline...")
        pipeline = Pipeline(
            workspace_id=workspace_id,
            name="Satış Pipeline",
            is_default=True
        )
        db.session.add(pipeline)
        db.session.flush()
        
        stages_data = [
            {"name": "Yeni Fırsat", "order": 1, "probability": 0.1},
            {"name": "İletişim Kuruldu", "order": 2, "probability": 0.25},
            {"name": "Teklif Hazırlandı", "order": 3, "probability": 0.5},
            {"name": "Müzakere", "order": 4, "probability": 0.75},
            {"name": "Kapalı - Kazanıldı", "order": 5, "probability": 1.0},
            {"name": "Kapalı - Kaybedildi", "order": 6, "probability": 0.0},
        ]
        
        stages = []
        for stage_data in stages_data:
            stage = DealStage(pipeline_id=pipeline.id, **stage_data)
            db.session.add(stage)
            stages.append(stage)
        db.session.flush()
        logger.info(f"Created pipeline with {len(stages)} stages")
        
        # 4. DEALS
        logger.info("Creating deals...")
        deals_data = [
            {"name": "CRM Yazılım Lisansı", "company_id": companies[0].id, "stage_id": stages[3].id, "value": 150000, "status": "open", "expected_close_date": datetime.now() + timedelta(days=15)},
            {"name": "E-ticaret Entegrasyonu", "company_id": companies[1].id, "stage_id": stages[2].id, "value": 75000, "status": "open", "expected_close_date": datetime.now() + timedelta(days=30)},
            {"name": "Mobil Uygulama Geliştirme", "company_id": companies[2].id, "stage_id": stages[1].id, "value": 200000, "status": "open", "expected_close_date": datetime.now() + timedelta(days=45)},
            {"name": "Danışmanlık Hizmeti", "company_id": companies[3].id, "stage_id": stages[4].id, "value": 50000, "status": "won", "closed_at": datetime.now() - timedelta(days=5)},
            {"name": "Bulut Altyapı Kurulumu", "company_id": companies[4].id, "stage_id": stages[0].id, "value": 120000, "status": "open", "expected_close_date": datetime.now() + timedelta(days=60)},
        ]
        
        deals = []
        for deal_data in deals_data:
            deal = Deal(
                workspace_id=workspace_id,
                pipeline_id=pipeline.id,
                owner_id=user_id,
                **deal_data
            )
            db.session.add(deal)
            deals.append(deal)
        db.session.flush()
        logger.info(f"Created {len(deals)} deals")
        
        # 5. TASKS
        logger.info("Creating tasks...")
        milestone = Milestone(
            workspace_id=workspace_id,
            name="Q1 2026 Hedefleri",
            company_id=companies[0].id,
            due_date=datetime.now() + timedelta(days=90)
        )
        db.session.add(milestone)
        db.session.flush()
        
        tasks_data = [
            {"title": "Teklif sunumu hazırla", "description": "Acme için detaylı teklif sunumu", "status": "in_progress", "priority": "high", "due_date": datetime.now() + timedelta(days=3), "company_id": companies[0].id, "deal_id": deals[0].id},
            {"title": "Demo toplantısı planla", "description": "TechStart ekibi ile ürün demosu", "status": "not_started", "priority": "medium", "due_date": datetime.now() + timedelta(days=7), "company_id": companies[1].id, "deal_id": deals[1].id},
            {"title": "Sözleşme gönder", "description": "FinanceHub için sözleşme hazırla", "status": "completed", "priority": "high", "due_date": datetime.now() - timedelta(days=2), "completed_at": datetime.now() - timedelta(days=1), "company_id": companies[3].id, "deal_id": deals[3].id},
            {"title": "Referans müşteri görüşmesi", "description": "Global Retail için referans paylaş", "status": "not_started", "priority": "low", "due_date": datetime.now() + timedelta(days=14), "company_id": companies[2].id},
            {"title": "Teknik gereksinim analizi", "description": "HealthCare Plus için teknik analiz", "status": "in_progress", "priority": "medium", "due_date": datetime.now() + timedelta(days=10), "company_id": companies[4].id, "deal_id": deals[4].id, "milestone_id": milestone.id},
        ]
        
        tasks = []
        for task_data in tasks_data:
            task = Task(
                workspace_id=workspace_id,
                assignee_id=user_id,
                **task_data
            )
            db.session.add(task)
            tasks.append(task)
        db.session.flush()
        logger.info(f"Created {len(tasks)} tasks")

        
        # 6. WHATSAPP CUSTOMERS & CONVERSATIONS
        logger.info("Creating WhatsApp conversations...")
        customers_data = [
            {"phone_number": "+905321112233", "profile_name": "Ahmet Yılmaz", "email": "ahmet@acme.com", "company": "Acme Corporation", "labels": "vip,enterprise"},
            {"phone_number": "+905323334455", "profile_name": "Mehmet Kaya", "email": "mehmet@techstart.io", "company": "TechStart Inc", "labels": "startup,tech"},
            {"phone_number": "+905324445566", "profile_name": "Fatma Şahin", "email": "fatma@globalretail.com", "company": "Global Retail Ltd", "labels": "retail"},
        ]
        
        customers = []
        for cust_data in customers_data:
            customer = Customer(workspace_id=workspace_id, **cust_data)
            db.session.add(customer)
            customers.append(customer)
        db.session.flush()
        
        # Link contacts to customers
        contacts[0].customer_id = customers[0].id
        contacts[2].customer_id = customers[1].id
        contacts[3].customer_id = customers[2].id
        
        # Create conversations
        conversations_data = [
            {"customer_id": customers[0].id, "status": "open", "tags": "sales,urgent", "assigned_to": user_id, "last_message_at": datetime.now() - timedelta(hours=2)},
            {"customer_id": customers[1].id, "status": "open", "tags": "support", "assigned_to": user_id, "last_message_at": datetime.now() - timedelta(hours=5)},
            {"customer_id": customers[2].id, "status": "closed", "tags": "sales", "assigned_to": user_id, "last_message_at": datetime.now() - timedelta(days=2)},
        ]
        
        conversations = []
        for conv_data in conversations_data:
            conversation = Conversation(workspace_id=workspace_id, **conv_data)
            db.session.add(conversation)
            conversations.append(conversation)
        db.session.flush()
        
        # Create messages
        messages_data = [
            # Conversation 1
            {"conversation_id": conversations[0].id, "sender_type": "customer", "message_body": "Merhaba, CRM yazılımınız hakkında bilgi alabilir miyim?", "created_at": datetime.now() - timedelta(hours=3)},
            {"conversation_id": conversations[0].id, "sender_type": "agent", "sender_id": user_id, "message_body": "Merhaba! Tabii ki. CRM sistemimiz satış, müşteri ilişkileri ve otomasyon özellikleri sunuyor. Size nasıl yardımcı olabilirim?", "created_at": datetime.now() - timedelta(hours=2, minutes=55)},
            {"conversation_id": conversations[0].id, "sender_type": "customer", "message_body": "Fiyatlandırma hakkında detaylı bilgi istiyorum.", "created_at": datetime.now() - timedelta(hours=2)},
            # Conversation 2
            {"conversation_id": conversations[1].id, "sender_type": "customer", "message_body": "Entegrasyon konusunda sorun yaşıyoruz.", "created_at": datetime.now() - timedelta(hours=5)},
            {"conversation_id": conversations[1].id, "sender_type": "agent", "sender_id": user_id, "message_body": "Anlıyorum. Hangi entegrasyon ile ilgili sorun yaşıyorsunuz?", "created_at": datetime.now() - timedelta(hours=4, minutes=50)},
            # Conversation 3
            {"conversation_id": conversations[2].id, "sender_type": "customer", "message_body": "Teşekkürler, sorunumuz çözüldü.", "created_at": datetime.now() - timedelta(days=2)},
            {"conversation_id": conversations[2].id, "sender_type": "agent", "sender_id": user_id, "message_body": "Rica ederim! Başka bir konuda yardımcı olabilirsem lütfen çekinmeyin.", "created_at": datetime.now() - timedelta(days=2, hours=1)},
        ]
        
        for msg_data in messages_data:
            message = Message(**msg_data)
            db.session.add(message)
        
        # Add notes to conversations
        note1 = Note(
            conversation_id=conversations[0].id,
            user_id=user_id,
            content="Müşteri enterprise paket için teklif bekliyor. Yarın demo toplantısı planlandı."
        )
        db.session.add(note1)
        
        logger.info(f"Created {len(customers)} customers, {len(conversations)} conversations")
        
        # 7. QUICK REPLIES
        logger.info("Creating quick replies...")
        quick_replies_data = [
            {"title": "Hoş Geldiniz", "body": "Merhaba! Size nasıl yardımcı olabilirim?", "category": "greeting"},
            {"title": "Fiyat Bilgisi", "body": "Fiyatlandırma bilgilerimizi size e-posta ile göndereceğim. E-posta adresinizi alabilir miyim?", "category": "sales"},
            {"title": "Demo Talebi", "body": "Demo için uygun olduğunuz tarih ve saati belirtir misiniz?", "category": "sales"},
            {"title": "Destek Talebi", "body": "Sorununuzu detaylı olarak anlatabilir misiniz? En kısa sürede size dönüş yapacağım.", "category": "support"},
            {"title": "Teşekkür", "body": "Bize ulaştığınız için teşekkür ederiz. İyi günler dileriz!", "category": "closing"},
        ]
        
        for qr_data in quick_replies_data:
            qr = QuickReply(workspace_id=workspace_id, **qr_data)
            db.session.add(qr)
        logger.info(f"Created {len(quick_replies_data)} quick replies")
        
        # 8. MESSAGE TEMPLATES
        logger.info("Creating message templates...")
        templates_data = [
            {"name": "Hoş Geldin Mesajı", "body": "Merhaba {{name}}, {{company}} ailesine hoş geldiniz! Size nasıl yardımcı olabiliriz?", "category": "utility", "language": "tr"},
            {"name": "Sipariş Onayı", "body": "Siparişiniz alındı! Sipariş No: {{order_id}}. Kargo takip numaranız: {{tracking_code}}", "category": "utility", "language": "tr"},
            {"name": "Randevu Hatırlatma", "body": "Merhaba {{name}}, {{date}} tarihinde saat {{time}}'de randevunuz bulunmaktadır.", "category": "utility", "language": "tr"},
            {"name": "Kampanya Duyurusu", "body": "🎉 Özel kampanya! {{discount}}% indirim fırsatını kaçırmayın. Son gün: {{end_date}}", "category": "marketing", "language": "tr"},
        ]
        
        for tmpl_data in templates_data:
            tmpl = MessageTemplate(workspace_id=workspace_id, created_by=user_id, **tmpl_data)
            db.session.add(tmpl)
        logger.info(f"Created {len(templates_data)} message templates")
        
        # 9. AUTOMATION RULES
        logger.info("Creating automation rules...")
        auto_rule = AutomationRule(
            workspace_id=workspace_id,
            name="Yeni Müşteri Hoş Geldin",
            description="Yeni konuşma başladığında otomatik hoş geldin mesajı gönder",
            is_active=True,
            trigger_type="new_conversation",
            trigger_config='{}',
            conditions='{}',
            actions='[{"type": "send_message", "message": "Merhaba! Size nasıl yardımcı olabilirim?"}]',
            created_by=user_id
        )
        db.session.add(auto_rule)
        logger.info("Created 1 automation rule")
        
        # 10. AUTO REPLIES
        logger.info("Creating auto replies...")
        auto_replies_data = [
            {"name": "Fiyat Sorusu", "keywords": "fiyat,ücret,maliyet,ne kadar", "match_type": "contains", "reply_message": "Fiyatlandırma bilgilerimiz için lütfen e-posta adresinizi paylaşın, size detaylı teklif gönderelim."},
            {"name": "Demo Talebi", "keywords": "demo,deneme,test", "match_type": "contains", "reply_message": "Demo talebiniz için teşekkürler! Size uygun bir tarih ve saat belirtir misiniz?"},
            {"name": "Çalışma Saatleri", "keywords": "saat,açık,kapalı,çalışma saati", "match_type": "contains", "reply_message": "Çalışma saatlerimiz: Hafta içi 09:00-18:00. Mesajınızı bırakabilirsiniz, en kısa sürede dönüş yapacağız."},
        ]
        
        for ar_data in auto_replies_data:
            ar = AutoReply(workspace_id=workspace_id, created_by=user_id, **ar_data)
            db.session.add(ar)
        logger.info(f"Created {len(auto_replies_data)} auto replies")
        
        # 11. ACTIVITIES
        logger.info("Creating activity timeline...")
        activities_data = [
            {"activity_type": "email", "contact_id": contacts[0].id, "company_id": companies[0].id, "deal_id": deals[0].id, "user_id": user_id, "subject": "Teklif Sunumu", "body": "Detaylı teklif sunumumuzu e-posta ile gönderdik.", "created_at": datetime.now() - timedelta(days=3)},
            {"activity_type": "call", "contact_id": contacts[2].id, "company_id": companies[1].id, "deal_id": deals[1].id, "user_id": user_id, "subject": "İlk Görüşme", "body": "30 dakikalık telefon görüşmesi yapıldı. Müşteri ürünle ilgileniyor.", "created_at": datetime.now() - timedelta(days=5)},
            {"activity_type": "meeting", "contact_id": contacts[0].id, "company_id": companies[0].id, "deal_id": deals[0].id, "user_id": user_id, "subject": "Demo Toplantısı", "body": "Ürün demosu başarıyla tamamlandı. Müşteri çok memnun kaldı.", "created_at": datetime.now() - timedelta(days=7)},
            {"activity_type": "note", "contact_id": contacts[4].id, "company_id": companies[3].id, "deal_id": deals[3].id, "user_id": user_id, "subject": "Sözleşme İmzalandı", "body": "Müşteri sözleşmeyi imzaladı. Proje başlangıç tarihi belirlendi.", "created_at": datetime.now() - timedelta(days=5)},
            {"activity_type": "whatsapp", "contact_id": contacts[0].id, "company_id": companies[0].id, "user_id": user_id, "subject": "WhatsApp Görüşmesi", "body": "Fiyatlandırma hakkında WhatsApp üzerinden görüşüldü.", "created_at": datetime.now() - timedelta(hours=2)},
        ]
        
        for act_data in activities_data:
            activity = Activity(workspace_id=workspace_id, **act_data)
            db.session.add(activity)
        logger.info(f"Created {len(activities_data)} activities")
        
        # 12. CUSTOM FIELDS
        logger.info("Creating custom fields...")
        custom_fields_data = [
            {"entity_type": "contact", "field_name": "LinkedIn Profili", "field_type": "text"},
            {"entity_type": "company", "field_name": "Yıllık Ciro", "field_type": "number"},
            {"entity_type": "deal", "field_name": "Rekabet Durumu", "field_type": "dropdown", "options": '["Yok", "Düşük", "Orta", "Yüksek"]'},
        ]
        
        custom_fields = []
        for cf_data in custom_fields_data:
            cf = CustomField(workspace_id=workspace_id, **cf_data)
            db.session.add(cf)
            custom_fields.append(cf)
        db.session.flush()
        
        # Add custom field values
        cfv1 = CustomFieldValue(custom_field_id=custom_fields[0].id, entity_id=contacts[0].id, value="https://linkedin.com/in/ahmetyilmaz")
        cfv2 = CustomFieldValue(custom_field_id=custom_fields[1].id, entity_id=companies[0].id, value="5000000")
        cfv3 = CustomFieldValue(custom_field_id=custom_fields[2].id, entity_id=deals[0].id, value="Orta")
        db.session.add_all([cfv1, cfv2, cfv3])
        
        logger.info(f"Created {len(custom_fields_data)} custom fields")
        
        # 13. EMAIL TRACKING (Demo)
        logger.info("Creating email tracking data...")
        from models_crm import EmailTracking
        from services.email_tracking_service import EmailTrackingService
        
        # Create some tracked emails
        for i, contact in enumerate(contacts[:3]):
            tracking = EmailTrackingService.create_tracking(
                workspace_id=workspace_id,
                recipient_email=contact.email,
                subject=f"Demo Email {i+1}: Teklif Sunumu",
                contact_id=contact.id
            )
            tracking.sent_at = datetime.now() - timedelta(days=i+1)
            
            # Simulate opens and clicks
            if i < 2:  # First 2 emails are opened
                tracking.opened_at = datetime.now() - timedelta(days=i+1, hours=2)
                tracking.open_count = i + 2
                tracking.last_opened_at = datetime.now() - timedelta(hours=i+5)
            
            if i == 0:  # First email has clicks
                tracking.click_count = 3
                tracking.last_clicked_at = datetime.now() - timedelta(hours=3)
        
        db.session.commit()
        logger.info("Created 3 email tracking records")
        
        # COMMIT ALL
        db.session.commit()
        
        logger.info("✅ Demo data created successfully!")
        logger.info(f"Summary: {len(companies)} companies, {len(contacts)} contacts, {len(deals)} deals, {len(tasks)} tasks")

if __name__ == '__main__':
    seed_demo_data()
