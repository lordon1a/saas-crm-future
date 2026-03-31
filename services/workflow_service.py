"""
Workflow Automation Service
============================
Core engine for IF X happens → THEN do Y workflow automation.
Handles trigger evaluation, condition checking, and action execution.

Trigger Types:
- deal_stage_changed: Deal stage transitions
- deal_created: New deal created
- deal_won: Deal marked as won
- deal_lost: Deal marked as lost
- contact_created: New contact added

Action Types:
- create_task: Create a task linked to entity
- notify_owner: Send notification to entity owner
- update_deal_field: Update deal field value
- send_email: Send email via SMTP
- add_tag: Add tag to entity
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class WorkflowService:
    """
    Main workflow automation engine.
    All trigger events flow through trigger_event() method.
    """
    
    # Supported trigger types
    TRIGGER_TYPES = {
        'deal_stage_changed': 'Anlaşma aşaması değişti',
        'deal_created': 'Yeni anlaşma oluşturuldu',
        'deal_won': 'Anlaşma kazanıldı',
        'deal_lost': 'Anlaşma kaybedildi',
        'deal_amount_changed': 'Anlaşma tutarı değişti',
        'deal_no_activity': 'Anlaşmada X gündür aktivite yok',
        'contact_created': 'Yeni kişi eklendi',
        'contact_updated': 'Kişi güncellendi',
        'contact_tag_added': 'Etiket eklendi',
        'contact_no_activity': 'Kişiyle X gündür iletişim yok',
        'task_created': 'Görev oluşturuldu',
        'task_completed': 'Görev tamamlandı',
    }
    
    # Supported action types
    ACTION_TYPES = {
        'create_task': 'Görev oluştur',
        'notify_owner': 'Sahiplere bildirim gönder',
        'update_deal_field': 'Anlaşma alanını güncelle',
        'update_contact_field': 'Kişi alanını güncelle',
        'send_email': 'Email gönder',
        'send_whatsapp': 'WhatsApp mesajı gönder',
        'add_tag': 'Etiket ekle',
        'remove_tag': 'Etiketi kaldır',
        'assign_owner': 'Sahip ata',
        'create_note': 'Not ekle',
        'notify_user': 'Kullanıcıya bildirim gönder',
        'webhook': 'Webhook gönder',
        'wait': 'Bekle',
    }
    
    @staticmethod
    def trigger_event(workspace_id: int, trigger_type: str, entity_type: str, 
                      entity_id: int, context: Dict = None) -> Dict:
        """
        Main entry point for all workflow triggers.
        Called from various places in the app when events occur.
        
        Args:
            workspace_id: The workspace context
            trigger_type: Type of trigger (e.g., 'deal_stage_changed')
            entity_type: Type of entity (deal, contact, task)
            entity_id: ID of the entity
            context: Additional context data (e.g., {'from_stage_id': 3, 'to_stage_id': 5})
        
        Returns:
            dict with status and results
        """
        from models_crm import WorkflowAutomation, WorkflowExecution
        
        context = context or {}
        results = {
            'trigger_type': trigger_type,
            'entity_type': entity_type,
            'entity_id': entity_id,
            'workflows_triggered': 0,
            'executions': []
        }
        
        try:
            # Find all active workflows matching this trigger type
            workflows = WorkflowAutomation.query.filter_by(
                workspace_id=workspace_id,
                trigger_type=trigger_type,
                is_active=True
            ).all()
            
            if not workflows:
                logger.debug(f"No active workflows for trigger {trigger_type} in workspace {workspace_id}")
                return results
            
            # Load the entity
            entity = WorkflowService._load_entity(entity_type, entity_id)
            if not entity:
                logger.warning(f"Entity not found: {entity_type}:{entity_id}")
                return {'error': 'Entity not found', **results}
            
            # Process each matching workflow
            for workflow in workflows:
                # Check if conditions are met
                if not WorkflowService.evaluate_conditions(workflow, entity, context):
                    logger.debug(f"Workflow {workflow.id} conditions not met, skipping")
                    continue
                
                # Execute the workflow
                execution_result = WorkflowService._execute_workflow(
                    workflow, entity, trigger_type, context
                )
                results['executions'].append(execution_result)
                results['workflows_triggered'] += 1
            
            return results
            
        except Exception as e:
            logger.error(f"Error in trigger_event: {e}", exc_info=True)
            return {'error': str(e), **results}
    
    @staticmethod
    def _load_entity(entity_type: str, entity_id: int):
        """Load an entity by type and ID"""
        from models_crm import Deal, Contact, Task
        
        if entity_type == 'deal':
            return Deal.query.get(entity_id)
        elif entity_type == 'contact':
            return Contact.query.get(entity_id)
        elif entity_type == 'task':
            return Task.query.get(entity_id)
        return None
    
    @staticmethod
    def evaluate_conditions(workflow, entity, context: Dict) -> bool:
        """
        Evaluate all conditions for a workflow against an entity.
        Supports AND/OR logic.
        
        Args:
            workflow: WorkflowAutomation instance
            entity: The entity to evaluate against
            context: Additional context from trigger
        
        Returns:
            bool: True if conditions are met (or no conditions defined)
        """
        from models_crm import WorkflowCondition
        
        conditions = WorkflowCondition.query.filter_by(
            workflow_id=workflow.id
        ).order_by(WorkflowCondition.order_index).all()
        
        if not conditions:
            return True  # No conditions = always execute
        
        condition_logic = workflow.condition_logic or 'AND'
        results = []
        
        for condition in conditions:
            result = WorkflowService._evaluate_single_condition(condition, entity, context)
            results.append(result)
        
        if condition_logic == 'AND':
            return all(results)
        else:  # OR
            return any(results)
    
    @staticmethod
    def _evaluate_single_condition(condition, entity, context: Dict) -> bool:
        """
        Evaluate a single condition against an entity.
        
        Operators: equals, not_equals, greater_than, less_than, contains,
                   is_empty, is_not_empty, changed_to
        """
        try:
            field_name = condition.field_name
            operator = condition.operator
            value = condition.value
            
            # Get the actual field value from entity
            field_value = WorkflowService._get_field_value(entity, field_name, context)
            
            # Handle null/None values
            if field_value is None:
                if operator == 'is_empty':
                    return True
                elif operator == 'is_not_empty':
                    return False
                return False
            
            # Evaluate based on operator
            if operator == 'equals':
                return str(field_value).lower() == str(value).lower()
            
            elif operator == 'not_equals':
                return str(field_value).lower() != str(value).lower()
            
            elif operator == 'greater_than':
                try:
                    return float(field_value) > float(value)
                except (ValueError, TypeError):
                    return False
            
            elif operator == 'less_than':
                try:
                    return float(field_value) < float(value)
                except (ValueError, TypeError):
                    return False
            
            elif operator == 'greater_than_or_equals':
                try:
                    return float(field_value) >= float(value)
                except (ValueError, TypeError):
                    return False
            
            elif operator == 'less_than_or_equals':
                try:
                    return float(field_value) <= float(value)
                except (ValueError, TypeError):
                    return False
            
            elif operator == 'contains':
                return str(value).lower() in str(field_value).lower()
            
            elif operator == 'not_contains':
                return str(value).lower() not in str(field_value).lower()
            
            elif operator == 'starts_with':
                return str(field_value).lower().startswith(str(value).lower())
            
            elif operator == 'ends_with':
                return str(field_value).lower().endswith(str(value).lower())
            
            elif operator == 'is_empty':
                return field_value == '' or field_value is None
            
            elif operator == 'is_not_empty':
                return field_value != '' and field_value is not None
            
            elif operator == 'changed_to':
                return str(field_value).lower() == str(value).lower()
            
            else:
                logger.warning(f"Unknown operator: {operator}")
                return False
                
        except Exception as e:
            logger.error(f"Error evaluating condition: {e}")
            return False
    
    @staticmethod
    def _get_field_value(entity, field_name: str, context: Dict):
        """
        Get a field value from an entity, supporting dot notation.
        Examples: 'deal_amount', 'contact.lead_score', 'stage.name'
        """
        # Handle context values (from trigger)
        if field_name.startswith('context.'):
            return context.get(field_name.replace('context.', ''))
        
        # Handle simple fields
        if '.' not in field_name:
            return getattr(entity, field_name, None)
        
        # Handle related fields (e.g., 'contact.email')
        parts = field_name.split('.')
        current = entity
        
        for part in parts:
            if current is None:
                return None
            if hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
        
        return current
    
    @staticmethod
    def _execute_workflow(workflow, entity, trigger_type: str, context: Dict) -> Dict:
        """
        Execute a workflow: queue actions and update statistics.
        """
        from models_crm import WorkflowAction, WorkflowExecution
        from models import db
        
        execution_result = {
            'workflow_id': workflow.id,
            'status': 'completed',
            'actions_executed': []
        }
        
        try:
            # Create execution log
            execution = WorkflowExecution(
                workflow_id=workflow.id,
                workspace_id=workflow.workspace_id,
                entity_type=entity.__class__.__name__.lower(),
                entity_id=entity.id,
                status='running',
                triggered_by=trigger_type,
                started_at=datetime.utcnow()
            )
            db.session.add(execution)
            db.session.flush()  # Get the ID
            
            # Get actions in order
            actions = WorkflowAction.query.filter_by(
                workflow_id=workflow.id
            ).order_by(WorkflowAction.order_index).all()
            
            # Process each action
            for action in actions:
                if action.delay_minutes > 0:
                    # Queue delayed action
                    WorkflowService._queue_delayed_action(action, entity, context)
                    execution_result['actions_executed'].append({
                        'action_id': action.id,
                        'type': action.action_type,
                        'status': 'queued',
                        'delay_minutes': action.delay_minutes
                    })
                else:
                    # Execute immediately
                    result = WorkflowService.execute_action(action, entity, context)
                    execution_result['actions_executed'].append({
                        'action_id': action.id,
                        'type': action.action_type,
                        'status': result.get('status'),
                        'result': result
                    })
            
            # Update workflow statistics
            workflow.run_count += 1
            workflow.last_run_at = datetime.utcnow()
            
            # Mark execution as completed
            execution.status = 'completed'
            execution.completed_at = datetime.utcnow()
            execution.actions_executed = json.dumps(execution_result['actions_executed'])
            
            db.session.commit()
            
            execution_result['status'] = 'completed'
            logger.info(f"Workflow {workflow.id} executed successfully for {entity.__class__.__name__}:{entity.id}")
            
        except Exception as e:
            logger.error(f"Error executing workflow {workflow.id}: {e}", exc_info=True)
            execution_result['status'] = 'failed'
            execution_result['error'] = str(e)
            
            # Update execution with error
            try:
                execution.status = 'failed'
                execution.error_message = str(e)
                execution.completed_at = datetime.utcnow()
                db.session.commit()
            except:
                db.session.rollback()
        
        return execution_result
    
    @staticmethod
    def execute_action(action, entity, context: Dict) -> Dict:
        """
        Execute a single workflow action.
        Returns dict with status and result/error.
        """
        action_type = action.action_type
        
        try:
            if action_type == 'create_task':
                return WorkflowService._action_create_task(action, entity, context)
            
            elif action_type == 'notify_owner':
                return WorkflowService._action_notify_owner(action, entity, context)
            
            elif action_type == 'update_deal_field':
                return WorkflowService._action_update_deal_field(action, entity, context)
            
            elif action_type == 'send_email':
                return WorkflowService._action_send_email(action, entity, context)
            
            elif action_type == 'add_tag':
                return WorkflowService._action_add_tag(action, entity, context)
            
            elif action_type == 'remove_tag':
                return WorkflowService._action_remove_tag(action, entity, context)
            
            elif action_type == 'notify_user':
                return WorkflowService._action_notify_user(action, entity, context)
            
            elif action_type == 'update_contact_field':
                return WorkflowService._action_update_contact_field(action, entity, context)
            
            elif action_type == 'update_deal_stage':
                return WorkflowService._action_update_deal_stage(action, entity, context)
            
            elif action_type == 'create_note':
                return WorkflowService._action_create_note(action, entity, context)
            
            elif action_type == 'http_request':
                return WorkflowService._action_http_request(action, entity, context)
            
            else:
                logger.warning(f"Unknown action type: {action_type}")
                return {'status': 'skipped', 'reason': f'Unknown action type: {action_type}'}
                
        except Exception as e:
            logger.error(f"Error executing action {action_type}: {e}", exc_info=True)
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _action_create_task(action, entity, context: Dict) -> Dict:
        """Create a task linked to the entity"""
        from models_crm import Task
        from models import db
        
        config = json.loads(action.action_config) if action.action_config else {}
        
        # Resolve template variables
        title = WorkflowService.resolve_template(config.get('title', 'Workflow Task'), entity, context)
        description = WorkflowService.resolve_template(config.get('description', ''), entity, context)
        
        # Determine assignment
        assign_to = config.get('assign_to', 'owner')
        assigned_to = None
        
        if assign_to == 'owner' and hasattr(entity, 'assigned_to'):
            assigned_to = entity.assigned_to
        elif assign_to == 'created_by' and hasattr(entity, 'created_by'):
            assigned_to = entity.created_by
        elif isinstance(assign_to, int):
            assigned_to = assign_to
        
        # Calculate due date
        due_in_days = config.get('due_in_days', 2)
        due_date = datetime.utcnow() + timedelta(days=due_in_days)
        
        # Determine priority
        priority = config.get('priority', 'medium')
        
        # Create the task
        task = Task(
            workspace_id=entity.workspace_id if hasattr(entity, 'workspace_id') else action.workspace_id,
            title=title,
            description=description,
            due_date=due_date,
            priority=priority,
            assignee_id=assigned_to,
            status='pending'
        )
        
        # Link to entity
        if hasattr(entity, 'id'):
            if entity.__class__.__name__ == 'Deal':
                task.deal_id = entity.id
            elif entity.__class__.__name__ == 'Contact':
                task.contact_id = entity.id
        
        db.session.add(task)
        db.session.commit()
        
        logger.info(f"Created task '{title}' for {entity.__class__.__name__}:{entity.id}")
        
        return {
            'status': 'success',
            'task_id': task.id,
            'title': title
        }
    
    @staticmethod
    def _action_notify_owner(action, entity, context: Dict) -> Dict:
        """Send notification to entity owner"""
        from services.notification_service import NotificationService
        
        config = json.loads(action.action_config) if action.action_config else {}
        message = WorkflowService.resolve_template(
            config.get('message', f'{entity.__class__.__name__} requires attention'),
            entity, context
        )
        
        # Get owner
        owner_id = None
        if hasattr(entity, 'assigned_to'):
            owner_id = entity.assigned_to
        elif hasattr(entity, 'created_by'):
            owner_id = entity.created_by
        
        if not owner_id:
            return {'status': 'skipped', 'reason': 'No owner found'}
        
        # Send notification
        try:
            NotificationService.create_notification(
                workspace_id=entity.workspace_id if hasattr(entity, 'workspace_id') else action.workspace_id,
                user_id=owner_id,
                notification_type='workflow_alert',
                title=config.get('title', 'Workflow Alert'),
                message=message,
                link=context.get('entity_link', f'/{entity.__class__.__name__.lower()}s/{entity.id}')
            )
            
            return {'status': 'success', 'owner_id': owner_id}
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _action_notify_user(action, entity, context: Dict) -> Dict:
        """Send notification to a specific user"""
        from services.notification_service import NotificationService
        
        config = json.loads(action.action_config) if action.action_config else {}
        
        user_id = config.get('user_id')
        if not user_id:
            return {'status': 'skipped', 'reason': 'No user_id specified'}
        
        message = WorkflowService.resolve_template(
            config.get('message', f'{entity.__class__.__name__} alert'),
            entity, context
        )
        
        try:
            NotificationService.create_notification(
                workspace_id=entity.workspace_id if hasattr(entity, 'workspace_id') else action.workspace_id,
                user_id=user_id,
                notification_type='workflow_alert',
                title=config.get('title', 'Workflow Alert'),
                message=message,
                link=context.get('entity_link', f'/{entity.__class__.__name__.lower()}s/{entity.id}')
            )
            
            return {'status': 'success', 'user_id': user_id}
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _action_update_deal_field(action, entity, context: Dict) -> Dict:
        """Update a field on a deal"""
        from models_crm import Deal
        from models import db
        
        if entity.__class__.__name__ != 'Deal':
            return {'status': 'skipped', 'reason': 'Entity is not a deal'}
        
        config = json.loads(action.action_config) if action.action_config else {}
        
        field = config.get('field')
        if not field:
            return {'status': 'skipped', 'reason': 'No field specified'}
        
        value = WorkflowService.resolve_template(str(config.get('value', '')), entity, context)
        
        # Handle special fields
        if field == 'stage_id':
            try:
                entity.stage_id = int(value)
            except ValueError:
                return {'status': 'failed', 'error': f'Invalid stage_id: {value}'}
        elif field == 'assigned_to':
            try:
                entity.assigned_to = int(value) if value else None
            except ValueError:
                return {'status': 'failed', 'error': f'Invalid assigned_to: {value}'}
        elif field == 'deal_value':
            try:
                entity.deal_value = float(value)
            except ValueError:
                return {'status': 'failed', 'error': f'Invalid deal_value: {value}'}
        elif field == 'name':
            entity.name = value
        elif field == 'notes':
            entity.notes = value
        else:
            # Dynamic field update
            if hasattr(entity, field):
                setattr(entity, field, value)
            else:
                return {'status': 'failed', 'error': f'Unknown field: {field}'}
        
        try:
            db.session.commit()
            logger.info(f"Updated deal {entity.id} field {field} = {value}")
            return {'status': 'success', 'field': field, 'value': value}
        except Exception as e:
            db.session.rollback()
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _action_send_email(action, entity, context: Dict) -> Dict:
        """Send an email using existing email service"""
        from services.email_hub_service import EmailHubService
        from models import User
        
        config = json.loads(action.action_config) if action.action_config else {}
        
        # Resolve templates
        to_email = WorkflowService.resolve_template(config.get('to', ''), entity, context)
        subject = WorkflowService.resolve_template(config.get('subject', ''), entity, context)
        body = WorkflowService.resolve_template(config.get('body', ''), entity, context)
        
        if not to_email or not subject:
            return {'status': 'skipped', 'reason': 'Missing to or subject'}
        
        # Get sender info
        sender_user_id = config.get('from_user_id')
        if sender_user_id:
            sender = User.query.get(sender_user_id)
        else:
            sender = User.query.get(action.created_by) if action.created_by else None
        
        try:
            # Use EmailHubService to send
            result = EmailHubService.send_workflow_email(
                workspace_id=action.workspace_id,
                to_email=to_email,
                subject=subject,
                body=body,
                from_name=sender.name if sender else None
            )
            
            if result.get('success'):
                return {'status': 'success', 'message_id': result.get('message_id')}
            else:
                return {'status': 'failed', 'error': result.get('error', 'Unknown error')}
                
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _action_add_tag(action, entity, context: Dict) -> Dict:
        """Add a tag to an entity"""
        from models import db
        
        config = json.loads(action.action_config) if action.action_config else {}
        tag = config.get('tag')
        
        if not tag:
            return {'status': 'skipped', 'reason': 'No tag specified'}
        
        # Add tag based on entity type
        if hasattr(entity, 'labels'):
            # Contact/Company
            current_labels = entity.labels or ''
            label_list = [l.strip() for l in current_labels.split(',') if l.strip()]
            
            if tag not in label_list:
                label_list.append(tag)
                entity.labels = ','.join(label_list)
                db.session.commit()
            
            return {'status': 'success', 'tag': tag}
        
        elif hasattr(entity, 'tags'):
            # Conversation or Deal
            current_tags = entity.tags or ''
            tag_list = [t.strip() for t in current_tags.split(',') if t.strip()]
            
            if tag not in tag_list:
                tag_list.append(tag)
                entity.tags = ','.join(tag_list)
                db.session.commit()
            
            return {'status': 'success', 'tag': tag}
        
        return {'status': 'skipped', 'reason': 'Entity does not support tags'}
    
    @staticmethod
    def _action_remove_tag(action, entity, context: Dict) -> Dict:
        """Remove a tag from an entity"""
        from models import db
        
        config = json.loads(action.action_config) if action.action_config else {}
        tag = config.get('tag')
        
        if not tag:
            return {'status': 'skipped', 'reason': 'No tag specified'}
        
        # Remove tag based on entity type
        if hasattr(entity, 'labels'):
            # Contact/Company
            current_labels = entity.labels or ''
            label_list = [l.strip() for l in current_labels.split(',') if l.strip()]
            
            if tag in label_list:
                label_list.remove(tag)
                entity.labels = ','.join(label_list)
                db.session.commit()
            
            return {'status': 'success', 'tag': tag}
        
        elif hasattr(entity, 'tags'):
            # Conversation or Deal
            current_tags = entity.tags or ''
            tag_list = [t.strip() for t in current_tags.split(',') if t.strip()]
            
            if tag in tag_list:
                tag_list.remove(tag)
                entity.tags = ','.join(tag_list)
                db.session.commit()
            
            return {'status': 'success', 'tag': tag}
        
        return {'status': 'skipped', 'reason': 'Entity does not support tags'}
    
    @staticmethod
    def _action_update_contact_field(action, entity, context: Dict) -> Dict:
        """Update a field on a contact"""
        from models_crm import Contact
        from models import db
        
        if entity.__class__.__name__ != 'Contact':
            return {'status': 'skipped', 'reason': 'Entity is not a contact'}
        
        config = json.loads(action.action_config) if action.action_config else {}
        
        field = config.get('field')
        if not field:
            return {'status': 'skipped', 'reason': 'No field specified'}
        
        value = WorkflowService.resolve_template(str(config.get('value', '')), entity, context)
        
        # Handle special fields
        if field == 'assigned_to':
            try:
                entity.assigned_to = int(value) if value else None
            except ValueError:
                return {'status': 'failed', 'error': f'Invalid assigned_to: {value}'}
        elif field == 'lead_score':
            try:
                entity.lead_score = int(value) if value else None
            except ValueError:
                return {'status': 'failed', 'error': f'Invalid lead_score: {value}'}
        elif field == 'job_title':
            entity.job_title = value
        elif field == 'role':
            entity.role = value
        elif field == 'phone':
            entity.phone = value
        elif field == 'notes':
            entity.notes = value
        else:
            # Dynamic field update
            if hasattr(entity, field):
                setattr(entity, field, value)
            else:
                return {'status': 'failed', 'error': f'Unknown field: {field}'}
        
        try:
            db.session.commit()
            logger.info(f"Updated contact {entity.id} field {field} = {value}")
            return {'status': 'success', 'field': field, 'value': value}
        except Exception as e:
            db.session.rollback()
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _action_update_deal_stage(action, entity, context: Dict) -> Dict:
        """Update the stage of a deal"""
        from models_crm import Deal
        from models import db
        
        if entity.__class__.__name__ != 'Deal':
            return {'status': 'skipped', 'reason': 'Entity is not a deal'}
        
        config = json.loads(action.action_config) if action.action_config else {}
        
        stage_id = config.get('stage_id')
        if not stage_id:
            return {'status': 'skipped', 'reason': 'No stage_id specified'}
        
        try:
            entity.stage_id = int(stage_id)
            db.session.commit()
            logger.info(f"Updated deal {entity.id} stage to {stage_id}")
            return {'status': 'success', 'stage_id': stage_id}
        except ValueError:
            return {'status': 'failed', 'error': f'Invalid stage_id: {stage_id}'}
        except Exception as e:
            db.session.rollback()
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _action_create_note(action, entity, context: Dict) -> Dict:
        """Create a note linked to the entity"""
        from models_crm import Note
        from models import db
        
        config = json.loads(action.action_config) if action.action_config else {}
        
        content = WorkflowService.resolve_template(
            config.get('content', ''),
            entity, context
        )
        
        if not content:
            return {'status': 'skipped', 'reason': 'No content specified'}
        
        # Determine the noteable type and ID
        noteable_type = entity.__class__.__name__
        noteable_id = entity.id
        
        # Create the note
        note = Note(
            workspace_id=entity.workspace_id if hasattr(entity, 'workspace_id') else action.workspace_id,
            content=content,
            noteable_type=noteable_type,
            noteable_id=noteable_id,
            created_by=action.created_by,
            is_private=config.get('is_private', False)
        )
        
        # Link to contact or deal if available
        if hasattr(entity, 'contact_id') and entity.contact_id:
            note.contact_id = entity.contact_id
        elif hasattr(entity, 'id') and entity.__class__.__name__ == 'Contact':
            note.contact_id = entity.id
        
        if hasattr(entity, 'deal_id') and entity.deal_id:
            note.deal_id = entity.deal_id
        elif hasattr(entity, 'id') and entity.__class__.__name__ == 'Deal':
            note.deal_id = entity.id
        
        try:
            db.session.add(note)
            db.session.commit()
            logger.info(f"Created note for {noteable_type}:{noteable_id}")
            return {'status': 'success', 'note_id': note.id}
        except Exception as e:
            db.session.rollback()
            return {'status': 'failed', 'error': str(e)}

    @staticmethod
    def _action_http_request(action, entity, context: Dict) -> Dict:
        """Execute an HTTP request"""
        import httpx
        import base64
        
        config = json.loads(action.action_config) if action.action_config else {}
        
        url = WorkflowService.resolve_template(config.get('url', ''), entity, context)
        method = config.get('method', 'GET').upper()
        auth_type = config.get('auth_type', 'none')
        header_key = config.get('header_key', '')
        header_value = WorkflowService.resolve_template(config.get('header_value', ''), entity, context)
        body = WorkflowService.resolve_template(config.get('body', ''), entity, context)
        timeout = config.get('timeout', 30)
        
        if not url:
            return {'status': 'skipped', 'reason': 'No URL specified'}
        
        headers = {}
        
        # Apply authentication
        if auth_type == 'bearer' and header_value:
            headers['Authorization'] = f'Bearer {header_value}'
        elif auth_type == 'basic' and header_value:
            encoded = base64.b64encode(header_value.encode()).decode()
            headers['Authorization'] = f'Basic {encoded}'
        elif auth_type == 'api_key' and header_key and header_value:
            headers[header_key] = header_value
        elif header_key and header_value:
            headers[header_key] = header_value
        
        # Set default content-type for body
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
            
            # Try to parse response as JSON
            try:
                response_data = response.json()
            except:
                response_data = response.text[:500] if response.text else ''
            
            logger.info(f"HTTP {method} {url} -> {response.status_code} ({duration_ms}ms)")
            
            return {
                'status': 'success',
                'http_status': response.status_code,
                'response': response_data,
                'duration_ms': duration_ms
            }
            
        except httpx.TimeoutException:
            logger.error(f"HTTP {method} {url} timed out after {timeout}s")
            return {'status': 'failed', 'error': f'Request timed out after {timeout} seconds'}
        except httpx.ConnectError as e:
            logger.error(f"HTTP {method} {url} connection error: {e}")
            return {'status': 'failed', 'error': f'Connection error: {str(e)}'}
        except Exception as e:
            logger.error(f"HTTP {method} {url} error: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _queue_delayed_action(action, entity, context: Dict):
        """Queue an action for delayed execution"""
        from models_crm import WorkflowExecutionQueue
        from models import db
        
        scheduled_at = datetime.utcnow() + timedelta(minutes=action.delay_minutes)
        
        queue_item = WorkflowExecutionQueue(
            workflow_id=action.workflow_id,
            workspace_id=action.workspace_id,
            entity_type=entity.__class__.__name__.lower(),
            entity_id=entity.id,
            action_id=action.id,
            scheduled_at=scheduled_at,
            status='pending'
        )
        
        db.session.add(queue_item)
        db.session.commit()
        
        logger.debug(f"Queued action {action.id} for execution at {scheduled_at}")
    
    @staticmethod
    def process_queue():
        """
        APScheduler job: Process pending delayed actions.
        Called every minute to execute queued actions whose time has come.
        """
        from models_crm import WorkflowExecutionQueue, WorkflowAction
        from models import db
        
        now = datetime.utcnow()
        
        # Find all pending items scheduled for now or earlier
        pending_items = WorkflowExecutionQueue.query.filter(
            WorkflowExecutionQueue.status == 'pending',
            WorkflowExecutionQueue.scheduled_at <= now
        ).limit(100).all()  # Process in batches
        
        processed = 0
        
        for item in pending_items:
            try:
                # Load the action
                action = WorkflowAction.query.get(item.action_id)
                if not action:
                    item.status = 'cancelled'
                    continue
                
                # Load the entity
                entity = WorkflowService._load_entity(item.entity_type, item.entity_id)
                if not entity:
                    item.status = 'cancelled'
                    continue
                
                # Execute the action
                result = WorkflowService.execute_action(action, entity, {})
                
                # Update queue item
                item.status = 'executed'
                item.executed_at = datetime.utcnow()
                
                processed += 1
                
            except Exception as e:
                logger.error(f"Error processing queued action {item.id}: {e}")
                item.status = 'cancelled'
        
        db.session.commit()
        
        if processed > 0:
            logger.info(f"Processed {processed} queued workflow actions")
        
        return processed
    
    @staticmethod
    def check_time_based_triggers():
        """
        APScheduler job: Check time-based triggers.
        Called daily at 00:05 to check for:
        - scheduled_daily workflows
        - contact_no_activity (X days, configurable)
        - deal_no_activity (X days, configurable)
        - deal_close_date_approaching (7 days before)
        """
        from models_crm import WorkflowAutomation, Contact, Deal
        from models import db
        from datetime import timedelta
        import json
        
        logger.info("Checking time-based workflow triggers...")
        
        today = datetime.utcnow().date()
        
        # Check contact_no_activity triggers
        no_activity_workflows = WorkflowAutomation.query.filter(
            WorkflowAutomation.trigger_type == 'contact_no_activity',
            WorkflowAutomation.is_active == True
        ).all()
        
        for workflow in no_activity_workflows:
            config = json.loads(workflow.trigger_config) if workflow.trigger_config else {}
            days = int(config.get('days', 30))
            min_score = int(config.get('min_lead_score', 0))
            
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Find contacts with no recent activity
            query = Contact.query.filter(
                Contact.workspace_id == workflow.workspace_id,
                db.or_(
                    Contact.last_activity_at <= cutoff_date,
                    Contact.last_activity_at == None
                )
            )
            
            if min_score > 0:
                query = query.filter(Contact.lead_score >= min_score)
            
            stale_contacts = query.limit(50).all()
            
            for contact in stale_contacts:
                # Prevent duplicate executions — check if already triggered 
                # for this contact within the last (days) period
                recent = WorkflowExecution.query.filter_by(
                    workflow_id=workflow.id,
                    entity_type='contact',
                    entity_id=contact.id,
                    status='completed'
                ).filter(
                    WorkflowExecution.started_at >= cutoff_date
                ).first()
                
                if recent:
                    continue  # Already triggered recently, skip
                
                try:
                    WorkflowService.trigger_event(
                        workspace_id=workflow.workspace_id,
                        trigger_type='contact_no_activity',
                        entity_type='contact',
                        entity_id=contact.id,
                        context={'days_inactive': days, 'cutoff_date': cutoff_date.isoformat()}
                    )
                except Exception as e:
                    logger.error(f"Error triggering contact_no_activity for contact {contact.id}: {e}")
        
        # Check deal_no_activity triggers
        deal_no_activity_workflows = WorkflowAutomation.query.filter(
            WorkflowAutomation.trigger_type == 'deal_no_activity',
            WorkflowAutomation.is_active == True
        ).all()
        
        for workflow in deal_no_activity_workflows:
            config = json.loads(workflow.trigger_config) if workflow.trigger_config else {}
            days = int(config.get('days', 30))
            min_value = int(config.get('min_deal_value', 0))
            
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Find deals with no recent activity (using updated_at field)
            query = Deal.query.filter(
                Deal.workspace_id == workflow.workspace_id,
                db.or_(
                    Deal.updated_at <= cutoff_date,
                    Deal.updated_at == None
                )
            )
            
            if min_value > 0:
                query = query.filter(Deal.value >= min_value)
            
            stale_deals = query.limit(50).all()
            
            for deal in stale_deals:
                # Prevent duplicate executions
                recent = WorkflowExecution.query.filter_by(
                    workflow_id=workflow.id,
                    entity_type='deal',
                    entity_id=deal.id,
                    status='completed'
                ).filter(
                    WorkflowExecution.started_at >= cutoff_date
                ).first()
                
                if recent:
                    continue  # Already triggered recently, skip
                
                try:
                    WorkflowService.trigger_event(
                        workspace_id=workflow.workspace_id,
                        trigger_type='deal_no_activity',
                        entity_type='deal',
                        entity_id=deal.id,
                        context={'days_inactive': days, 'cutoff_date': cutoff_date.isoformat()}
                    )
                except Exception as e:
                    logger.error(f"Error triggering deal_no_activity for deal {deal.id}: {e}")
        
        # Check deal_close_date_approaching triggers
        seven_days_from_now = datetime.utcnow() + timedelta(days=7)
        
        approaching_workflows = WorkflowAutomation.query.filter(
            WorkflowAutomation.trigger_type == 'deal_close_date_approaching',
            WorkflowAutomation.is_active == True
        ).all()
        
        for workflow in approaching_workflows:
            deals = Deal.query.filter(
                Deal.workspace_id == workflow.workspace_id,
                Deal.closedate != None,
                Deal.closedate <= seven_days_from_now,
                Deal.closedate >= datetime.utcnow()
            ).limit(50).all()
            
            for deal in deals:
                try:
                    days_until_close = (deal.closedate.date() - today).days
                    WorkflowService.trigger_event(
                        workspace_id=workflow.workspace_id,
                        trigger_type='deal_close_date_approaching',
                        entity_type='deal',
                        entity_id=deal.id,
                        context={'days_until_close': days_until_close}
                    )
                except Exception as e:
                    logger.error(f"Error triggering deal_close_date_approaching for {deal.id}: {e}")
        
        db.session.commit()
        logger.info("Time-based trigger check completed")
    
    @staticmethod
    def resolve_template(template_str: str, entity, context: Dict) -> str:
        """
        Resolve template variables in a string.
        Supports: {{contact.first_name}}, {{deal.name}}, {{context.days}}, etc.
        
        Example:
            "Merhaba {{contact.first_name}}" → "Merhaba Ahmet"
        """
        if not template_str:
            return ''
        
        result = template_str
        
        # Replace context variables
        for key, value in context.items():
            result = result.replace(f'{{{{context.{key}}}}}', str(value))
        
        # Replace entity field variables
        if entity:
            entity_dict = entity.to_dict() if hasattr(entity, 'to_dict') else {}
            
            # Handle nested fields (e.g., contact.email)
            if hasattr(entity, 'email'):
                result = result.replace('{{contact.email}}', str(entity.email or ''))
            if hasattr(entity, 'first_name'):
                result = result.replace('{{contact.first_name}}', str(entity.first_name or ''))
            if hasattr(entity, 'last_name'):
                result = result.replace('{{contact.last_name}}', str(entity.last_name or ''))
            if hasattr(entity, 'name'):
                result = result.replace('{{deal.name}}', str(entity.name or ''))
                result = result.replace('{{contact.name}}', str(entity.name or ''))
            if hasattr(entity, 'deal_value'):
                result = result.replace('{{deal.deal_value}}', str(entity.deal_value or ''))
            if hasattr(entity, 'stage_id'):
                result = result.replace('{{deal.stage_id}}', str(entity.stage_id or ''))
            
            # Generic replacement for any field in to_dict
            for field, value in entity_dict.items():
                placeholder = f'{{{{{entity.__class__.__name__.lower()}.{field}}}}}'
                result = result.replace(placeholder, str(value or ''))
        
        return result
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # BUILT-IN WORKFLOW TEMPLATES
    # ═══════════════════════════════════════════════════════════════════════════════
    
    WORKFLOW_TEMPLATES = [
        {
            'id': 'new_lead_welcome',
            'name': 'Yeni Lead Karşılama',
            'description': 'Yeni kişi eklendiğinde otomatik karşılama emaili gönder ve takip görevi oluştur',
            'icon': '🤝',
            'trigger': 'contact_created',
            'actions': ['send_email', 'create_task']
        },
        {
            'id': 'deal_won_celebration',
            'name': 'Anlaşma Kazanıldı',
            'description': 'Deal kazanılınca müşteriye teşekkür emaili gönder, onboarding görevi oluştur',
            'icon': '🏆',
            'trigger': 'deal_won',
            'actions': ['send_email', 'create_task', 'notify_owner']
        },
        {
            'id': 'stage_follow_up',
            'name': 'Teklif Sonrası Takip',
            'description': 'Deal aşama değişince belirli süre sonra takip emaili gönder',
            'icon': '📧',
            'trigger': 'deal_stage_changed',
            'actions': ['wait', 'send_email']
        },
    ]
