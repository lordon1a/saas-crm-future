"""
Workflow Node Handlers
======================
Individual handlers for each node type in the workflow graph.

Architecture:
- Each handler receives: node_data, context, config
- Handlers return a dict with their output
- Handlers can read/write from context
- Handlers should be pure functions (no side effects except DB writes)

Handler Registry:
- TriggerHandler: Handles all trigger node types
- ConditionHandler: Handles condition/branch nodes
- ActionHandler: Handles all action nodes
"""
import json
import logging
import httpx
import requests
import base64
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class NodeHandlerRegistry:
    """Registry for all node handlers"""
    
    _handlers = {}
    
    @classmethod
    def register(cls, node_type: str):
        """Decorator to register a handler"""
        def decorator(func):
            cls._handlers[node_type] = func
            return func
        return decorator
    
    @classmethod
    def get_handler(cls, node_type: str):
        return cls._handlers.get(node_type)
    
    @classmethod
    def get_all_handlers(cls):
        return cls._handlers.copy()


# ═══════════════════════════════════════════════════════════════════
# TRIGGER HANDLERS
# ═══════════════════════════════════════════════════════════════════

class TriggerHandler:
    """Handles all trigger node types"""
    
    @staticmethod
    def handle(node_data: Dict, context: Dict, config: Dict) -> Dict:
        subtype = node_data.get('subtype', '')
        handler_map = {
            'contact_created': TriggerHandler._contact_created,
            'contact_updated': TriggerHandler._contact_updated,
            'contact_tag_added': TriggerHandler._contact_tag_added,
            'contact_no_activity': TriggerHandler._contact_no_activity,
            'deal_created': TriggerHandler._deal_created,
            'deal_stage_changed': TriggerHandler._deal_stage_changed,
            'deal_won': TriggerHandler._deal_won,
            'deal_lost': TriggerHandler._deal_lost,
            'deal_amount_changed': TriggerHandler._deal_amount_changed,
            'deal_no_activity': TriggerHandler._deal_no_activity,
            'task_created': TriggerHandler._task_created,
            'task_completed': TriggerHandler._task_completed,
            'deal_close_date_approaching': TriggerHandler._deal_close_date_approaching,
        }
        
        handler = handler_map.get(subtype)
        if handler:
            return handler(node_data, context, config)
        
        return {'status': 'skipped', 'reason': f'Unknown trigger: {subtype}'}
    
    @staticmethod
    def _contact_created(node_data, context, config):
        return {
            'trigger': 'contact_created',
            'entity': context.get('entity', {}),
            'message': 'Contact created trigger fired',
        }
    
    @staticmethod
    def _contact_updated(node_data, context, config):
        return {
            'trigger': 'contact_updated',
            'entity': context.get('entity', {}),
            'message': 'Contact updated trigger fired',
        }
    
    @staticmethod
    def _contact_tag_added(node_data, context, config):
        tag_name = config.get('tag_name', '')
        return {
            'trigger': 'contact_tag_added',
            'tag_name': tag_name,
            'entity': context.get('entity', {}),
        }
    
    @staticmethod
    def _contact_no_activity(node_data, context, config):
        days = int(config.get('days', 30))
        min_lead_score = int(config.get('min_lead_score', 0))
        return {
            'trigger': 'contact_no_activity',
            'days': days,
            'min_lead_score': min_lead_score,
            'entity': context.get('entity', {}),
        }
    
    @staticmethod
    def _deal_created(node_data, context, config):
        return {
            'trigger': 'deal_created',
            'entity': context.get('entity', {}),
            'message': 'Deal created trigger fired',
        }
    
    @staticmethod
    def _deal_stage_changed(node_data, context, config):
        from_stage = config.get('from_stage_id')
        to_stage = config.get('to_stage_id')
        return {
            'trigger': 'deal_stage_changed',
            'from_stage_id': from_stage,
            'to_stage_id': to_stage,
            'entity': context.get('entity', {}),
        }
    
    @staticmethod
    def _deal_won(node_data, context, config):
        return {
            'trigger': 'deal_won',
            'entity': context.get('entity', {}),
            'message': 'Deal won trigger fired',
        }
    
    @staticmethod
    def _deal_lost(node_data, context, config):
        return {
            'trigger': 'deal_lost',
            'entity': context.get('entity', {}),
            'message': 'Deal lost trigger fired',
        }
    
    @staticmethod
    def _deal_amount_changed(node_data, context, config):
        return {
            'trigger': 'deal_amount_changed',
            'entity': context.get('entity', {}),
        }
    
    @staticmethod
    def _deal_no_activity(node_data, context, config):
        days = int(config.get('days', 14))
        return {
            'trigger': 'deal_no_activity',
            'days': days,
            'entity': context.get('entity', {}),
        }
    
    @staticmethod
    def _task_created(node_data, context, config):
        return {
            'trigger': 'task_created',
            'entity': context.get('entity', {}),
        }
    
    @staticmethod
    def _task_completed(node_data, context, config):
        return {
            'trigger': 'task_completed',
            'entity': context.get('entity', {}),
        }
    
    @staticmethod
    def _deal_close_date_approaching(node_data, context, config):
        days_before = int(config.get('days_before', 7))
        return {
            'trigger': 'deal_close_date_approaching',
            'days_before': days_before,
            'entity': context.get('entity', {}),
        }
    
    @staticmethod
    def _manual(node_data, context, config):
        return {
            'trigger': 'manual',
            'description': config.get('description', ''),
            'entity': context.get('entity', {}),
            'message': 'Manual trigger fired',
        }
    
    @staticmethod
    def _schedule(node_data, context, config):
        return {
            'trigger': 'schedule',
            'interval_type': config.get('interval_type', 'every_day'),
            'run_time': config.get('run_time', ''),
            'cron_expression': config.get('cron_expression', ''),
            'entity': context.get('entity', {}),
        }
    
    @staticmethod
    def _webhook_trigger(node_data, context, config):
        return {
            'trigger': 'webhook_trigger',
            'method': config.get('method', 'POST'),
            'payload': context.get('trigger', {}).get('payload', {}),
            'entity': context.get('entity', {}),
        }


# ═══════════════════════════════════════════════════════════════════
# CONDITION HANDLERS
# ═══════════════════════════════════════════════════════════════════

class ConditionHandler:
    """Handles condition/branch nodes"""
    
    @staticmethod
    def handle(node_data: Dict, context: Dict, config: Dict) -> Dict:
        subtype = node_data.get('subtype', '')
        handler_map = {
            'check_field': ConditionHandler._check_field,
            'check_score': ConditionHandler._check_score,
            'if': ConditionHandler._if_condition,
            'if_else': ConditionHandler._if_condition,
            'loop_over_items': ConditionHandler._loop_over_items,
            'error_trigger': ConditionHandler._error_trigger,
            'split_in_batches': ConditionHandler._split_in_batches,
        }
        
        handler = handler_map.get(subtype)
        if handler:
            return handler(node_data, context, config)
        
        # Default: pass through
        return {'condition_result': True, 'reason': f'Unknown condition: {subtype}'}
    
    @staticmethod
    def _check_field(node_data, context, config):
        field_name = config.get('field_name', '')
        operator = config.get('operator', 'equals')
        value = config.get('value', '')
        
        # Resolve field value from entity
        field_value = ConditionHandler._get_field_value(field_name, context)
        
        result = ConditionHandler._evaluate_operator(field_value, operator, value)
        
        return {
            'condition_result': result,
            'field_name': field_name,
            'field_value': field_value,
            'operator': operator,
            'expected_value': value,
        }
    
    @staticmethod
    def _check_score(node_data, context, config):
        operator = config.get('operator', 'greater_than')
        expected_score = float(config.get('value', 50))
        
        entity = context.get('entity', {})
        actual_score = float(entity.get('lead_score', 0) or 0)
        
        result = ConditionHandler._evaluate_operator(actual_score, operator, expected_score)
        
        return {
            'condition_result': result,
            'actual_score': actual_score,
            'expected_score': expected_score,
            'operator': operator,
        }
    
    @staticmethod
    def _if_condition(node_data, context, config):
        conditions_str = config.get('conditions', '[]')
        try:
            conditions = json.loads(conditions_str) if isinstance(conditions_str, str) else conditions_str
        except:
            conditions = []
        
        if not conditions:
            return {'condition_result': True, 'reason': 'No conditions defined'}
        
        # Evaluate all conditions (AND logic by default)
        all_passed = True
        for cond in conditions:
            field = cond.get('field', '')
            operator = cond.get('operator', 'equals')
            expected = cond.get('value', '')
            
            field_value = ConditionHandler._get_field_value(field, context)
            if not ConditionHandler._evaluate_operator(field_value, operator, expected):
                all_passed = False
                break
        
        return {
            'condition_result': all_passed,
            'conditions_evaluated': len(conditions),
        }
    
    @staticmethod
    def _loop_over_items(node_data, context, config):
        items_field = config.get('items_field', '')
        items = ConditionHandler._get_field_value(items_field, context)
        
        if not items:
            return {'condition_result': False, 'reason': 'No items to loop over', 'item_count': 0}
        
        if isinstance(items, str):
            try:
                items = json.loads(items)
            except:
                items = [items]
        
        if not isinstance(items, list):
            items = [items]
        
        return {
            'condition_result': True,
            'item_count': len(items),
            'items': items[:100],
        }
    
    @staticmethod
    def _error_trigger(node_data, context, config):
        error_threshold = int(config.get('error_threshold', 1))
        previous_errors = context.get('variables', {}).get('previous_errors', 0)
        
        trigger = previous_errors >= error_threshold
        
        return {
            'condition_result': trigger,
            'error_count': previous_errors,
            'threshold': error_threshold,
        }
    
    @staticmethod
    def _split_in_batches(node_data, context, config):
        batch_size = int(config.get('batch_size', 10))
        total_items = int(config.get('total_items', 0))
        
        if total_items == 0:
            items_field = config.get('items_field', '')
            items = ConditionHandler._get_field_value(items_field, context)
            if isinstance(items, list):
                total_items = len(items)
        
        batch_count = (total_items + batch_size - 1) // batch_size if total_items > 0 else 0
        
        return {
            'condition_result': True,
            'batch_count': batch_count,
            'batch_size': batch_size,
            'total_items': total_items,
        }
    
    @staticmethod
    def _get_field_value(field_name: str, context: Dict) -> Any:
        """Get field value from context using dot notation"""
        parts = field_name.split('.')
        current = context
        
        for part in parts:
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(part)
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
        
        return current
    
    @staticmethod
    def _evaluate_operator(actual, operator: str, expected) -> bool:
        """Evaluate a condition operator"""
        if actual is None:
            return operator in ('is_empty',)
        
        # Convert to comparable types
        try:
            actual_num = float(actual)
            expected_num = float(expected)
        except (ValueError, TypeError):
            actual_num = None
            expected_num = None
        
        if operator == 'equals':
            return str(actual).lower() == str(expected).lower()
        elif operator == 'not_equals':
            return str(actual).lower() != str(expected).lower()
        elif operator == 'greater_than':
            if actual_num is not None and expected_num is not None:
                return actual_num > expected_num
            return False
        elif operator == 'less_than':
            if actual_num is not None and expected_num is not None:
                return actual_num < expected_num
            return False
        elif operator == 'greater_than_or_equals':
            if actual_num is not None and expected_num is not None:
                return actual_num >= expected_num
            return False
        elif operator == 'less_than_or_equals':
            if actual_num is not None and expected_num is not None:
                return actual_num <= expected_num
            return False
        elif operator == 'contains':
            return str(expected).lower() in str(actual).lower()
        elif operator == 'not_contains':
            return str(expected).lower() not in str(actual).lower()
        elif operator == 'starts_with':
            return str(actual).lower().startswith(str(expected).lower())
        elif operator == 'ends_with':
            return str(actual).lower().endswith(str(expected).lower())
        elif operator == 'is_empty':
            return actual == '' or actual is None or actual == 0
        elif operator == 'is_not_empty':
            return actual != '' and actual is not None and actual != 0
        else:
            logger.warning(f"Unknown operator: {operator}")
            return False


# ═══════════════════════════════════════════════════════════════════
# ACTION HANDLERS
# ═══════════════════════════════════════════════════════════════════

class ActionHandler:
    """Handles all action node types"""
    
    @staticmethod
    def handle(node_data: Dict, context: Dict, config: Dict) -> Dict:
        subtype = node_data.get('subtype', '')
        handler_map = {
            'create_task': ActionHandler._create_task,
            'send_email': ActionHandler._send_email,
            'send_whatsapp': ActionHandler._send_whatsapp,
            'notify_owner': ActionHandler._notify_owner,
            'update_deal_stage': ActionHandler._update_deal_stage,
            'update_deal_field': ActionHandler._update_deal_field,
            'update_contact_field': ActionHandler._update_contact_field,
            'add_tag': ActionHandler._add_tag,
            'remove_tag': ActionHandler._remove_tag,
            'assign_owner': ActionHandler._assign_owner,
            'create_note': ActionHandler._create_note,
            'webhook': ActionHandler._webhook,
            'delay': ActionHandler._delay,
            'wait': ActionHandler._wait,
            'http_request': ActionHandler._http_request,
            'find_records': ActionHandler._find_records,
            'delete_record': ActionHandler._delete_record,
            'code': ActionHandler._code,
            'wait_until': ActionHandler._wait_until,
            'set_node': ActionHandler._set_node,
            'ai_agent': ActionHandler._ai_agent,
            'call_workflow': ActionHandler._call_workflow,
        }
        
        handler = handler_map.get(subtype)
        if handler:
            return handler(node_data, context, config)
        
        return {'status': 'skipped', 'reason': f'Unknown action: {subtype}'}
    
    @staticmethod
    def _resolve_template(template: str, context: Dict) -> str:
        """Resolve template variables"""
        if not template or not isinstance(template, str):
            return template
        
        import re
        
        def replace_var(match):
            var_path = match.group(1).strip()
            return str(ActionHandler._resolve_path(var_path, context))
        
        pattern = r'\{\{([^}]+)\}\}'
        return re.sub(pattern, replace_var, template)
    
    @staticmethod
    def _resolve_path(path: str, context: Dict) -> Any:
        """Resolve a dotted path against context"""
        parts = path.split('.')
        current = context
        
        for part in parts:
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        
        return current
    
    @staticmethod
    def _create_task(node_data, context, config):
        from models_crm import Task
        from models import db
        
        entity = context.get('entity', {})
        workspace_id = context.get('workspace_id')
        
        title = ActionHandler._resolve_template(config.get('title', 'Workflow Task'), context)
        description = ActionHandler._resolve_template(config.get('description', ''), context)
        due_in_days = int(config.get('due_in_days', 2))
        priority = config.get('priority', 'medium')
        
        # Resolve assignment
        assign_to = config.get('assign_to', 'contact_owner')
        assigned_to = None
        if assign_to == 'contact_owner':
            assigned_to = entity.get('assigned_to')
        elif assign_to == 'deal_owner':
            assigned_to = entity.get('assigned_to')
        
        due_date = datetime.utcnow() + timedelta(days=due_in_days)
        
        task = Task(
            workspace_id=workspace_id,
            title=title,
            description=description,
            due_date=due_date,
            priority=priority,
            assignee_id=assigned_to,
            status='pending',
        )
        
        # Link to entity
        entity_type = context.get('entity_type')
        entity_id = context.get('entity_id')
        if entity_type == 'deal':
            task.deal_id = entity_id
        elif entity_type == 'contact':
            task.contact_id = entity_id
        
        try:
            db.session.add(task)
            db.session.commit()
            return {
                'status': 'success',
                'task_id': task.id,
                'title': title,
            }
        except Exception as e:
            db.session.rollback()
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _send_email(node_data, context, config):
        from services.email_hub_service import EmailHubService
        from models import User
        
        entity = context.get('entity', {})
        workspace_id = context.get('workspace_id')
        
        to_email = ActionHandler._resolve_template(config.get('to', ''), context)
        subject = ActionHandler._resolve_template(config.get('subject', ''), context)
        body = ActionHandler._resolve_template(config.get('body', ''), context)
        
        if not to_email or not subject:
            return {'status': 'skipped', 'reason': 'Missing to or subject'}
        
        try:
            result = EmailHubService.send_workflow_email(
                workspace_id=workspace_id,
                to_email=to_email,
                subject=subject,
                body=body,
            )
            
            if result.get('success'):
                return {'status': 'success', 'message_id': result.get('message_id')}
            return {'status': 'failed', 'error': result.get('error', 'Unknown error')}
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _send_whatsapp(node_data, context, config):
        message = ActionHandler._resolve_template(config.get('message', ''), context)
        entity = context.get('entity', {})
        
        if not message:
            return {'status': 'skipped', 'reason': 'No message specified'}
        
        from models import Workspace
        from services.message_manager import MessageManager
        from services.meta_api_client import MetaAPIClient
        
        phone = entity.get('phone') or entity.get('phone_number')
        if not phone:
            return {'status': 'skipped', 'reason': 'No phone number found'}
        
        workspace_id = context.get('workspace_id')
        if not workspace_id:
            return {'status': 'failed', 'error': 'No workspace_id in context'}
        
        try:
            workspace = Workspace.query.get(workspace_id)
            if not workspace or not workspace.whatsapp_access_token:
                return {'status': 'failed', 'error': 'WhatsApp not configured for workspace'}
            
            meta_client = MetaAPIClient(
                access_token=workspace.whatsapp_access_token,
                phone_number_id=workspace.whatsapp_phone_number_id
            )
            
            result = meta_client.send_text_message(phone, message)
            
            if result['success']:
                return {
                    'status': 'success',
                    'message_id': result['message_id'],
                    'phone': phone,
                }
            return {'status': 'failed', 'error': result.get('error', 'Unknown error')}
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _notify_owner(node_data, context, config):
        from services.notification_service import NotificationService
        
        entity = context.get('entity', {})
        workspace_id = context.get('workspace_id')
        
        message = ActionHandler._resolve_template(config.get('message', ''), context)
        title = config.get('title', 'Workflow Alert')
        
        owner_id = entity.get('assigned_to') or entity.get('created_by')
        if not owner_id:
            return {'status': 'skipped', 'reason': 'No owner found'}
        
        try:
            NotificationService.create_notification(
                workspace_id=workspace_id,
                user_id=owner_id,
                notification_type='workflow_alert',
                title=title,
                message=message,
                link=f'/{context.get("entity_type", "entity")}s/{context.get("entity_id")}',
            )
            return {'status': 'success', 'owner_id': owner_id}
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _update_deal_stage(node_data, context, config):
        from models_crm import Deal
        from models import db
        
        entity = context.get('entity', {})
        entity_id = context.get('entity_id')
        
        if context.get('entity_type') != 'deal':
            return {'status': 'skipped', 'reason': 'Entity is not a deal'}
        
        stage_id = config.get('stage_id')
        if not stage_id:
            return {'status': 'skipped', 'reason': 'No stage_id specified'}
        
        try:
            deal = Deal.query.get(entity_id)
            if not deal:
                return {'status': 'failed', 'error': 'Deal not found'}
            
            deal.stage_id = int(stage_id)
            db.session.commit()
            return {'status': 'success', 'stage_id': stage_id}
        except Exception as e:
            db.session.rollback()
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _update_deal_field(node_data, context, config):
        from models_crm import Deal
        from models import db
        
        entity = context.get('entity', {})
        entity_id = context.get('entity_id')
        
        if context.get('entity_type') != 'deal':
            return {'status': 'skipped', 'reason': 'Entity is not a deal'}
        
        field = config.get('field_name') or config.get('field')
        if not field:
            return {'status': 'skipped', 'reason': 'No field specified'}
        
        value = ActionHandler._resolve_template(str(config.get('field_value', '') or config.get('value', '')), context)
        
        try:
            deal = Deal.query.get(entity_id)
            if not deal:
                return {'status': 'failed', 'error': 'Deal not found'}
            
            if hasattr(deal, field):
                setattr(deal, field, value)
                db.session.commit()
                return {'status': 'success', 'field': field, 'value': value}
            return {'status': 'failed', 'error': f'Unknown field: {field}'}
        except Exception as e:
            db.session.rollback()
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _update_contact_field(node_data, context, config):
        from models_crm import Contact
        from models import db
        
        entity = context.get('entity', {})
        entity_id = context.get('entity_id')
        
        if context.get('entity_type') != 'contact':
            return {'status': 'skipped', 'reason': 'Entity is not a contact'}
        
        field = config.get('field_name') or config.get('field')
        if not field:
            return {'status': 'skipped', 'reason': 'No field specified'}
        
        value = ActionHandler._resolve_template(str(config.get('field_value', '') or config.get('value', '')), context)
        
        try:
            contact = Contact.query.get(entity_id)
            if not contact:
                return {'status': 'failed', 'error': 'Contact not found'}
            
            if hasattr(contact, field):
                setattr(contact, field, value)
                db.session.commit()
                return {'status': 'success', 'field': field, 'value': value}
            return {'status': 'failed', 'error': f'Unknown field: {field}'}
        except Exception as e:
            db.session.rollback()
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _add_tag(node_data, context, config):
        entity_id = context.get('entity_id')
        entity_type = context.get('entity_type')
        workspace_id = context.get('workspace_id')

        tag_name = config.get('tag_name') or config.get('tag')
        if not tag_name:
            return {'status': 'skipped', 'reason': 'No tag specified'}

        if entity_type != 'contact':
            return {'status': 'skipped', 'reason': 'add_tag only supports contact entity type'}

        try:
            from services.tag_service import TagService
            tag = TagService.get_or_create_tag(workspace_id, tag_name)
            TagService.add_tags_to_contact(workspace_id, entity_id, [tag.id])
            return {'status': 'success', 'tag': tag_name, 'tag_id': tag.id}
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _remove_tag(node_data, context, config):
        entity_id = context.get('entity_id')
        entity_type = context.get('entity_type')
        workspace_id = context.get('workspace_id')

        tag_name = config.get('tag_name') or config.get('tag')
        if not tag_name:
            return {'status': 'skipped', 'reason': 'No tag specified'}

        if entity_type != 'contact':
            return {'status': 'skipped', 'reason': 'remove_tag only supports contact entity type'}

        try:
            from services.tag_service import TagService
            from models_crm import Tag
            tag = Tag.query.filter_by(workspace_id=workspace_id, name=tag_name).first()
            if not tag:
                return {'status': 'skipped', 'reason': f'Tag not found: {tag_name}'}
            TagService.remove_tag_from_contact(entity_id, tag.id)
            return {'status': 'success', 'tag': tag_name}
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _assign_owner(node_data, context, config):
        from models import db, User
        
        entity = context.get('entity', {})
        entity_id = context.get('entity_id')
        entity_type = context.get('entity_type')
        
        assign_to = config.get('assign_to', 'round_robin')
        
        try:
            if assign_to == 'round_robin':
                users = User.query.filter_by(is_active=True).limit(1).all()
                if not users:
                    return {'status': 'failed', 'error': 'No active users found'}
                assigned_id = users[0].id
            elif isinstance(assign_to, int):
                assigned_id = assign_to
            else:
                return {'status': 'failed', 'error': f'Invalid assign_to value: {assign_to}'}
            
            if entity_type == 'contact':
                from models_crm import Contact
                record = Contact.query.get(entity_id)
            elif entity_type == 'deal':
                from models_crm import Deal
                record = Deal.query.get(entity_id)
            else:
                return {'status': 'skipped', 'reason': 'Unsupported entity type'}
            
            if not record:
                return {'status': 'failed', 'error': 'Record not found'}
            
            if hasattr(record, 'assigned_to'):
                record.assigned_to = assigned_id
                db.session.commit()
                return {'status': 'success', 'assigned_to': assigned_id}
            
            return {'status': 'failed', 'error': 'Entity does not support assignment'}
        except Exception as e:
            db.session.rollback()
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _create_note(node_data, context, config):
        from models_crm import Note
        from models import db
        
        entity = context.get('entity', {})
        workspace_id = context.get('workspace_id')
        entity_type = context.get('entity_type')
        entity_id = context.get('entity_id')
        
        content = ActionHandler._resolve_template(config.get('content', ''), context)
        if not content:
            return {'status': 'skipped', 'reason': 'No content specified'}
        
        try:
            note = Note(
                workspace_id=workspace_id,
                content=content,
                noteable_type=entity_type.capitalize(),
                noteable_id=entity_id,
                is_private=config.get('is_private', False),
            )
            
            if entity_type == 'contact':
                note.contact_id = entity_id
            elif entity_type == 'deal':
                note.deal_id = entity_id
            
            db.session.add(note)
            db.session.commit()
            return {'status': 'success', 'note_id': note.id}
        except Exception as e:
            db.session.rollback()
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _webhook(node_data, context, config):
        url = ActionHandler._resolve_template(config.get('url', ''), context)
        method = config.get('method', 'POST').upper()
        
        if not url:
            return {'status': 'skipped', 'reason': 'No URL specified'}
        
        try:
            payload = {
                'entity': context.get('entity', {}),
                'trigger': context.get('trigger', {}),
                'variables': context.get('variables', {}),
            }
            
            with httpx.Client(timeout=30) as client:
                if method == 'GET':
                    response = client.get(url)
                elif method == 'POST':
                    response = client.post(url, json=payload)
                elif method == 'PUT':
                    response = client.put(url, json=payload)
                else:
                    return {'status': 'failed', 'error': f'Unsupported method: {method}'}
            
            return {
                'status': 'success',
                'http_status': response.status_code,
                'response': response.text[:500] if response.text else '',
            }
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _wait(node_data, context, config):
        delay_minutes = int(config.get('delay_minutes', 60))
        return {
            'status': 'queued',
            'delay_minutes': delay_minutes,
            'execute_after': (datetime.utcnow() + timedelta(minutes=delay_minutes)).isoformat(),
        }
    
    @staticmethod
    def _http_request(node_data, context, config):
        url = ActionHandler._resolve_template(config.get('url', ''), context)
        method = config.get('method', 'GET').upper()
        auth_type = config.get('auth_type', 'none')
        header_key = config.get('header_key', '')
        header_value = ActionHandler._resolve_template(config.get('header_value', ''), context)
        body = ActionHandler._resolve_template(config.get('body', ''), context)
        timeout = int(config.get('timeout', 30))
        
        if not url:
            return {'status': 'skipped', 'reason': 'No URL specified'}
        
        headers = {}
        
        if auth_type == 'bearer' and header_value:
            headers['Authorization'] = f'Bearer {header_value}'
        elif auth_type == 'basic' and header_value:
            encoded = base64.b64encode(header_value.encode()).decode()
            headers['Authorization'] = f'Basic {encoded}'
        elif auth_type == 'api_key' and header_key and header_value:
            headers[header_key] = header_value
        elif header_key and header_value:
            headers[header_key] = header_value
        
        if body and 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/json'
        
        try:
            start_time = datetime.utcnow()
            
            with httpx.Client(timeout=timeout) as client:
                if method == 'GET':
                    response = client.get(url, headers=headers)
                elif method == 'POST':
                    response = client.post(url, headers=headers, content=body)
                elif method == 'PUT':
                    response = client.put(url, headers=headers, content=body)
                elif method == 'PATCH':
                    response = client.patch(url, headers=headers, content=body)
                elif method == 'DELETE':
                    response = client.delete(url, headers=headers)
                else:
                    return {'status': 'failed', 'error': f'Unsupported method: {method}'}
            
            end_time = datetime.utcnow()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            try:
                response_data = response.json()
            except:
                response_data = response.text[:500] if response.text else ''
            
            return {
                'status': 'success',
                'http_status': response.status_code,
                'response': response_data,
                'duration_ms': duration_ms,
            }
        except httpx.TimeoutException:
            return {'status': 'failed', 'error': f'Request timed out after {timeout} seconds'}
        except httpx.ConnectError as e:
            return {'status': 'failed', 'error': f'Connection error: {str(e)}'}
    
    @staticmethod
    def _code(node_data, context, config):
        language = config.get('language', 'javascript')
        code = config.get('code', '')
        
        # For security, we don't execute arbitrary code
        # Instead, we return the code for manual review
        return {
            'status': 'skipped',
            'reason': 'Code execution not enabled for security',
            'language': language,
            'code_length': len(code),
        }
    
    @staticmethod
    def _wait_until(node_data, context, config):
        timestamp_field = config.get('timestamp_field', '')
        timeout_hours = int(config.get('timeout_hours', 72))
        
        timestamp_value = ActionHandler._resolve_path(timestamp_field, context)
        
        return {
            'status': 'queued',
            'wait_until': timestamp_value,
            'timeout_hours': timeout_hours,
        }
    
    @staticmethod
    def _set_node(node_data, context, config):
        field_name = config.get('field_name', '')
        field_value = ActionHandler._resolve_template(config.get('field_value', ''), context)
        
        if not field_name:
            return {'status': 'skipped', 'reason': 'No field name specified'}
        
        context.setdefault('variables', {})
        context['variables'][field_name] = field_value
        
        return {
            'status': 'success',
            'field_name': field_name,
            'field_value': field_value,
        }
    
    @staticmethod
    def _ai_agent(node_data, context, config):
        provider = config.get('provider', 'minimax')
        model = config.get('model', 'MiniMax-M2.7')
        system_prompt = ActionHandler._resolve_template(config.get('system_prompt', ''), context)
        user_prompt = ActionHandler._resolve_template(config.get('user_prompt', ''), context)
        max_tokens = int(config.get('max_tokens', 2048))
        temperature = float(config.get('temperature', 0.7))
        output_variable = config.get('output_variable', 'ai_response')
        
        if not user_prompt:
            return {'status': 'skipped', 'reason': 'No user prompt specified'}
        
        # Get AI settings from config or environment
        import os
        api_key = config.get('api_key') or os.environ.get(f'{provider.upper()}_API_KEY', '')
        
        if not api_key:
            return {'status': 'failed', 'error': f'No API key configured for {provider}'}
        
        try:
            start_time = datetime.utcnow()
            
            messages = []
            if system_prompt:
                messages.append({'role': 'system', 'content': system_prompt})
            messages.append({'role': 'user', 'content': user_prompt})
            
            if provider == 'minimax':
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                }
                payload = {
                    'model': model,
                    'max_tokens': max_tokens,
                    'temperature': temperature,
                    'messages': messages
                }
                response = requests.post(
                    'https://api.minimax.io/v1/text/chatcompletion_v2',
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                response.raise_for_status()
                result = response.json()
                ai_response = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            elif provider == 'anthropic':
                headers = {
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json',
                }
                payload = {
                    'model': model,
                    'max_tokens': max_tokens,
                    'temperature': temperature,
                    'messages': messages
                }
                response = requests.post(
                    'https://api.anthropic.com/v1/messages',
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                response.raise_for_status()
                result = response.json()
                ai_response = result.get('content', [{}])[0].get('text', '') if result.get('content') else ''
            
            elif provider == 'gemini':
                headers = {
                    'Content-Type': 'application/json',
                }
                payload = {
                    'contents': [
                        {'role': 'user', 'parts': [{'text': user_prompt}]}
                    ],
                    'generationConfig': {
                        'maxOutputTokens': max_tokens,
                        'temperature': temperature,
                    }
                }
                response = requests.post(
                    f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}',
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                response.raise_for_status()
                result = response.json()
                ai_response = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
            
            elif provider == 'groq':
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                }
                payload = {
                    'model': model,
                    'messages': messages,
                    'max_tokens': max_tokens,
                    'temperature': temperature,
                }
                response = requests.post(
                    'https://api.groq.com/openai/v1/chat/completions',
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                response.raise_for_status()
                result = response.json()
                ai_response = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            else:
                return {'status': 'failed', 'error': f'Unsupported provider: {provider}'}
            
            end_time = datetime.utcnow()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            return {
                'status': 'success',
                'provider': provider,
                'model': model,
                'response': ai_response,
                'duration_ms': duration_ms,
                'output_variable': output_variable,
            }
        
        except requests.exceptions.Timeout:
            return {'status': 'failed', 'error': 'AI request timed out'}
        except requests.exceptions.RequestException as e:
            return {'status': 'failed', 'error': f'AI request failed: {str(e)}'}
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _delay(node_data, context, config):
        """Delay execution by N minutes/hours/days"""
        duration = int(config.get('duration', 1))
        unit = config.get('unit', 'hours')
        
        multiplier = {'minutes': 1, 'hours': 60, 'days': 1440}.get(unit, 60)
        total_minutes = duration * multiplier
        
        execute_after = (datetime.utcnow() + timedelta(minutes=total_minutes)).isoformat()
        
        return {
            'status': 'queued',
            'duration': duration,
            'unit': unit,
            'total_minutes': total_minutes,
            'execute_after': execute_after,
        }
    
    @staticmethod
    def _find_records(node_data, context, config):
        """Find CRM records matching a filter"""
        entity_type = config.get('entity_type', 'contact')
        filter_field = config.get('filter_field', '')
        filter_operator = config.get('filter_operator', 'equals')
        filter_value = ActionHandler._resolve_template(config.get('filter_value', ''), context)
        limit = int(config.get('limit', 10))
        output_variable = config.get('output_variable', 'found_records')
        workspace_id = context.get('workspace_id')
        
        if not filter_field:
            return {'status': 'skipped', 'reason': 'No filter_field specified'}
        
        try:
            from models import db
            
            if entity_type == 'contact':
                from models_crm import Contact
                query = Contact.query.filter_by(workspace_id=workspace_id)
                model_class = Contact
            elif entity_type == 'deal':
                from models_crm import Deal
                query = Deal.query.filter_by(workspace_id=workspace_id)
                model_class = Deal
            elif entity_type == 'task':
                from models_crm import Task
                query = Task.query.filter_by(workspace_id=workspace_id)
                model_class = Task
            else:
                return {'status': 'failed', 'error': f'Unsupported entity_type: {entity_type}'}
            
            # Apply filter
            if hasattr(model_class, filter_field):
                col = getattr(model_class, filter_field)
                if filter_operator == 'equals':
                    query = query.filter(col == filter_value)
                elif filter_operator == 'not_equals':
                    query = query.filter(col != filter_value)
                elif filter_operator == 'contains':
                    query = query.filter(col.ilike(f'%{filter_value}%'))
                elif filter_operator == 'greater_than':
                    query = query.filter(col > filter_value)
                elif filter_operator == 'less_than':
                    query = query.filter(col < filter_value)
                elif filter_operator == 'is_empty':
                    query = query.filter((col == None) | (col == ''))
            
            records = query.limit(limit).all()
            records_list = []
            for r in records:
                try:
                    records_list.append(r.to_dict())
                except Exception:
                    records_list.append({'id': getattr(r, 'id', None)})
            
            context.setdefault('variables', {})
            context['variables'][output_variable] = records_list
            
            return {
                'status': 'success',
                'entity_type': entity_type,
                'count': len(records_list),
                'records': records_list,
                'output_variable': output_variable,
            }
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _delete_record(node_data, context, config):
        """Delete a CRM record"""
        entity_type = config.get('entity_type', 'contact')
        entity_id_raw = ActionHandler._resolve_template(config.get('entity_id', ''), context)
        confirm = config.get('confirm', 'false')
        
        if confirm != 'true':
            return {'status': 'skipped', 'reason': 'Deletion not confirmed (set confirm=true)'}
        
        if not entity_id_raw:
            entity_id_raw = str(context.get('entity_id', ''))
        
        if not entity_id_raw:
            return {'status': 'skipped', 'reason': 'No entity_id specified'}
        
        try:
            entity_id = int(entity_id_raw)
        except (ValueError, TypeError):
            return {'status': 'failed', 'error': f'Invalid entity_id: {entity_id_raw}'}
        
        try:
            from models import db
            
            if entity_type == 'contact':
                from models_crm import Contact
                record = Contact.query.get(entity_id)
            elif entity_type == 'deal':
                from models_crm import Deal
                record = Deal.query.get(entity_id)
            elif entity_type == 'task':
                from models_crm import Task
                record = Task.query.get(entity_id)
            else:
                return {'status': 'failed', 'error': f'Unsupported entity_type: {entity_type}'}
            
            if not record:
                return {'status': 'failed', 'error': f'{entity_type} {entity_id} not found'}
            
            db.session.delete(record)
            db.session.commit()
            return {
                'status': 'success',
                'entity_type': entity_type,
                'entity_id': entity_id,
                'deleted': True,
            }
        except Exception as e:
            db.session.rollback()
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _call_workflow(node_data, context, config):
        """Call another workflow as a sub-workflow"""
        from models_crm import WorkflowAutomation
        from services.workflow_graph_runner import WorkflowGraphRunner
        
        workflow_id = config.get('workflow_id')
        if not workflow_id:
            return {'status': 'skipped', 'reason': 'No workflow_id specified'}
        
        try:
            sub_workflow = WorkflowAutomation.query.get(workflow_id)
            if not sub_workflow:
                return {'status': 'failed', 'error': f'Workflow {workflow_id} not found'}
            
            canvas_data = sub_workflow.canvas_data
            if not canvas_data:
                return {'status': 'skipped', 'reason': 'Sub-workflow has no canvas data'}
            
            # Pass current context to sub-workflow
            sub_context = {
                'entity': context.get('entity', {}),
                'entity_type': context.get('entity_type'),
                'entity_id': context.get('entity_id'),
                'workspace_id': context.get('workspace_id'),
                'variables': context.get('variables', {}),
                'parent_workflow_id': context.get('workflow_id'),
            }
            
            runner = WorkflowGraphRunner()
            result = runner.execute_graph(
                canvas_data=canvas_data,
                context=sub_context,
                dry_run=False,
            )
            
            # Merge sub-workflow variables back into parent context
            context.setdefault('variables', {})
            context['variables'].update(sub_context.get('variables', {}))
            
            return {
                'status': 'success',
                'sub_workflow_id': workflow_id,
                'sub_workflow_name': sub_workflow.name,
                'result': result,
            }
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}


# ═══════════════════════════════════════════════════════════════════
# Register all handlers
# ═══════════════════════════════════════════════════════════════════

# Trigger handlers
TRIGGER_TYPES = [
    'contact_created', 'contact_updated', 'contact_tag_added', 'contact_no_activity',
    'deal_created', 'deal_stage_changed', 'deal_won', 'deal_lost',
    'deal_amount_changed', 'deal_no_activity',
    'task_created', 'task_completed', 'deal_close_date_approaching',
    'segment_joined', 'segment_left',
    'manual', 'schedule', 'webhook_trigger',
]

for trigger_type in TRIGGER_TYPES:
    NodeHandlerRegistry.register(trigger_type)(TriggerHandler.handle)

# Condition handlers
CONDITION_TYPES = [
    'check_field', 'check_score', 'if', 'if_else', 'loop_over_items',
    'error_trigger', 'split_in_batches',
]

for condition_type in CONDITION_TYPES:
    NodeHandlerRegistry.register(condition_type)(ConditionHandler.handle)

# Action handlers
ACTION_TYPES = [
    'create_task', 'send_email', 'send_whatsapp', 'notify_owner',
    'update_deal_stage', 'update_deal_field', 'update_contact_field',
    'add_tag', 'remove_tag', 'assign_owner',
    'create_note', 'webhook', 'delay', 'wait', 'http_request',
    'find_records', 'delete_record',
    'code', 'wait_until', 'set_node', 'ai_agent', 'call_workflow',
]

for action_type in ACTION_TYPES:
    NodeHandlerRegistry.register(action_type)(ActionHandler.handle)
