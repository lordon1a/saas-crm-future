from app import app

with app.test_client() as client:
    # Login first
    login_resp = client.post('/login', data={
        'email': 'demo@example.com',
        'password': 'demo123'
    }, follow_redirects=False)
    
    print(f'Login Status: {login_resp.status_code}')
    
    # Now try contacts API
    resp = client.get('/api/v1/contacts?page=1&per_page=50')
    print(f'Contacts Status: {resp.status_code}')
    
    if resp.status_code != 200:
        print(f'Error Response: {resp.get_json()}')
    else:
        data = resp.get_json()
        print(f'Success! Got {len(data.get("contacts", []))} contacts')
