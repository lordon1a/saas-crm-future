"""
Automation Engine
Otomasyon kurallarını çalıştıran ana motor
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class AutomationEngine:
    """Otomasyon motorunun ana sınıfı"""
    
    @staticmethod
    def execute_rule(rule, conversation=None, message=None, context=None):
        """
        Bir otomasyon kuralını çalıştırır
        
        Args:
            rule: AutomationRule instance
            conversation: Conversation instance (opsiyonel)
            message: Message instance (opsiyonel)
            context: Ek bağlam bilgisi (dict)
        
        Returns:
            dict: Çalıştırma sonucu
        """
        from models import db
        from models_automation import AutomationExecution
        
        try:
            # Koşulları kontrol et
            if not AutomationEngine._check_conditions(rule, conversation, message, context):
                logger.info(f"Rule {rule.id} conditions not met, skipping")
                return {'status': 'skipped', 'reason': 'conditions_not_met'}
            
            # Aksiyonları çalıştır
            actions = json.loads(rule.actions) if rule.actions else []
            results = []
            
            for action in actions:
                result = AutomationEngine._execute_action(action, conversation, message, context)
                results.append(result)
            
            # İstatistikleri güncelle
            rule.execution_count += 1
            rule.last_executed_at = datetime.utcnow()
            
            # Execution log kaydet
            execution = AutomationExecution(
                rule_id=rule.id,
                conversation_id=conversation.id if conversation else None,
                status='success',
                execution_data=json.dumps(results),
                executed_at=datetime.utcnow()
            )
            db.session.add(execution)
            db.session.commit()
            
            logger.info(f"Rule {rule.id} executed successfully")
            return {'status': 'success', 'results': results}
            
        except Exception as e:
            logger.error(f"Error executing rule {rule.id}: {e}")
            
            # Hata log kaydet
            execution = AutomationExecution(
                rule_id=rule.id,
                conversation_id=conversation.id if conversation else None,
                status='failed',
                error_message=str(e),
                executed_at=datetime.utcnow()
            )
            db.session.add(execution)
            db.session.commit()
            
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _check_conditions(rule, conversation, message, context):
        """Kural koşullarını kontrol eder"""
        if not rule.conditions:
            return True
        
        try:
            conditions = json.loads(rule.conditions)
            
            # Customer tag kontrolü
            if 'customer_tags' in conditions and conversation:
                required_tags = conditions['customer_tags']
                customer_labels = (conversation.customer.labels or '').split(',')
                customer_labels = [l.strip() for l in customer_labels]
                
                if not any(tag in customer_labels for tag in required_tags):
                    return False
            
            # Conversation tag kontrolü
            if 'conversation_tags' in conditions and conversation:
                required_tags = conditions['conversation_tags']
                conv_tags = (conversation.tags or '').split(',')
                conv_tags = [t.strip() for t in conv_tags]
                
                if not any(tag in conv_tags for tag in required_tags):
                    return False
            
            # Zaman aralığı kontrolü
            if 'time_range' in conditions:
                time_range = conditions['time_range']
                current_hour = datetime.utcnow().hour
                
                if not (time_range['start'] <= current_hour < time_range['end']):
                    return False
            
            # Hafta günü kontrolü
            if 'weekdays' in conditions:
                allowed_days = conditions['weekdays']  # [0-6, 0=Monday]
                current_day = datetime.utcnow().weekday()
                
                if current_day not in allowed_days:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking conditions: {e}")
            return False
    
    @staticmethod
    def _execute_action(action: Dict, conversation, message, context):
        """Bir aksiyonu çalıştırır"""
        action_type = action.get('type')
        
        try:
            if action_type == 'send_message':
                return AutomationEngine._action_send_message(action, conversation)
            
            elif action_type == 'assign_agent':
                return AutomationEngine._action_assign_agent(action, conversation)
            
            elif action_type == 'add_tag':
                return AutomationEngine._action_add_tag(action, conversation)
            
            elif action_type == 'create_ticket':
                return AutomationEngine._action_create_ticket(action, conversation)
            
            elif action_type == 'send_notification':
                return AutomationEngine._action_send_notification(action, conversation)
            
            elif action_type == 'update_customer':
                return AutomationEngine._action_update_customer(action, conversation)
            
            else:
                logger.warning(f"Unknown action type: {action_type}")
                return {'status': 'skipped', 'reason': 'unknown_action_type'}
                
        except Exception as e:
            logger.error(f"Error executing action {action_type}: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _action_send_message(action: Dict, conversation):
        """Mesaj gönder aksiyonu"""
        from services.message_manager import MessageManager
        from services.meta_api_client import MetaAPIClient
        from models import Workspace
        
        message_body = action.get('message')
        if not message_body or not conversation:
            return {'status': 'skipped', 'reason': 'missing_data'}
        
        # Workspace credentials
        workspace = Workspace.query.get(conversation.workspace_id)
        if not workspace or not workspace.whatsapp_access_token:
            return {'status': 'failed', 'reason': 'no_whatsapp_config'}
        
        # Meta API ile gönder
        meta_client = MetaAPIClient(
            access_token=workspace.whatsapp_access_token,
            phone_number_id=workspace.whatsapp_phone_number_id
        )
        
        result = meta_client.send_text_message(
            conversation.customer.phone_number,
            message_body
        )
        
        if result['success']:
            # Veritabanına kaydet
            MessageManager.save_outgoing_message(
                conversation_id=conversation.id,
                message_body=message_body,
                sender_id=None,  # Sistem mesajı
                meta_message_id=result['message_id']
            )
            return {'status': 'success', 'message_id': result['message_id']}
        else:
            return {'status': 'failed', 'error': result['error']}
    
    @staticmethod
    def _action_assign_agent(action: Dict, conversation):
        """Temsilci ata aksiyonu"""
        from models import db
        
        agent_id = action.get('agent_id')
        if not agent_id or not conversation:
            return {'status': 'skipped', 'reason': 'missing_data'}
        
        conversation.assigned_to = agent_id
        db.session.commit()
        
        return {'status': 'success', 'agent_id': agent_id}
    
    @staticmethod
    def _action_add_tag(action: Dict, conversation):
        """Etiket ekle aksiyonu"""
        from models import db
        
        tag = action.get('tag')
        if not tag or not conversation:
            return {'status': 'skipped', 'reason': 'missing_data'}
        
        # Mevcut etiketlere ekle
        current_tags = conversation.tags.split(',') if conversation.tags else []
        current_tags = [t.strip() for t in current_tags if t.strip()]
        
        if tag not in current_tags:
            current_tags.append(tag)
            conversation.tags = ','.join(current_tags)
            db.session.commit()
        
        return {'status': 'success', 'tag': tag}
    
    @staticmethod
    def _action_create_ticket(action: Dict, conversation):
        """Ticket oluştur aksiyonu (gelecekte implement edilecek)"""
        # TODO: Ticket sistemi eklendiğinde implement edilecek
        return {'status': 'pending', 'reason': 'ticket_system_not_implemented'}
    
    @staticmethod
    def _action_send_notification(action: Dict, conversation):
        """Bildirim gönder aksiyonu"""
        # TODO: Notification sistemi ile entegre edilecek
        return {'status': 'pending', 'reason': 'notification_system_not_implemented'}
    
    @staticmethod
    def _action_update_customer(action: Dict, conversation):
        """Müşteri bilgilerini güncelle aksiyonu"""
        from models import db
        
        updates = action.get('updates', {})
        if not updates or not conversation:
            return {'status': 'skipped', 'reason': 'missing_data'}
        
        customer = conversation.customer
        
        if 'labels' in updates:
            customer.labels = updates['labels']
        if 'notes' in updates:
            customer.notes = updates['notes']
        
        db.session.commit()
        
        return {'status': 'success', 'updates': updates}


class AutoReplyEngine:
    """Otomatik yanıt motoru"""
    
    @staticmethod
    def check_and_reply(message, conversation):
        """
        Gelen mesajı kontrol eder ve uygun otomatik yanıtı gönderir
        
        Args:
            message: Message instance
            conversation: Conversation instance
        
        Returns:
            bool: Otomatik yanıt gönderildi mi?
        """
        from models_automation import AutoReply
        from models import db
        import time
        
        # Sadece müşteri mesajlarına yanıt ver
        if message.sender_type != 'customer':
            return False
        
        # Aktif otomatik yanıtları getir
        auto_replies = AutoReply.query.filter_by(
            workspace_id=conversation.workspace_id,
            is_active=True
        ).all()
        
        message_text = message.message_body.lower()
        
        for auto_reply in auto_replies:
            # Koşulları kontrol et
            if not AutoReplyEngine._check_conditions(auto_reply, conversation):
                continue
            
            # Keyword kontrolü
            keywords = [k.strip() for k in auto_reply.keywords.split(',')]
            matched = False
            
            for keyword in keywords:
                keyword_lower = keyword.lower() if not auto_reply.case_sensitive else keyword
                message_check = message.message_body if auto_reply.case_sensitive else message_text
                
                if auto_reply.match_type == 'exact':
                    matched = message_check == keyword_lower
                elif auto_reply.match_type == 'starts_with':
                    matched = message_check.startswith(keyword_lower)
                elif auto_reply.match_type == 'ends_with':
                    matched = message_check.endswith(keyword_lower)
                else:  # contains
                    matched = keyword_lower in message_check
                
                if matched:
                    break
            
            if matched:
                # Gecikme varsa bekle (daha doğal görünmesi için)
                if auto_reply.reply_delay > 0:
                    time.sleep(auto_reply.reply_delay)
                
                # Yanıt gönder
                from services.message_manager import MessageManager
                from services.meta_api_client import MetaAPIClient
                from models import Workspace
                
                workspace = Workspace.query.get(conversation.workspace_id)
                if workspace and workspace.whatsapp_access_token:
                    meta_client = MetaAPIClient(
                        access_token=workspace.whatsapp_access_token,
                        phone_number_id=workspace.whatsapp_phone_number_id
                    )
                    
                    result = meta_client.send_text_message(
                        conversation.customer.phone_number,
                        auto_reply.reply_message
                    )
                    
                    if result['success']:
                        # Veritabanına kaydet
                        MessageManager.save_outgoing_message(
                            conversation_id=conversation.id,
                            message_body=auto_reply.reply_message,
                            sender_id=None,  # Otomatik yanıt
                            meta_message_id=result['message_id']
                        )
                        
                        # İstatistikleri güncelle
                        auto_reply.trigger_count += 1
                        auto_reply.last_triggered_at = datetime.utcnow()
                        db.session.commit()
                        
                        logger.info(f"Auto-reply {auto_reply.id} triggered for message {message.id}")
                        return True
        
        return False
    
    @staticmethod
    def _check_conditions(auto_reply, conversation):
        """Otomatik yanıt koşullarını kontrol eder"""
        if not auto_reply.conditions:
            return True
        
        try:
            conditions = json.loads(auto_reply.conditions)
            
            # Zaman aralığı kontrolü
            if 'time_range' in conditions:
                time_range = conditions['time_range']
                current_hour = datetime.utcnow().hour
                
                if not (time_range['start'] <= current_hour < time_range['end']):
                    return False
            
            # Customer tag kontrolü
            if 'customer_tags' in conditions:
                required_tags = conditions['customer_tags']
                customer_labels = (conversation.customer.labels or '').split(',')
                customer_labels = [l.strip() for l in customer_labels]
                
                if not any(tag in customer_labels for tag in required_tags):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking auto-reply conditions: {e}")
            return False


class AssignmentEngine:
    """Otomatik atama motoru"""
    
    @staticmethod
    def auto_assign_conversation(conversation):
        """
        Yeni konuşmayı otomatik olarak bir temsilciye atar
        
        Args:
            conversation: Conversation instance
        
        Returns:
            int: Atanan agent_id veya None
        """
        from models_automation import AssignmentRule
        from models import db, User
        
        # Aktif atama kurallarını getir (priority sırasına göre)
        rules = AssignmentRule.query.filter_by(
            workspace_id=conversation.workspace_id,
            is_active=True
        ).order_by(AssignmentRule.priority.desc()).all()
        
        for rule in rules:
            # Koşulları kontrol et
            if not AssignmentEngine._check_conditions(rule, conversation):
                continue
            
            # Atama stratejisine göre agent seç
            agent_id = AssignmentEngine._select_agent(rule, conversation)
            
            if agent_id:
                conversation.assigned_to = agent_id
                
                # İstatistikleri güncelle
                rule.assignment_count += 1
                rule.last_assigned_at = datetime.utcnow()
                
                db.session.commit()
                
                logger.info(f"Conversation {conversation.id} auto-assigned to agent {agent_id} by rule {rule.id}")
                return agent_id
        
        return None
    
    @staticmethod
    def _check_conditions(rule, conversation):
        """Atama kuralı koşullarını kontrol eder"""
        if not rule.conditions:
            return True
        
        try:
            conditions = json.loads(rule.conditions)
            
            # Customer tag kontrolü
            if 'customer_tags' in conditions:
                required_tags = conditions['customer_tags']
                customer_labels = (conversation.customer.labels or '').split(',')
                customer_labels = [l.strip() for l in customer_labels]
                
                if not any(tag in customer_labels for tag in required_tags):
                    return False
            
            # Conversation tag kontrolü
            if 'conversation_tags' in conditions:
                required_tags = conditions['conversation_tags']
                conv_tags = (conversation.tags or '').split(',')
                conv_tags = [t.strip() for t in conv_tags]
                
                if not any(tag in conv_tags for tag in required_tags):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking assignment conditions: {e}")
            return False
    
    @staticmethod
    def _select_agent(rule, conversation):
        """Atama stratejisine göre agent seçer"""
        from models import User, Conversation
        
        try:
            config = json.loads(rule.assignment_config) if rule.assignment_config else {}
            
            if rule.assignment_type == 'specific_agent':
                # Belirli bir agent'a ata
                return config.get('agent_id')
            
            elif rule.assignment_type == 'round_robin':
                # Sırayla ata
                agent_ids = config.get('agent_ids', [])
                if not agent_ids:
                    return None
                
                # Son atanan agent'ı bul
                last_assignment = Conversation.query.filter(
                    Conversation.workspace_id == conversation.workspace_id,
                    Conversation.assigned_to.in_(agent_ids)
                ).order_by(Conversation.last_message_at.desc()).first()
                
                if last_assignment and last_assignment.assigned_to:
                    # Bir sonraki agent'ı seç
                    current_index = agent_ids.index(last_assignment.assigned_to)
                    next_index = (current_index + 1) % len(agent_ids)
                    return agent_ids[next_index]
                else:
                    # İlk agent'ı seç
                    return agent_ids[0]
            
            elif rule.assignment_type == 'load_based':
                # En az yükü olan agent'a ata
                agent_ids = config.get('agent_ids', [])
                if not agent_ids:
                    return None
                
                # Her agent'ın açık konuşma sayısını hesapla
                from sqlalchemy import func
                loads = {}
                for agent_id in agent_ids:
                    count = Conversation.query.filter_by(
                        workspace_id=conversation.workspace_id,
                        assigned_to=agent_id,
                        status='open'
                    ).count()
                    loads[agent_id] = count
                
                # En az yükü olan agent'ı seç
                return min(loads, key=loads.get)
            
            return None
            
        except Exception as e:
            logger.error(f"Error selecting agent: {e}")
            return None
