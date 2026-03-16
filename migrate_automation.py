"""
Migration script to add Automation tables
Otomasyon tablolarını ekler
"""
from app import app
from models import db
from sqlalchemy import text

def migrate():
    with app.app_context():
        print("Creating Automation tables...")
        
        try:
            # Import automation models
            from models_automation import (
                AutomationRule, AutomationExecution, ScheduledMessage,
                AutoReply, AssignmentRule, WorkflowTemplate
            )
            
            # Create all tables (will only create missing ones)
            db.create_all()
            
            print("✓ Migration completed successfully!")
            print("\nCreated tables:")
            print("  - automation_rules")
            print("  - automation_executions")
            print("  - scheduled_messages")
            print("  - auto_replies")
            print("  - assignment_rules")
            print("  - workflow_templates")
            
            # Örnek workflow template'leri ekle
            print("\nAdding sample workflow templates...")
            
            templates = [
                {
                    'name': 'Yeni Müşteri Hoş Geldin',
                    'description': 'Yeni müşterilere otomatik hoş geldin mesajı gönderir',
                    'category': 'onboarding',
                    'icon': 'fa-hand-wave',
                    'workflow_config': '''{
                        "trigger": "new_conversation",
                        "actions": [
                            {
                                "type": "send_message",
                                "message": "Merhaba! Size nasıl yardımcı olabilirim?"
                            }
                        ]
                    }'''
                },
                {
                    'name': 'Sipariş Takibi',
                    'description': 'Sipariş etiketli konuşmalara otomatik takip mesajı',
                    'category': 'sales',
                    'icon': 'fa-box',
                    'workflow_config': '''{
                        "trigger": "tag_added",
                        "trigger_config": {"tag": "yeni_siparis"},
                        "actions": [
                            {
                                "type": "send_message",
                                "message": "Siparişiniz alındı! En kısa sürede kargoya verilecektir."
                            },
                            {
                                "type": "assign_agent",
                                "strategy": "round_robin"
                            }
                        ]
                    }'''
                },
                {
                    'name': 'Destek Talebi Yönlendirme',
                    'description': 'Destek taleplerini otomatik olarak uygun temsilciye yönlendirir',
                    'category': 'support',
                    'icon': 'fa-headset',
                    'workflow_config': '''{
                        "trigger": "keyword",
                        "trigger_config": {"keywords": ["destek", "yardım", "sorun"]},
                        "actions": [
                            {
                                "type": "add_tag",
                                "tag": "destek_talebi"
                            },
                            {
                                "type": "assign_agent",
                                "strategy": "load_based"
                            }
                        ]
                    }'''
                }
            ]
            
            for tmpl_data in templates:
                existing = WorkflowTemplate.query.filter_by(name=tmpl_data['name']).first()
                if not existing:
                    template = WorkflowTemplate(
                        name=tmpl_data['name'],
                        description=tmpl_data['description'],
                        category=tmpl_data['category'],
                        icon=tmpl_data['icon'],
                        workflow_config=tmpl_data['workflow_config'],
                        is_system=True
                    )
                    db.session.add(template)
                    print(f"  ✓ {tmpl_data['name']}")
            
            db.session.commit()
            print("\n✅ All done! Automation system is ready.")
            
        except Exception as e:
            print(f"✗ Migration failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    migrate()
