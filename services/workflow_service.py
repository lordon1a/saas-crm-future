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
        'deal_close_date_approaching': 'Anlaşma kapanış tarihi yaklaşıyor',
        'contact_created': 'Yeni kişi eklendi',
        'contact_updated': 'Kişi güncellendi',
        'form_submitted': 'Form gönderildi',
        'segment_joined': 'Kişi segmente eklendi',
        'segment_left': 'Kişi segmentten çıktı',
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
        'ai_agent': 'AI Agent',
    }
    
    @staticmethod
    def _check_enrollment_allowed(workflow, entity_type: str, entity_id: int) -> bool:
        """
        Check if an entity is allowed to be enrolled in a workflow based on
        the workflow's re_enrollment_mode setting.
        
        Args:
            workflow: WorkflowAutomation instance
            entity_type: Type of entity (deal, contact, task)
            entity_id: ID of the entity
            
        Returns:
            bool: True if enrollment is allowed, False otherwise
        """
        from models_crm import WorkflowEnrollment
        from datetime import datetime
        
        mode = workflow.re_enrollment_mode
        if mode == 'always':
            return True
        
        last = WorkflowEnrollment.query.filter_by(
            workflow_id=workflow.id, entity_id=entity_id, entity_type=entity_type
        ).order_by(WorkflowEnrollment.enrolled_at.desc()).first()
        
        if mode == 'never':
            return last is None
        if mode == 'once_per_day':
            return not last or (datetime.utcnow() - last.enrolled_at).days >= 1
        if mode == 'once_per_week':
            return not last or (datetime.utcnow() - last.enrolled_at).days >= 7
        
        # Default: allow enrollment
        return True
    
    @staticmethod
    def _create_enrollment_record(workflow_id: int, entity_type: str, entity_id: int, trigger_type: str):
        """
        Create a WorkflowEnrollment record to track that an entity was enrolled in a workflow.
        
        Args:
            workflow_id: ID of the workflow
            entity_type: Type of entity (deal, contact, task)
            entity_id: ID of the entity
            trigger_type: The trigger type that caused enrollment
        """
        from models_crm import WorkflowEnrollment, db
        from datetime import datetime
        
        try:
            enrollment = WorkflowEnrollment(
                workflow_id=workflow_id,
                entity_id=entity_id,
                entity_type=entity_type,
                enrolled_at=datetime.utcnow(),
                trigger_type=trigger_type
            )
            db.session.add(enrollment)
            db.session.commit()
            logger.debug(f"Created enrollment record for workflow {workflow_id}, entity {entity_type}:{entity_id}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating enrollment record: {e}", exc_info=True)
    
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
                # Legacy condition rows only apply to old-style workflows (no canvas_data)
                if not workflow.canvas_data and not WorkflowService.evaluate_conditions(workflow, entity, context):
                    logger.debug(f"Workflow {workflow.id} conditions not met, skipping")
                    continue

                # Check enrollment allowed based on re_enrollment_mode
                if not WorkflowService._check_enrollment_allowed(workflow, entity_type, entity_id):
                    logger.debug(f"Workflow {workflow.id} enrollment not allowed for {entity_type}:{entity_id}, skipping")
                    continue

                # Canvas-based workflows → use graph runner
                if workflow.canvas_data:
                    execution_result = WorkflowService._execute_graph_workflow(
                        workflow, entity, entity_type, entity_id, trigger_type, context
                    )
                else:
                    # Legacy action-row based execution
                    execution_result = WorkflowService._execute_workflow(
                        workflow, entity, trigger_type, context
                    )
                
                # Create enrollment record after successful execution
                WorkflowService._create_enrollment_record(
                    workflow.id, entity_type, entity_id, trigger_type
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
    def _execute_graph_workflow(workflow, entity, entity_type: str, entity_id: int,
                                trigger_type: str, context: Dict) -> Dict:
        """
        Execute a canvas-based (n8n-style) workflow using WorkflowGraphRunner.
        Called automatically when a CRM event fires and the workflow has canvas_data.
        """
        from services.workflow_graph_runner import WorkflowGraphRunner
        from models_crm import WorkflowExecution
        from models import db

        canvas_data = json.loads(workflow.canvas_data)

        # Serialize entity: prefer to_dict(), fall back to reading SQLAlchemy columns
        if hasattr(entity, 'to_dict'):
            try:
                entity_dict = entity.to_dict()
            except Exception:
                entity_dict = {}
        else:
            entity_dict = {}

        if not entity_dict and hasattr(entity, '__table__'):
            for col in entity.__table__.columns:
                val = getattr(entity, col.name, None)
                if hasattr(val, 'isoformat'):
                    val = val.isoformat()
                entity_dict[col.name] = val

        ctx = {
            'entity': entity_dict,
            'entity_type': entity_type,
            'entity_id': entity_id,
            'workspace_id': workflow.workspace_id,
            'variables': {},
            'trigger': {'type': trigger_type, **(context or {})},
            # Also expose entity under its type name so {{contact.x}}, {{deal.x}} work
            entity_type: entity_dict,
        }

        execution = None
        try:
            execution = WorkflowExecution(
                workflow_id=workflow.id,
                workspace_id=workflow.workspace_id,
                entity_type=entity_type,
                entity_id=entity_id,
                status='running',
                triggered_by=trigger_type,
                started_at=datetime.utcnow(),
            )
            db.session.add(execution)
            db.session.flush()
        except Exception as e:
            logger.error(f"Failed to create execution log for graph workflow {workflow.id}: {e}")

        runner = WorkflowGraphRunner()
        result = runner.execute_graph(canvas_data=canvas_data, context=ctx, dry_run=False)

        if execution:
            try:
                execution.status = result.get('status', 'completed')
                execution.completed_at = datetime.utcnow()
                execution.actions_executed = json.dumps(result.get('node_results', []))
                if result.get('error'):
                    execution.error_message = result['error']
                workflow.run_count = (workflow.run_count or 0) + 1
                workflow.last_run_at = datetime.utcnow()
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"Failed to update execution log for graph workflow {workflow.id}: {e}")

        logger.info(f"Graph workflow {workflow.id} executed for {entity_type}:{entity_id} — status={result.get('status')}")
        return result

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
            
            elif action_type == 'ai_agent':
                return WorkflowService._action_ai_agent(action, entity, context)
            
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
    
    @staticmethod
    def _action_ai_agent(action, entity, context: Dict) -> Dict:
        """Execute an AI Agent (MiniMax/LangChain style) request"""
        import requests
        
        config = json.loads(action.action_config) if action.action_config else {}
        
        # Get AI configuration
        provider = config.get('provider', 'minimax')
        model = config.get('model', 'MiniMax-M2.7')
        system_prompt = WorkflowService.resolve_template(config.get('system_prompt', ''), entity, context)
        user_prompt = WorkflowService.resolve_template(config.get('user_prompt', ''), entity, context)
        max_tokens = int(config.get('max_tokens', 2048))
        temperature = float(config.get('temperature', 0.7))
        output_variable = config.get('output_variable', 'ai_response')
        
        if not user_prompt:
            return {'status': 'skipped', 'reason': 'No user prompt specified'}
        
        # Get workspace AI settings
        workspace_id = action.workspace_id
        ai_settings = WorkflowService._get_workspace_ai_settings(workspace_id)
        
        if not ai_settings or not ai_settings.get(f'{provider}_key'):
            # Fall back to any available provider
            for p in ['minimax', 'anthropic', 'gemini', 'groq']:
                if ai_settings and ai_settings.get(f'{p}_key'):
                    provider = p
                    break
            else:
                return {'status': 'failed', 'error': 'No AI provider configured. Please set up AI API keys in workspace settings.'}
        
        api_key = ai_settings.get(f'{provider}_key')
        
        try:
            start_time = datetime.utcnow()
            
            # Build messages
            messages = []
            if system_prompt:
                messages.append({'role': 'system', 'content': system_prompt})
            messages.append({'role': 'user', 'content': user_prompt})
            
            # Call AI based on provider
            if provider == 'minimax':
                headers = {
                    'Authorization': f'Bearer {api_key}',
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
                    'https://api.minimax.io/anthropic/v1/messages',
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                response.raise_for_status()
                result = response.json()
                ai_response = result.get('content', [{}])[0].get('text', '') if result.get('content') else ''
                
            elif provider == 'anthropic':
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)
                response = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[{'role': 'user', 'content': user_prompt}]
                )
                ai_response = response.content[0].text
                
            elif provider == 'gemini':
                try:
                    from google import genai
                    client = genai.Client(api_key=api_key)
                    full_prompt = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
                    response = client.models.generate_content(model=model, contents=full_prompt)
                    ai_response = response.text
                except ImportError:
                    # Fallback to deprecated package
                    import google.generativeai as genai_deprecated
                    genai_deprecated.configure(api_key=api_key)
                    model_obj = genai_deprecated.GenerativeModel(model)
                    full_prompt = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
                    response = model_obj.generate_content(full_prompt)
                    ai_response = response.text
                
            elif provider == 'groq':
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'content-type': 'application/json',
                }
                payload = {
                    'model': model,
                    'messages': messages,
                    'temperature': temperature,
                    'max_tokens': max_tokens
                }
                response = requests.post(
                    'https://api.groq.com/openai/v1/chat/completions',
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                response.raise_for_status()
                result = response.json()
                ai_response = result['choices'][0]['message']['content']
            else:
                return {'status': 'failed', 'error': f'Unknown provider: {provider}'}
            
            end_time = datetime.utcnow()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            logger.info(f"AI Agent {provider}/{model} -> success ({duration_ms}ms)")
            
            # Store result in context for variable interpolation in subsequent nodes
            context[output_variable] = ai_response
            
            return {
                'status': 'success',
                'provider': provider,
                'model': model,
                'response': ai_response,
                'output_variable': output_variable,
                'duration_ms': duration_ms
            }
            
        except requests.exceptions.Timeout:
            logger.error(f"AI Agent {provider} request timed out")
            return {'status': 'failed', 'error': 'AI request timed out'}
        except requests.exceptions.HTTPError as e:
            logger.error(f"AI Agent {provider} HTTP error: {e}")
            return {'status': 'failed', 'error': f'AI HTTP error: {str(e)}'}
        except Exception as e:
            logger.error(f"AI Agent error: {e}", exc_info=True)
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def _get_workspace_ai_settings(workspace_id: int) -> Dict:
        """Get AI settings for a workspace"""
        from models_crm import AISetting
        from models import db
        
        settings = AISetting.query.filter_by(workspace_id=workspace_id).all()
        result = {}
        for s in settings:
            if s.provider and s.api_key:
                # API key is encrypted, need to decrypt
                try:
                    from routes.settings import _ai_decrypt
                    result[f'{s.provider}_key'] = _ai_decrypt(s.api_key)
                    result[f'{s.provider}_model'] = s.model_name
                except Exception:
                    pass
        return result
    
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
        import models_crm as crm_models
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
                recent = crm_models.WorkflowExecution.query.filter_by(
                    workflow_id=workflow.id,
                    entity_type='contact',
                    entity_id=contact.id,
                    status='completed'
                ).filter(
                    crm_models.WorkflowExecution.started_at >= cutoff_date
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
                recent = crm_models.WorkflowExecution.query.filter_by(
                    workflow_id=workflow.id,
                    entity_type='deal',
                    entity_id=deal.id,
                    status='completed'
                ).filter(
                    crm_models.WorkflowExecution.started_at >= cutoff_date
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
        # ── KİŞİ ──────────────────────────────────────────────────────────
        {
            'id': 'contact_created_task',
            'name': 'Yeni Kişi → Görev Oluştur',
            'description': 'Yeni kişi eklendiğinde otomatik takip görevi oluşturur.',
            'icon': '👤',
            'category': 'contact',
            'trigger': 'contact_created',
            'actions': ['create_task'],
            'canvas_data': {
                'nodes': [
                    {'id': 'trigger', 'type': 'workflowNode', 'position': {'x': 250, 'y': 80},
                     'data': {'nodeType': 'trigger', 'subtype': 'contact_created', 'isEmpty': False,
                              'label': 'Yeni Kişi Eklendi', 'config': {}}},
                    {'id': 'n1', 'type': 'workflowNode', 'position': {'x': 250, 'y': 220},
                     'data': {'nodeType': 'action', 'subtype': 'create_task', 'isEmpty': False,
                              'label': 'Görev Oluştur',
                              'config': {'title': '{{contact.first_name}} ile takip görüşmesi',
                                         'assign_to': 'contact_owner', 'due_in_days': 2,
                                         'priority': 'medium'}}},
                ],
                'edges': [{'id': 'e1', 'source': 'trigger', 'target': 'n1'}],
            },
        },
        {
            'id': 'contact_created_email',
            'name': 'Yeni Kişi → Karşılama E-postası',
            'description': 'Yeni kişi eklendiğinde otomatik karşılama e-postası gönderir.',
            'icon': '📨',
            'category': 'contact',
            'trigger': 'contact_created',
            'actions': ['send_email'],
            'canvas_data': {
                'nodes': [
                    {'id': 'trigger', 'type': 'workflowNode', 'position': {'x': 250, 'y': 80},
                     'data': {'nodeType': 'trigger', 'subtype': 'contact_created', 'isEmpty': False,
                              'label': 'Yeni Kişi Eklendi', 'config': {}}},
                    {'id': 'n1', 'type': 'workflowNode', 'position': {'x': 250, 'y': 220},
                     'data': {'nodeType': 'action', 'subtype': 'send_email', 'isEmpty': False,
                              'label': 'Karşılama E-postası Gönder',
                              'config': {'to': '{{contact.email}}',
                                         'subject': 'Hoş geldiniz, {{contact.first_name}}!',
                                         'body': 'Merhaba {{contact.first_name}},\n\nSizi sistemimizde görmekten mutluluk duyuyoruz. Size en kısa sürede ulaşacağız.\n\nSaygılarımızla'}}},
                ],
                'edges': [{'id': 'e1', 'source': 'trigger', 'target': 'n1'}],
            },
        },
        {
            'id': 'contact_created_welcome_full',
            'name': 'Yeni Kişi → E-posta + Görev',
            'description': 'Karşılama e-postası gönderir ve satış temsilcisine takip görevi oluşturur.',
            'icon': '🤝',
            'category': 'contact',
            'trigger': 'contact_created',
            'actions': ['send_email', 'create_task'],
            'canvas_data': {
                'nodes': [
                    {'id': 'trigger', 'type': 'workflowNode', 'position': {'x': 250, 'y': 80},
                     'data': {'nodeType': 'trigger', 'subtype': 'contact_created', 'isEmpty': False,
                              'label': 'Yeni Kişi Eklendi', 'config': {}}},
                    {'id': 'n1', 'type': 'workflowNode', 'position': {'x': 250, 'y': 220},
                     'data': {'nodeType': 'action', 'subtype': 'send_email', 'isEmpty': False,
                              'label': 'Karşılama E-postası',
                              'config': {'to': '{{contact.email}}',
                                         'subject': 'Hoş geldiniz!',
                                         'body': 'Merhaba {{contact.first_name}}, sisteme hoş geldiniz.'}}},
                    {'id': 'n2', 'type': 'workflowNode', 'position': {'x': 250, 'y': 360},
                     'data': {'nodeType': 'action', 'subtype': 'create_task', 'isEmpty': False,
                              'label': 'Takip Görevi',
                              'config': {'title': '{{contact.first_name}} ile ilk görüşme',
                                         'assign_to': 'contact_owner', 'due_in_days': 1,
                                         'priority': 'high'}}},
                ],
                'edges': [
                    {'id': 'e1', 'source': 'trigger', 'target': 'n1'},
                    {'id': 'e2', 'source': 'n1', 'target': 'n2'},
                ],
            },
        },
        {
            'id': 'contact_updated_notify',
            'name': 'Kişi Güncellenince Bildir',
            'description': 'Kişi bilgileri değiştiğinde sahibine bildirim gönderir.',
            'icon': '🔔',
            'category': 'contact',
            'trigger': 'contact_updated',
            'actions': ['notify_owner'],
            'canvas_data': {
                'nodes': [
                    {'id': 'trigger', 'type': 'workflowNode', 'position': {'x': 250, 'y': 80},
                     'data': {'nodeType': 'trigger', 'subtype': 'contact_updated', 'isEmpty': False,
                              'label': 'Kişi Güncellendi', 'config': {}}},
                    {'id': 'n1', 'type': 'workflowNode', 'position': {'x': 250, 'y': 220},
                     'data': {'nodeType': 'action', 'subtype': 'notify_owner', 'isEmpty': False,
                              'label': 'Sahibine Bildir',
                              'config': {'title': 'Kişi güncellendi',
                                         'message': '{{contact.first_name}} {{contact.last_name}} kişisinin bilgileri güncellendi.'}}},
                ],
                'edges': [{'id': 'e1', 'source': 'trigger', 'target': 'n1'}],
            },
        },
        {
            'id': 'contact_tag_whatsapp',
            'name': 'Etiket Eklenince WhatsApp',
            'description': 'Kişiye etiket eklendiğinde WhatsApp mesajı gönderir.',
            'icon': '💬',
            'category': 'contact',
            'trigger': 'contact_tag_added',
            'actions': ['send_whatsapp'],
            'canvas_data': {
                'nodes': [
                    {'id': 'trigger', 'type': 'workflowNode', 'position': {'x': 250, 'y': 80},
                     'data': {'nodeType': 'trigger', 'subtype': 'contact_tag_added', 'isEmpty': False,
                              'label': 'Etiket Eklendi', 'config': {}}},
                    {'id': 'n1', 'type': 'workflowNode', 'position': {'x': 250, 'y': 220},
                     'data': {'nodeType': 'action', 'subtype': 'send_whatsapp', 'isEmpty': False,
                              'label': 'WhatsApp Gönder',
                              'config': {'message': 'Merhaba {{contact.first_name}}, size özel teklifimiz için sizi arayabiliriz.'}}},
                ],
                'edges': [{'id': 'e1', 'source': 'trigger', 'target': 'n1'}],
            },
        },
        {
            'id': 'contact_no_activity_remind',
            'name': 'Uzun Süre İletişim Yok → Hatırlat',
            'description': 'Kişiyle uzun süre iletişim kurulmadığında sahibine görev ve bildirim gönderir.',
            'icon': '⏰',
            'category': 'contact',
            'trigger': 'contact_no_activity',
            'actions': ['create_task', 'notify_owner'],
            'canvas_data': {
                'nodes': [
                    {'id': 'trigger', 'type': 'workflowNode', 'position': {'x': 250, 'y': 80},
                     'data': {'nodeType': 'trigger', 'subtype': 'contact_no_activity', 'isEmpty': False,
                              'label': 'İletişim Yok', 'config': {}}},
                    {'id': 'n1', 'type': 'workflowNode', 'position': {'x': 250, 'y': 220},
                     'data': {'nodeType': 'action', 'subtype': 'create_task', 'isEmpty': False,
                              'label': 'Yeniden İletişim Görevi',
                              'config': {'title': '{{contact.first_name}} ile yeniden iletişime geç',
                                         'assign_to': 'contact_owner', 'due_in_days': 1,
                                         'priority': 'high'}}},
                    {'id': 'n2', 'type': 'workflowNode', 'position': {'x': 250, 'y': 360},
                     'data': {'nodeType': 'action', 'subtype': 'notify_owner', 'isEmpty': False,
                              'label': 'Sahibine Uyar',
                              'config': {'title': 'İnaktif kişi uyarısı',
                                         'message': '{{contact.first_name}} ile uzun süredir iletişim kurulmadı!'}}},
                ],
                'edges': [
                    {'id': 'e1', 'source': 'trigger', 'target': 'n1'},
                    {'id': 'e2', 'source': 'n1', 'target': 'n2'},
                ],
            },
        },
        # ── ANLAŞMA ────────────────────────────────────────────────────────
        {
            'id': 'deal_created_task',
            'name': 'Yeni Anlaşma → Görev Oluştur',
            'description': 'Yeni anlaşma oluşturulduğunda otomatik aksiyon görevi atar.',
            'icon': '💼',
            'category': 'deal',
            'trigger': 'deal_created',
            'actions': ['create_task'],
            'canvas_data': {
                'nodes': [
                    {'id': 'trigger', 'type': 'workflowNode', 'position': {'x': 250, 'y': 80},
                     'data': {'nodeType': 'trigger', 'subtype': 'deal_created', 'isEmpty': False,
                              'label': 'Yeni Anlaşma Oluşturuldu', 'config': {}}},
                    {'id': 'n1', 'type': 'workflowNode', 'position': {'x': 250, 'y': 220},
                     'data': {'nodeType': 'action', 'subtype': 'create_task', 'isEmpty': False,
                              'label': 'Keşif Görüşmesi Görevi',
                              'config': {'title': '{{entity.name}} — keşif görüşmesi planla',
                                         'assign_to': 'contact_owner', 'due_in_days': 1,
                                         'priority': 'high'}}},
                ],
                'edges': [{'id': 'e1', 'source': 'trigger', 'target': 'n1'}],
            },
        },
        {
            'id': 'deal_stage_email',
            'name': 'Aşama Değişti → Takip E-postası',
            'description': 'Deal aşaması değiştiğinde müşteriye bilgilendirme e-postası gönderir.',
            'icon': '📧',
            'category': 'deal',
            'trigger': 'deal_stage_changed',
            'actions': ['send_email'],
            'canvas_data': {
                'nodes': [
                    {'id': 'trigger', 'type': 'workflowNode', 'position': {'x': 250, 'y': 80},
                     'data': {'nodeType': 'trigger', 'subtype': 'deal_stage_changed', 'isEmpty': False,
                              'label': 'Aşama Değişti', 'config': {}}},
                    {'id': 'n1', 'type': 'workflowNode', 'position': {'x': 250, 'y': 220},
                     'data': {'nodeType': 'action', 'subtype': 'send_email', 'isEmpty': False,
                              'label': 'Durum Güncelleme E-postası',
                              'config': {'to': '{{contact.email}}',
                                         'subject': '{{entity.name}} sürecinizde güncelleme',
                                         'body': 'Sayın {{contact.first_name}},\n\nAnlaşmanız bir sonraki aşamaya taşındı. Detaylar için lütfen bizimle iletişime geçin.'}}},
                ],
                'edges': [{'id': 'e1', 'source': 'trigger', 'target': 'n1'}],
            },
        },
        {
            'id': 'deal_won_full',
            'name': 'Deal Kazanıldı → Teşekkür + Onboarding',
            'description': 'Anlaşma kazanılınca müşteriye teşekkür e-postası ve onboarding görevi oluşturur.',
            'icon': '🏆',
            'category': 'deal',
            'trigger': 'deal_won',
            'actions': ['send_email', 'create_task', 'notify_owner'],
            'canvas_data': {
                'nodes': [
                    {'id': 'trigger', 'type': 'workflowNode', 'position': {'x': 250, 'y': 80},
                     'data': {'nodeType': 'trigger', 'subtype': 'deal_won', 'isEmpty': False,
                              'label': 'Anlaşma Kazanıldı', 'config': {}}},
                    {'id': 'n1', 'type': 'workflowNode', 'position': {'x': 250, 'y': 220},
                     'data': {'nodeType': 'action', 'subtype': 'send_email', 'isEmpty': False,
                              'label': 'Teşekkür E-postası',
                              'config': {'to': '{{contact.email}}',
                                         'subject': 'Hoş geldiniz! {{entity.name}}',
                                         'body': 'Sayın {{contact.first_name}},\n\nAnlaşmamız tamamlandı! Onboarding süreci için ekibimiz yakında sizinle iletişime geçecek.'}}},
                    {'id': 'n2', 'type': 'workflowNode', 'position': {'x': 250, 'y': 360},
                     'data': {'nodeType': 'action', 'subtype': 'create_task', 'isEmpty': False,
                              'label': 'Onboarding Görevi',
                              'config': {'title': '{{entity.name}} — onboarding başlat',
                                         'assign_to': 'contact_owner', 'due_in_days': 3,
                                         'priority': 'high'}}},
                    {'id': 'n3', 'type': 'workflowNode', 'position': {'x': 250, 'y': 500},
                     'data': {'nodeType': 'action', 'subtype': 'notify_owner', 'isEmpty': False,
                              'label': 'Ekibe Bildir',
                              'config': {'title': 'Deal kazanıldı!',
                                         'message': '{{entity.name}} anlaşması kazanıldı. Onboarding başlatıldı.'}}},
                ],
                'edges': [
                    {'id': 'e1', 'source': 'trigger', 'target': 'n1'},
                    {'id': 'e2', 'source': 'n1', 'target': 'n2'},
                    {'id': 'e3', 'source': 'n2', 'target': 'n3'},
                ],
            },
        },
        {
            'id': 'deal_lost_note',
            'name': 'Deal Kaybedildi → Not + Bildirim',
            'description': 'Anlaşma kaybedilince nedenini not olarak kaydeder ve ekibe bildirir.',
            'icon': '📝',
            'category': 'deal',
            'trigger': 'deal_lost',
            'actions': ['create_note', 'notify_owner'],
            'canvas_data': {
                'nodes': [
                    {'id': 'trigger', 'type': 'workflowNode', 'position': {'x': 250, 'y': 80},
                     'data': {'nodeType': 'trigger', 'subtype': 'deal_lost', 'isEmpty': False,
                              'label': 'Anlaşma Kaybedildi', 'config': {}}},
                    {'id': 'n1', 'type': 'workflowNode', 'position': {'x': 250, 'y': 220},
                     'data': {'nodeType': 'action', 'subtype': 'create_note', 'isEmpty': False,
                              'label': 'Kaybetme Notu',
                              'config': {'content': '{{entity.name}} anlaşması kaybedildi. İnceleme yapılmalı.',
                                         'is_private': False}}},
                    {'id': 'n2', 'type': 'workflowNode', 'position': {'x': 250, 'y': 360},
                     'data': {'nodeType': 'action', 'subtype': 'notify_owner', 'isEmpty': False,
                              'label': 'Ekibe Bildir',
                              'config': {'title': 'Deal kaybedildi',
                                         'message': '{{entity.name}} anlaşması kaybedildi. Sebep analizi yapılsın.'}}},
                ],
                'edges': [
                    {'id': 'e1', 'source': 'trigger', 'target': 'n1'},
                    {'id': 'e2', 'source': 'n1', 'target': 'n2'},
                ],
            },
        },
        {
            'id': 'deal_close_approaching',
            'name': 'Kapanış Tarihi Yaklaşıyor → Uyar',
            'description': 'Deal kapanış tarihi yaklaşınca sahibini uyarır ve acil görev oluşturur.',
            'icon': '⚡',
            'category': 'deal',
            'trigger': 'deal_close_date_approaching',
            'actions': ['notify_owner', 'create_task'],
            'canvas_data': {
                'nodes': [
                    {'id': 'trigger', 'type': 'workflowNode', 'position': {'x': 250, 'y': 80},
                     'data': {'nodeType': 'trigger', 'subtype': 'deal_close_date_approaching', 'isEmpty': False,
                              'label': 'Kapanış Tarihi Yaklaşıyor', 'config': {}}},
                    {'id': 'n1', 'type': 'workflowNode', 'position': {'x': 250, 'y': 220},
                     'data': {'nodeType': 'action', 'subtype': 'notify_owner', 'isEmpty': False,
                              'label': 'Acil Uyarı',
                              'config': {'title': 'Kapanış tarihi yaklaşıyor!',
                                         'message': '{{entity.name}} anlaşmasının kapanış tarihi yaklaşıyor. Hemen aksiyon alın!'}}},
                    {'id': 'n2', 'type': 'workflowNode', 'position': {'x': 250, 'y': 360},
                     'data': {'nodeType': 'action', 'subtype': 'create_task', 'isEmpty': False,
                              'label': 'Acil Takip Görevi',
                              'config': {'title': '{{entity.name}} — kapanış aksiyonu',
                                         'assign_to': 'contact_owner', 'due_in_days': 0,
                                         'priority': 'high'}}},
                ],
                'edges': [
                    {'id': 'e1', 'source': 'trigger', 'target': 'n1'},
                    {'id': 'e2', 'source': 'n1', 'target': 'n2'},
                ],
            },
        },
        # ── GÖREV ──────────────────────────────────────────────────────────
        {
            'id': 'task_created_notify',
            'name': 'Görev Oluşunca Sahibine Bildir',
            'description': 'Yeni görev oluşturulduğunda atanan kişiye bildirim gönderir.',
            'icon': '✅',
            'category': 'task',
            'trigger': 'task_created',
            'actions': ['notify_owner'],
            'canvas_data': {
                'nodes': [
                    {'id': 'trigger', 'type': 'workflowNode', 'position': {'x': 250, 'y': 80},
                     'data': {'nodeType': 'trigger', 'subtype': 'task_created', 'isEmpty': False,
                              'label': 'Yeni Görev Oluşturuldu', 'config': {}}},
                    {'id': 'n1', 'type': 'workflowNode', 'position': {'x': 250, 'y': 220},
                     'data': {'nodeType': 'action', 'subtype': 'notify_owner', 'isEmpty': False,
                              'label': 'Atanan Kişiye Bildir',
                              'config': {'title': 'Yeni görev atandı',
                                         'message': 'Size yeni bir görev atandı: {{entity.title}}'}}},
                ],
                'edges': [{'id': 'e1', 'source': 'trigger', 'target': 'n1'}],
            },
        },
        {
            'id': 'task_completed_whatsapp',
            'name': 'Görev Tamamlanınca Müşteriye WhatsApp',
            'description': 'Görev tamamlandığında ilgili müşteriye WhatsApp bildirimi gönderir.',
            'icon': '🎯',
            'category': 'task',
            'trigger': 'task_completed',
            'actions': ['send_whatsapp'],
            'canvas_data': {
                'nodes': [
                    {'id': 'trigger', 'type': 'workflowNode', 'position': {'x': 250, 'y': 80},
                     'data': {'nodeType': 'trigger', 'subtype': 'task_completed', 'isEmpty': False,
                              'label': 'Görev Tamamlandı', 'config': {}}},
                    {'id': 'n1', 'type': 'workflowNode', 'position': {'x': 250, 'y': 220},
                     'data': {'nodeType': 'action', 'subtype': 'send_whatsapp', 'isEmpty': False,
                              'label': 'WhatsApp Gönder',
                              'config': {'message': 'Merhaba! Talebinizle ilgili işlem tamamlandı. Başka bir konuda yardımcı olabilir miyiz?'}}},
                ],
                'edges': [{'id': 'e1', 'source': 'trigger', 'target': 'n1'}],
            },
        },
        # ── GELİŞMİŞ ───────────────────────────────────────────────────────
        {
            'id': 'contact_ai_tag',
            'name': 'Yeni Kişi → AI Analizi → Etiketle',
            'description': 'Yeni kişiyi AI ile analiz eder, uygun etiket ekler ve not oluşturur.',
            'icon': '🤖',
            'category': 'advanced',
            'trigger': 'contact_created',
            'actions': ['ai_agent', 'add_tag', 'create_note'],
            'canvas_data': {
                'nodes': [
                    {'id': 'trigger', 'type': 'workflowNode', 'position': {'x': 250, 'y': 80},
                     'data': {'nodeType': 'trigger', 'subtype': 'contact_created', 'isEmpty': False,
                              'label': 'Yeni Kişi Eklendi', 'config': {}}},
                    {'id': 'n1', 'type': 'workflowNode', 'position': {'x': 250, 'y': 220},
                     'data': {'nodeType': 'action', 'subtype': 'ai_agent', 'isEmpty': False,
                              'label': 'AI Analizi',
                              'config': {'provider': 'minimax', 'model': 'MiniMax-M2.7',
                                         'system_prompt': 'Sen bir CRM asistanısın. Kişi bilgilerini analiz et.',
                                         'user_prompt': 'Şu kişiyi analiz et: {{contact.first_name}} {{contact.last_name}}, email: {{contact.email}}. Kısa bir özet yaz.',
                                         'max_tokens': 256, 'temperature': 0.5,
                                         'output_variable': 'ai_summary'}}},
                    {'id': 'n2', 'type': 'workflowNode', 'position': {'x': 250, 'y': 360},
                     'data': {'nodeType': 'action', 'subtype': 'add_tag', 'isEmpty': False,
                              'label': 'Etiket Ekle',
                              'config': {'tag_name': 'ai-incelendi'}}},
                    {'id': 'n3', 'type': 'workflowNode', 'position': {'x': 250, 'y': 500},
                     'data': {'nodeType': 'action', 'subtype': 'create_note', 'isEmpty': False,
                              'label': 'AI Notu Oluştur',
                              'config': {'content': 'AI Analizi: {{variables.ai_summary}}',
                                         'is_private': True}}},
                ],
                'edges': [
                    {'id': 'e1', 'source': 'trigger', 'target': 'n1'},
                    {'id': 'e2', 'source': 'n1', 'target': 'n2'},
                    {'id': 'e3', 'source': 'n2', 'target': 'n3'},
                ],
            },
        },
        {
            'id': 'webhook_task_email',
            'name': 'Webhook → Görev + E-posta',
            'description': 'Dış sistemden webhook geldiğinde görev oluşturur ve bilgilendirme e-postası gönderir.',
            'icon': '�',
            'category': 'advanced',
            'trigger': 'webhook_trigger',
            'actions': ['create_task', 'send_email'],
            'canvas_data': {
                'nodes': [
                    {'id': 'trigger', 'type': 'workflowNode', 'position': {'x': 250, 'y': 80},
                     'data': {'nodeType': 'trigger', 'subtype': 'webhook_trigger', 'isEmpty': False,
                              'label': 'Webhook Alındı', 'config': {}}},
                    {'id': 'n1', 'type': 'workflowNode', 'position': {'x': 250, 'y': 220},
                     'data': {'nodeType': 'action', 'subtype': 'create_task', 'isEmpty': False,
                              'label': 'Görev Oluştur',
                              'config': {'title': 'Webhook: aksiyon gerekli',
                                         'assign_to': 'contact_owner', 'due_in_days': 1,
                                         'priority': 'high'}}},
                    {'id': 'n2', 'type': 'workflowNode', 'position': {'x': 250, 'y': 360},
                     'data': {'nodeType': 'action', 'subtype': 'notify_owner', 'isEmpty': False,
                              'label': 'Ekibe Bildir',
                              'config': {'title': 'Webhook tetiklendi',
                                         'message': 'Dış sistemden yeni bir istek alındı ve işleme alındı.'}}},
                ],
                'edges': [
                    {'id': 'e1', 'source': 'trigger', 'target': 'n1'},
                    {'id': 'e2', 'source': 'n1', 'target': 'n2'},
                ],
            },
        },
        {
            'id': 'manual_bulk_update',
            'name': 'Manuel → Kişi Güncelle + Bildir',
            'description': 'Manuel olarak tetiklendiğinde kişi alanını günceller ve sahibini bilgilendirir.',
            'icon': '⚙️',
            'category': 'advanced',
            'trigger': 'manual',
            'actions': ['update_contact_field', 'notify_owner'],
            'canvas_data': {
                'nodes': [
                    {'id': 'trigger', 'type': 'workflowNode', 'position': {'x': 250, 'y': 80},
                     'data': {'nodeType': 'trigger', 'subtype': 'manual', 'isEmpty': False,
                              'label': 'Manuel Başlat', 'config': {}}},
                    {'id': 'n1', 'type': 'workflowNode', 'position': {'x': 250, 'y': 220},
                     'data': {'nodeType': 'action', 'subtype': 'update_contact_field', 'isEmpty': False,
                              'label': 'Kişi Alanını Güncelle',
                              'config': {'field': 'lifecycle_stage', 'value': 'qualified_lead'}}},
                    {'id': 'n2', 'type': 'workflowNode', 'position': {'x': 250, 'y': 360},
                     'data': {'nodeType': 'action', 'subtype': 'notify_owner', 'isEmpty': False,
                              'label': 'Güncelleme Bildirimi',
                              'config': {'title': 'Kişi güncellendi',
                                         'message': '{{contact.first_name}} kişisinin lifecycle aşaması güncellendi.'}}},
                ],
                'edges': [
                    {'id': 'e1', 'source': 'trigger', 'target': 'n1'},
                    {'id': 'e2', 'source': 'n1', 'target': 'n2'},
                ],
            },
        },
    ]

    @staticmethod
    def _get_default_action_config(action_type: str) -> Dict:
        """Return default configuration for an action type"""
        defaults = {
            'create_task': {
                'title': 'Follow-up Task',
                'description': '',
                'assign_to': 'owner',
                'due_in_days': 2,
                'priority': 'medium',
            },
            'notify_owner': {
                'title': 'Workflow Alert',
                'message': 'Attention required for {{contact.first_name}}',
            },
            'update_deal_field': {
                'field': '',
                'value': '',
            },
            'update_contact_field': {
                'field': '',
                'value': '',
            },
            'send_email': {
                'to': '{{contact.email}}',
                'subject': 'Follow-up',
                'body': 'Hello {{contact.first_name}},',
            },
            'send_whatsapp': {
                'message': 'Hello {{contact.first_name}}!',
            },
            'add_tag': {
                'tag': '',
            },
            'remove_tag': {
                'tag': '',
            },
            'assign_owner': {
                'assign_to': 'round_robin',
            },
            'create_note': {
                'content': '',
                'is_private': False,
            },
            'webhook': {
                'url': '',
                'method': 'POST',
            },
            'wait': {
                'delay_minutes': 60,
            },
            'ai_agent': {
                'provider': 'minimax',
                'model': 'MiniMax-M2.7',
                'system_prompt': '',
                'user_prompt': '',
                'max_tokens': 2048,
                'temperature': 0.7,
            },
            'http_request': {
                'url': '',
                'method': 'GET',
                'auth_type': 'none',
                'timeout': 30,
            },
        }
        return defaults.get(action_type, {})
