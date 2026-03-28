"""
Check if demo data was actually saved to database
"""
from app import app, db
from models_crm import Contact, Deal, Task
from datetime import datetime

with app.app_context():
    workspace_id = 1
    
    print("🔍 Checking demo data in database...\n")
    
    # Check tasks
    print("📌 Tasks:")
    today = datetime.utcnow().date()
    overdue_tasks = Task.query.filter(
        Task.workspace_id == workspace_id,
        Task.status != 'completed',
        Task.due_date != None,
        Task.due_date < today
    ).all()
    print(f"  Overdue tasks: {len(overdue_tasks)}")
    for task in overdue_tasks:
        print(f"    - {task.title} (due: {task.due_date})")
    
    due_today_tasks = Task.query.filter(
        Task.workspace_id == workspace_id,
        Task.status != 'completed',
        Task.due_date == today
    ).all()
    print(f"  Due today tasks: {len(due_today_tasks)}")
    for task in due_today_tasks:
        print(f"    - {task.title}")
    
    # Check contacts
    print("\n👤 Contacts:")
    high_score_contacts = Contact.query.filter(
        Contact.workspace_id == workspace_id,
        Contact.is_deleted == False,
        Contact.lead_score >= 80
    ).all()
    print(f"  High score contacts (>=80): {len(high_score_contacts)}")
    for contact in high_score_contacts:
        print(f"    - {contact.full_name} (score: {contact.lead_score}, last_activity: {contact.last_activity_at})")
    
    medium_score_contacts = Contact.query.filter(
        Contact.workspace_id == workspace_id,
        Contact.is_deleted == False,
        Contact.lead_score >= 60,
        Contact.lead_score < 80
    ).all()
    print(f"  Medium score contacts (60-79): {len(medium_score_contacts)}")
    for contact in medium_score_contacts:
        print(f"    - {contact.full_name} (score: {contact.lead_score}, last_activity: {contact.last_activity_at})")
    
    # Check deals
    print("\n💼 Deals:")
    open_deals = Deal.query.filter(
        Deal.workspace_id == workspace_id,
        Deal.is_deleted == False,
        Deal.status == 'open'
    ).all()
    print(f"  Open deals: {len(open_deals)}")
    for deal in open_deals:
        print(f"    - {deal.name} (close: {deal.expected_close_date}, stage_entered: {deal.stage_entered_at})")
    
    print("\n" + "="*50)
    if not overdue_tasks and not due_today_tasks and len(high_score_contacts) == 0:
        print("❌ NO DEMO DATA FOUND - Need to run script again!")
    else:
        print("✅ Demo data exists in database")
