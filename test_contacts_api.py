from app import app
import json

with app.test_client() as client:
    # Login first
    login_resp = client.post('/login', data={
        'email': 'demo@example.com',
        'password': 'demo123'
    }, follow_redirects=False)
    
    print(f'Login Status: {login_resp.status_code}')
    
    # Now try contacts API
    resp = client.get('/api/v1/contacts?page=1&per_page=50')
    print(f'\nContacts Status: {resp.status_code}')
    
    if resp.status_code != 200:
        data = resp.get_json()
        print(f'\nError Response:')
        print(json.dumps(data, indent=2))
    else:
        data = resp.get_json()
        print(f'\nSuccess! Got {len(data.get("contacts", []))} contacts')
