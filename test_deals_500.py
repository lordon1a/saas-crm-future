import json
from app import app
from models import User
from models_crm import Contact, Deal

with app.app_context():
    client = app.test_client()
    
    user = User.query.first()
    if not user:
        print("No user found.")
        exit()
        
    with client.session_transaction() as sess:
        sess['user_id'] = user.id
        sess['workspace_id'] = user.workspace_id
        
    # Get a valid contact or just use any valid contact_id
    contact = Contact.query.filter_by(workspace_id=user.workspace_id).first()
    if contact:
        cid = contact.id
        print(f"Testing with contact_id={cid}")
        res = client.get(f'/api/v1/deals?contact_id={cid}')
        print(f"Status Code: {res.status_code}")
        print(f"Response: {res.get_data(as_text=True)}")
    else:
        print("No contact found to test with.")
