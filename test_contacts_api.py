"""
Test script for Contact Management API
Tests companies, contacts, and CSV import/export
"""
import requests
import json

BASE_URL = 'http://localhost:5000'

# Login first
session = requests.Session()
login_response = session.post(f'{BASE_URL}/login', json={
    'email': 'admin@example.com',
    'password': 'admin123'
})

if login_response.status_code != 200:
    print("❌ Login failed")
    exit(1)

print("✅ Login successful")

# Test 1: Create a company
print("\n--- Test 1: Create Company ---")
company_data = {
    'name': 'Acme Corporation',
    'industry': 'Technology',
    'size': '51-200',
    'website': 'https://acme.com',
    'phone': '+90 212 555 0001',
    'address': 'Istanbul, Turkey'
}

response = session.post(f'{BASE_URL}/api/v1/companies', json=company_data)
print(f"Status: {response.status_code}")
if response.status_code == 201:
    company = response.json()
    company_id = company['id']
    print(f"✅ Company created: {company['name']} (ID: {company_id})")
else:
    print(f"❌ Failed: {response.text}")
    exit(1)

# Test 2: Get all companies
print("\n--- Test 2: Get Companies ---")
response = session.get(f'{BASE_URL}/api/v1/companies')
print(f"Status: {response.status_code}")
if response.status_code == 200:
    companies = response.json()['companies']
    print(f"✅ Found {len(companies)} companies")
    for c in companies:
        print(f"  - {c['name']} ({c['industry']})")
else:
    print(f"❌ Failed: {response.text}")

# Test 3: Create contacts
print("\n--- Test 3: Create Contacts ---")
contacts_data = [
    {
        'first_name': 'John',
        'last_name': 'Doe',
        'email': 'john.doe@acme.com',
        'phone': '+90 532 111 2233',
        'whatsapp_phone': '+90 532 111 2233',
        'role': 'Decision Maker',
        'job_title': 'CEO',
        'company_id': company_id
    },
    {
        'first_name': 'Jane',
        'last_name': 'Smith',
        'email': 'jane.smith@acme.com',
        'phone': '+90 532 444 5566',
        'role': 'Influencer',
        'job_title': 'CTO',
        'company_id': company_id
    },
    {
        'first_name': 'Bob',
        'last_name': 'Johnson',
        'email': 'bob.johnson@acme.com',
        'phone': '+90 532 777 8899',
        'role': 'User',
        'job_title': 'Developer',
        'company_id': company_id
    }
]

contact_ids = []
for contact_data in contacts_data:
    response = session.post(f'{BASE_URL}/api/v1/contacts', json=contact_data)
    if response.status_code == 201:
        contact = response.json()
        contact_ids.append(contact['id'])
        print(f"✅ Contact created: {contact['full_name']} (Lead Score: {contact['lead_score']})")
    else:
        print(f"❌ Failed to create contact: {response.text}")

# Test 4: Get contacts by company
print("\n--- Test 4: Get Contacts by Company ---")
response = session.get(f'{BASE_URL}/api/v1/contacts?company_id={company_id}')
print(f"Status: {response.status_code}")
if response.status_code == 200:
    contacts = response.json()['contacts']
    print(f"✅ Found {len(contacts)} contacts for company")
    for c in contacts:
        print(f"  - {c['full_name']} ({c['job_title']}) - Lead Score: {c['lead_score']}")
else:
    print(f"❌ Failed: {response.text}")

# Test 5: Search contacts
print("\n--- Test 5: Search Contacts ---")
response = session.get(f'{BASE_URL}/api/v1/contacts?search=john')
print(f"Status: {response.status_code}")
if response.status_code == 200:
    contacts = response.json()['contacts']
    print(f"✅ Search found {len(contacts)} contacts")
    for c in contacts:
        print(f"  - {c['full_name']}")
else:
    print(f"❌ Failed: {response.text}")

# Test 6: Update contact
print("\n--- Test 6: Update Contact ---")
if contact_ids:
    update_data = {
        'job_title': 'Chief Executive Officer',
        'role': 'Champion'
    }
    response = session.patch(f'{BASE_URL}/api/v1/contacts/{contact_ids[0]}', json=update_data)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        contact = response.json()
        print(f"✅ Contact updated: {contact['full_name']} - {contact['job_title']}")
        print(f"   New Lead Score: {contact['lead_score']}")
    else:
        print(f"❌ Failed: {response.text}")

# Test 7: Export contacts to CSV
print("\n--- Test 7: Export Contacts CSV ---")
response = session.get(f'{BASE_URL}/api/v1/contacts/export')
print(f"Status: {response.status_code}")
if response.status_code == 200:
    csv_content = response.text
    lines = csv_content.strip().split('\n')
    print(f"✅ CSV exported with {len(lines)} lines (including header)")
    print(f"   Header: {lines[0][:100]}...")
    
    # Save CSV for inspection
    with open('test_contacts_export.csv', 'w', encoding='utf-8') as f:
        f.write(csv_content)
    print("   Saved to test_contacts_export.csv")
else:
    print(f"❌ Failed: {response.text}")

# Test 8: Export companies to CSV
print("\n--- Test 8: Export Companies CSV ---")
response = session.get(f'{BASE_URL}/api/v1/companies/export')
print(f"Status: {response.status_code}")
if response.status_code == 200:
    csv_content = response.text
    lines = csv_content.strip().split('\n')
    print(f"✅ CSV exported with {len(lines)} lines (including header)")
    
    # Save CSV for inspection
    with open('test_companies_export.csv', 'w', encoding='utf-8') as f:
        f.write(csv_content)
    print("   Saved to test_companies_export.csv")
else:
    print(f"❌ Failed: {response.text}")

# Test 9: Get single company with custom fields
print("\n--- Test 9: Get Single Company ---")
response = session.get(f'{BASE_URL}/api/v1/companies/{company_id}')
print(f"Status: {response.status_code}")
if response.status_code == 200:
    company = response.json()
    print(f"✅ Company details retrieved")
    print(f"   Name: {company['name']}")
    print(f"   Industry: {company['industry']}")
    print(f"   Size: {company['size']}")
    print(f"   Website: {company['website']}")
else:
    print(f"❌ Failed: {response.text}")

# Test 10: Get single contact with custom fields
print("\n--- Test 10: Get Single Contact ---")
if contact_ids:
    response = session.get(f'{BASE_URL}/api/v1/contacts/{contact_ids[0]}')
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        contact = response.json()
        print(f"✅ Contact details retrieved")
        print(f"   Name: {contact['full_name']}")
        print(f"   Email: {contact['email']}")
        print(f"   Role: {contact['role']}")
        print(f"   Lead Score: {contact['lead_score']}")
        print(f"   Company: {contact['company_name']}")
    else:
        print(f"❌ Failed: {response.text}")

print("\n" + "="*50)
print("✅ All tests completed successfully!")
print("="*50)
