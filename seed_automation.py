"""
Seed Automation Rules
Örnek otomasyon kuralları oluşturur
"""
from app import app
from models import db
from models_automation import AutoReply, AssignmentRule, AutomationRule
import json

def seed_automation():
    with app.app_context():
        print("Creating sample automation rules...")
        
        workspace_id = 1  # Default workspace
        
        # 1. Otomatik Yanıtlar
        auto_replies = [
            {
                'name': 'Merhaba Yanıtı',
                'keywords': 'merhaba, selam, hello, hi',
                'match_type': 'contains',
                'case_sensitive': False,
                'reply_message': 'Merhaba! Size nasıl yardımcı olabilirim? 😊',
                'reply_delay': 1,
                'is_active': True
            },
            {
                'name': 'Fiyat Bilgisi',
                'keywords': 'fiyat, ücret, ne kadar, price',
                'match_type': 'contains',
                'case_sensitive': False,
                'reply_message': 'Fiyat listemiz için lütfen web sitemizi ziyaret edin: https://example.com/fiyatlar\n\nDetaylı bilgi için size yardımcı olabilirim!',
                'reply_delay': 2,
                'is_active': True
            },
            {
                'name': 'Çalışma Saatleri',
                'keywords': 'çalışma saatleri, mesai, açık mısınız, kaçta açık',
                'match_type': 'contains',
                'case_sensitive': False,
                'reply_message': '⏰ Çalışma Saatlerimiz:\nHafta içi: 09:00 - 18:00\nCumartesi: 10:00 - 16:00\nPazar: Kapalı',
                'reply_delay': 1,
                'is_active': True
            },
            {
                'name': 'IBAN Bilgisi',
                'keywords': 'iban, hesap numarası, banka, ödeme',
                'match_type': 'contains',
                'case_sensitive': False,
                'reply_message': '💳 Banka Bilgilerimiz:\nIBAN: TR00 0000 0000 0000 0000 0000 00\nAlıcı: Örnek Şirket A.Ş.\n\nÖdeme yaptıktan sonra dekont görseli göndermeyi unutmayın!',
                'reply_delay': 2,
                'is_active': True
            },
            {
                'name': 'Teşekkür Yanıtı',
                'keywords': 'teşekkür, sağol, thanks, thank you',
                'match_type': 'contains',
                'case_sensitive': False,
                'reply_message': 'Rica ederim! Başka bir konuda yardımcı olabilirsem lütfen çekinmeden yazın. 🙏',
                'reply_delay': 1,
                'is_active': True
            }
        ]
        
        for reply_data in auto_replies:
            existing = AutoReply.query.filter_by(
                workspace_id=workspace_id,
                name=reply_data['name']
            ).first()
            
            if not existing:
                reply = AutoReply(
                    workspace_id=workspace_id,
                    **reply_data
                )
                db.session.add(reply)
                print(f"  ✓ {reply_data['name']}")
            else:
                print(f"  ⚠ {reply_data['name']} already exists")
        
        # 2. Atama Kuralları
        assignment_rules = [
            {
                'name': 'VIP Müşteri Atama',
                'is_active': True,
                'priority': 10,
                'conditions': json.dumps({
                    'customer_tags': ['VIP']
                }),
                'assignment_type': 'specific_agent',
                'assignment_config': json.dumps({
                    'agent_id': 1  # Admin'e ata
                })
            },
            {
                'name': 'Genel Round-Robin Atama',
                'is_active': True,
                'priority': 0,
                'conditions': json.dumps({}),
                'assignment_type': 'round_robin',
                'assignment_config': json.dumps({
                    'agent_ids': [1, 2]  # Admin ve Agent
                })
            }
        ]
        
        for rule_data in assignment_rules:
            existing = AssignmentRule.query.filter_by(
                workspace_id=workspace_id,
                name=rule_data['name']
            ).first()
            
            if not existing:
                rule = AssignmentRule(
                    workspace_id=workspace_id,
                    **rule_data
                )
                db.session.add(rule)
                print(f"  ✓ {rule_data['name']}")
            else:
                print(f"  ⚠ {rule_data['name']} already exists")
        
        # 3. Otomasyon Kuralları
        automation_rules = [
            {
                'name': 'Yeni Müşteri Hoş Geldin',
                'description': 'Yeni konuşma başladığında hoş geldin mesajı gönder',
                'is_active': True,
                'trigger_type': 'new_conversation',
                'trigger_config': json.dumps({}),
                'conditions': json.dumps({}),
                'actions': json.dumps([
                    {
                        'type': 'send_message',
                        'message': '👋 Hoş geldiniz! Size nasıl yardımcı olabilirim?'
                    }
                ])
            },
            {
                'name': 'Sipariş Onay Mesajı',
                'description': 'Yeni sipariş etiketlendiğinde onay mesajı gönder',
                'is_active': True,
                'trigger_type': 'tag_added',
                'trigger_config': json.dumps({
                    'tag': 'yeni_siparis'
                }),
                'conditions': json.dumps({}),
                'actions': json.dumps([
                    {
                        'type': 'send_message',
                        'message': '✅ Siparişiniz başarıyla alındı! En kısa sürede kargoya verilecektir.'
                    },
                    {
                        'type': 'add_tag',
                        'tag': 'siparis_onaylandi'
                    }
                ])
            }
        ]
        
        for rule_data in automation_rules:
            existing = AutomationRule.query.filter_by(
                workspace_id=workspace_id,
                name=rule_data['name']
            ).first()
            
            if not existing:
                rule = AutomationRule(
                    workspace_id=workspace_id,
                    **rule_data
                )
                db.session.add(rule)
                print(f"  ✓ {rule_data['name']}")
            else:
                print(f"  ⚠ {rule_data['name']} already exists")
        
        db.session.commit()
        print("\n✅ Automation rules seeded successfully!")
        print("\nCreated:")
        print(f"  - {len(auto_replies)} Auto-replies")
        print(f"  - {len(assignment_rules)} Assignment rules")
        print(f"  - {len(automation_rules)} Automation rules")

if __name__ == '__main__':
    seed_automation()
