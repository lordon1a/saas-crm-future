"""
Test script for new CRM features
Tests: Analytics, Broadcast, Templates, Segmentation
"""
import requests
import json

BASE_URL = 'http://localhost:5000'
session = requests.Session()

def login():
    """Login as admin"""
    # Login endpoint JSON bekliyor
    response = session.post(
        f'{BASE_URL}/login',
        json={
            'email': 'admin@example.com',
            'password': 'admin123'
        },
        headers={'Content-Type': 'application/json'}
    )
    
    # Session cookie'si alındı mı kontrol et
    if response.status_code == 200:
        data = response.json()
        if data.get('status') in ['success', 'ok']:
            print("✓ Login successful")
            return True
    
    print(f"✗ Login failed: {response.status_code}")
    if response.status_code == 200:
        print(f"  Response: {response.json()}")
    return False

def test_analytics():
    """Test analytics endpoint"""
    print("\n=== Testing Analytics ===")
    response = session.get(f'{BASE_URL}/api/analytics')
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Analytics loaded")
        print(f"  - Total conversations: {data['kpis']['total_conversations']}")
        print(f"  - Total customers: {data['kpis']['total_customers']}")
        print(f"  - Total messages: {data['kpis']['total_messages']}")
        print(f"  - Trend data points: {len(data['trend'])}")
        print(f"  - Tag distribution: {len(data['tag_distribution'])} tags")
        print(f"  - Agent stats: {len(data['agent_stats'])} agents")
        return True
    print(f"✗ Analytics failed: {response.status_code}")
    return False

def test_templates():
    """Test message templates"""
    print("\n=== Testing Message Templates ===")
    
    # Get templates
    response = session.get(f'{BASE_URL}/api/settings/templates')
    if response.status_code == 200:
        templates = response.json()
        print(f"✓ Templates loaded: {len(templates)} templates")
        for t in templates[:3]:
            print(f"  - {t['name']} ({t['category']})")
    else:
        print(f"✗ Get templates failed: {response.status_code}")
        return False
    
    # Create new template
    new_template = {
        'name': 'Test Template',
        'body': 'This is a test template: {{variable}}',
        'category': 'custom',
        'language': 'tr'
    }
    response = session.post(
        f'{BASE_URL}/api/settings/templates',
        json=new_template,
        headers={'Content-Type': 'application/json'}
    )
    if response.status_code == 201:
        data = response.json()
        template_id = data['id']
        print(f"✓ Template created: ID {template_id}")
        
        # Delete test template
        response = session.delete(f'{BASE_URL}/api/settings/templates/{template_id}')
        if response.status_code == 200:
            print(f"✓ Template deleted")
        return True
    else:
        print(f"✗ Create template failed: {response.status_code}")
        return False

def test_broadcast():
    """Test broadcast endpoint"""
    print("\n=== Testing Broadcast ===")
    
    # Test broadcast (dry run - will fail if no WhatsApp config)
    broadcast_data = {
        'target': 'all',
        'content': 'Test broadcast message'
    }
    response = session.post(
        f'{BASE_URL}/api/broadcast/send',
        json=broadcast_data,
        headers={'Content-Type': 'application/json'}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Broadcast endpoint working")
        print(f"  - Sent: {data.get('count', 0)}")
        print(f"  - Failed: {data.get('failed', 0)}")
        return True
    elif response.status_code == 400:
        data = response.json()
        if 'WhatsApp' in data.get('error', ''):
            print(f"⚠ Broadcast endpoint working (WhatsApp not configured)")
            return True
    
    print(f"✗ Broadcast failed: {response.status_code}")
    return False

def test_contacts():
    """Test contacts and segmentation"""
    print("\n=== Testing Contacts & Segmentation ===")
    
    # Get all contacts
    response = session.get(f'{BASE_URL}/api/contacts')
    if response.status_code == 200:
        data = response.json()
        contacts = data['contacts']
        print(f"✓ Contacts loaded: {len(contacts)} contacts")
        
        # Show label distribution
        labels = {}
        for c in contacts:
            if c.get('labels'):
                for label in c['labels'].split(','):
                    label = label.strip()
                    labels[label] = labels.get(label, 0) + 1
        
        if labels:
            print(f"  Label distribution:")
            for label, count in labels.items():
                print(f"    - {label}: {count}")
        else:
            print(f"  No labels found")
        
        return True
    
    print(f"✗ Contacts failed: {response.status_code}")
    return False

def test_workspace_settings():
    """Test workspace settings"""
    print("\n=== Testing Workspace Settings ===")
    
    response = session.get(f'{BASE_URL}/api/settings/workspace')
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Workspace settings loaded")
        print(f"  - Company: {data.get('company_name', 'N/A')}")
        print(f"  - Phone ID: {data.get('whatsapp_phone_number_id', 'Not set')}")
        print(f"  - Has token: {data.get('has_token', False)}")
        return True
    
    print(f"✗ Workspace settings failed: {response.status_code}")
    return False

def test_team():
    """Test team management"""
    print("\n=== Testing Team Management ===")
    
    response = session.get(f'{BASE_URL}/api/settings/team')
    if response.status_code == 200:
        team = response.json()
        print(f"✓ Team loaded: {len(team)} members")
        for member in team:
            print(f"  - {member['name']} ({member['role']}) - {member['email']}")
        return True
    
    print(f"✗ Team failed: {response.status_code}")
    return False

def main():
    print("=" * 50)
    print("WhatsApp CRM - Feature Test Suite")
    print("=" * 50)
    
    if not login():
        print("\n✗ Cannot proceed without login")
        return
    
    results = {
        'Analytics': test_analytics(),
        'Templates': test_templates(),
        'Broadcast': test_broadcast(),
        'Contacts': test_contacts(),
        'Workspace': test_workspace_settings(),
        'Team': test_team()
    }
    
    print("\n" + "=" * 50)
    print("Test Results Summary")
    print("=" * 50)
    
    for feature, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{feature:20s} {status}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠ {total - passed} test(s) failed")

if __name__ == '__main__':
    main()
