"""
Test dashboard API to see what it returns
"""
import requests

# Test the API
response = requests.get('http://localhost:5000/api/dashboard/actions', 
                       cookies={'session': 'your_session_cookie_here'})

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
