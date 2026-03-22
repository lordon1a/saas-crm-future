"""
Test DocGen nested context generation
"""
import requests
import json

BASE_URL = 'http://localhost:5000'

# 1. Login
print("1. Logging in...")
session = requests.Session()
login_resp = session.post(f'{BASE_URL}/login', data={
    'username': 'demo',
    'password': 'demo123'
})
print(f"   Login status: {login_resp.status_code}")

# 2. Get first deal
print("\n2. Getting first deal...")
deals_resp = session.get(f'{BASE_URL}/api/deals')
if deals_resp.status_code == 200:
    deals = deals_resp.json()
    if deals:
        first_deal = deals[0]
        print(f"   Found deal: ID={first_deal['id']}, Name={first_deal['name']}")
        deal_id = first_deal['id']
    else:
        print("   No deals found!")
        exit(1)
else:
    print(f"   Error: {deals_resp.status_code}")
    exit(1)

# 3. Get templates
print("\n3. Getting templates...")
templates_resp = session.get(f'{BASE_URL}/api/docgen/templates')
if templates_resp.status_code == 200:
    data = templates_resp.json()
    templates = data.get('templates', [])
    if templates:
        template = templates[0]
        print(f"   Found template: ID={template['id']}, Name={template['name']}")
        template_id = template['id']
    else:
        print("   No templates found! Please upload a template first.")
        exit(1)
else:
    print(f"   Error: {templates_resp.status_code} - {templates_resp.text}")
    exit(1)

# 4. Generate document
print("\n4. Generating document...")
generate_payload = {
    'template_id': template_id,
    'record_id': deal_id,
    'record_type': 'deal',
    'output_type': 'docx'
}
print(f"   Payload: {json.dumps(generate_payload, indent=2)}")

generate_resp = session.post(
    f'{BASE_URL}/api/docgen/generate',
    json=generate_payload
)

print(f"   Status: {generate_resp.status_code}")
if generate_resp.status_code in [200, 201]:
    result = generate_resp.json()
    print(f"   Success! Document: {json.dumps(result, indent=2)}")
    
    # 5. Download document
    if result.get('document') and result['document'].get('id'):
        doc_id = result['document']['id']
        print(f"\n5. Downloading document ID={doc_id}...")
        download_resp = session.get(f'{BASE_URL}/api/docgen/download/{doc_id}')
        print(f"   Download status: {download_resp.status_code}")
        if download_resp.status_code == 200:
            filename = f"test_output_{doc_id}.docx"
            with open(filename, 'wb') as f:
                f.write(download_resp.content)
            print(f"   ✅ Document saved to: {filename}")
        else:
            print(f"   ❌ Download failed: {download_resp.text}")
else:
    print(f"   ❌ Generation failed: {generate_resp.text}")
