"""
End-to-End Workflow System Test
================================
Tests if the workflow system actually works after our fixes.
"""
from app import app, db
from models_crm import Contact, Task, WorkflowExecution, WorkflowAutomation, WorkflowAction
import json

def run_test():
    with app.app_context():
        from models import User
        user = User.query.first()
        if not user:
            print("ERROR: No user found in database")
            return
        workspace_id = user.workspace_id
        print("Using workspace_id: %d" % workspace_id)
        
        # Clean up any previous test data
        print("\n--- Cleaning up previous test data ---")
        WorkflowAutomation.query.filter(WorkflowAutomation.name.like("TEST%")).delete()
        Task.query.filter(Task.title.like("%TEST TASK%")).delete()
        WorkflowExecution.query.filter(WorkflowExecution.entity_id.in_(
            db.session.query(Contact.id).filter(Contact.email == "test_workflow@test.com")
        )).delete(synchronize_session=False)
        Contact.query.filter_by(email="test_workflow@test.com").delete()
        db.session.commit()
        print("Cleanup complete")
        
        # STEP 1: Create test workflow
        print("\n--- STEP 1: Creating test workflow ---")
        try:
            wf = WorkflowAutomation(
                workspace_id=workspace_id,
                name="TEST - Contact Created Create Task",
                is_active=True,
                trigger_type="contact_created",
                trigger_config=json.dumps({}),
                condition_logic="AND"
            )
            db.session.add(wf)
            db.session.flush()
            
            # Create action: create_task
            action_config = {
                "title": "TEST TASK - Follow up with {{contact.first_name}}",
                "description": "Created automatically by workflow test",
                "due_in_days": 2,
                "assign_to": "contact_owner"
            }
            action = WorkflowAction(
                workflow_id=wf.id,
                workspace_id=workspace_id,
                action_type="create_task",
                action_config=json.dumps(action_config),
                delay_minutes=0,
                order_index=0
            )
            db.session.add(action)
            db.session.commit()
            print("OK - Created workflow id=%d, action id=%d" % (wf.id, action.id))
        except Exception as e:
            print("ERROR creating workflow: %s" % str(e))
            import traceback
            traceback.print_exc()
            return
        
        # STEP 2: Create test contact and fire trigger
        print("\n--- STEP 2: Creating test contact and firing trigger ---")
        try:
            contact = Contact(
                workspace_id=workspace_id,
                first_name="Test",
                last_name="Workflow",
                email="test_workflow@test.com"
            )
            db.session.add(contact)
            db.session.commit()
            print("OK - Created contact id=%d, first_name=%s" % (contact.id, contact.first_name))
        except Exception as e:
            print("ERROR creating contact: %s" % str(e))
            import traceback
            traceback.print_exc()
            return
        
        # Fire the trigger manually
        print("\nFiring trigger_event()...")
        from services.workflow_service import WorkflowService
        try:
            result = WorkflowService.trigger_event(
                workspace_id=workspace_id,
                trigger_type="contact_created",
                entity_type="contact",
                entity_id=contact.id
            )
            print("OK - trigger_event() returned: %s" % result)
        except Exception as e:
            print("ERROR in trigger_event: %s" % str(e))
            import traceback
            traceback.print_exc()
        
        # STEP 3: Check results
        print("\n--- STEP 3: Checking results ---")
        
        # Check WorkflowExecution
        executions = WorkflowExecution.query.filter_by(
            entity_id=contact.id
        ).all()
        print("WorkflowExecution records found: %d" % len(executions))
        for ex in executions:
            print("  - id=%d, status=%s, error=%s, actions=%s" % (ex.id, ex.status, ex.error_message, ex.actions_executed))
        
        # Check if Task was created
        tasks = Task.query.filter(
            Task.workspace_id == workspace_id,
            Task.title.like("%TEST TASK%")
        ).all()
        print("\nTasks created with 'TEST TASK' title: %d" % len(tasks))
        for t in tasks:
            print("  - id=%d, title=%s, contact_id=%s" % (t.id, t.title, t.contact_id))
        
        # Summary
        print("\n" + "="*50)
        if len(executions) > 0 and executions[0].status == 'completed':
            print("SUCCESS - WorkflowExecution created with status='completed'")
        else:
            print("FAIL - WorkflowExecution NOT created or not completed")
        
        if len(tasks) > 0:
            print("SUCCESS - Task created successfully!")
        else:
            print("FAIL - Task NOT created")
        print("="*50)

if __name__ == "__main__":
    run_test()