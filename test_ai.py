import json
from app import app
from models import User, Workspace
from models_crm import Deal

with app.app_context():
    client = app.test_client()
    
    user = User.query.first()
    if not user:
        print("No user found in DB to perform the test.")
        exit()
        
    print(f"Testing with User ID: {user.id}, Workspace ID: {user.workspace_id}")
    
    with client.session_transaction() as sess:
        sess['user_id'] = user.id
        sess['workspace_id'] = user.workspace_id
        
    # Find a deal for test 2
    deal = Deal.query.filter_by(workspace_id=user.workspace_id).first()
    if deal:
        res2 = client.get(f'/api/ai/context/deal/{deal.id}')
        print(f"\n--- TEST 2 Output (Deal {deal.id} Context) ---")
        print(json.dumps(res2.get_json(), indent=2, ensure_ascii=False))
    else:
        print("\n--- TEST 2 Output ---")
        print("No deals found for this workspace to test.")
        
    # Test 3: non-existent/different workspace deal
    res3 = client.get('/api/ai/context/deal/99999')
    print(f"\n--- TEST 3 Output (Deal 99999 Context) ---")
    print(f"Status Code: {res3.status_code}")
    print(f"Response: {res3.get_data(as_text=True).strip()}")
