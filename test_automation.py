"""
Automation Features Test Script
Otomasyon özelliklerini test eder
"""
import requests
import json

BASE_URL = 'http://localhost:5000'
session = requests.Session()

def login():
    """Login as admin"""
    response = session.post(
        f'{BASE_URL}/login',
        json={
            'email': 'admin@example.com',
            'password': 'admin123'
        },
        headers={'Content-Type': 'application/json'}
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('status') in ['success', 'ok']:
            print("✓ Login successful")
            return True
    
    print(f"✗ Login failed: {response.status_code}")
    return False


def test_auto_replies():
    """Test auto-reply endpoints"""
    print("\n=== Testing Auto-Replies ===")
    
    # Get existing auto-replies
    response = session.get(f'{BASE_URL}/api/automation/auto-replies')
    if response.status_code == 200:
        replies = response.json()
        print(f"✓ Loaded {len(replies)} auto-replies")
    else:
        print(f"✗ Failed to load auto-replies: {response.status_code}")
        return False
    
    # Create new auto-reply
    new_reply = {
        'name': 'Test Fiyat Bilgisi',
        'keywords': 'fiyat, ücret, ne kadar',
        'match_type': 'contains',
        'case_sensitive': False,
        'reply_message': 'Fiyat listemiz için: https://example.com/fiyatlar',
        'reply_delay': 2,
        'is_active': True
    }
    
    response = session.post(
        f'{BASE_URL}/api/automation/auto-replies',
        json=new_reply,
        headers={'Content-Type': 'application/json'}
    )
    
    if response.status_code == 201:
        data = response.json()
        reply_id = data['id']
        print(f"✓ Created auto-reply: ID {reply_id}")
        
        # Update it
        response = session.put(
            f'{BASE_URL}/api/automation/auto-replies/{reply_id}',
            json={'reply_delay': 3},
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            print(f"✓ Updated auto-reply")
        
        # Delete it
        response = session.delete(f'{BASE_URL}/api/automation/auto-replies/{reply_id}')
        if response.status_code == 200:
            print(f"✓ Deleted auto-reply")
        
        return True
    else:
        print(f"✗ Failed to create auto-reply: {response.status_code}")
        return False


def test_assignment_rules():
    """Test assignment rule endpoints"""
    print("\n=== Testing Assignment Rules ===")
    
    # Get existing rules
    response = session.get(f'{BASE_URL}/api/automation/assignment-rules')
    if response.status_code == 200:
        rules = response.json()
        print(f"✓ Loaded {len(rules)} assignment rules")
    else:
        print(f"✗ Failed to load assignment rules: {response.status_code}")
        return False
    
    # Create new rule
    new_rule = {
        'name': 'Test Round-Robin',
        'is_active': True,
        'priority': 5,
        'conditions': {},
        'assignment_type': 'round_robin',
        'assignment_config': {
            'agent_ids': [1, 2, 3]
        }
    }
    
    response = session.post(
        f'{BASE_URL}/api/automation/assignment-rules',
        json=new_rule,
        headers={'Content-Type': 'application/json'}
    )
    
    if response.status_code == 201:
        data = response.json()
        rule_id = data['id']
        print(f"✓ Created assignment rule: ID {rule_id}")
        
        # Delete it
        response = session.delete(f'{BASE_URL}/api/automation/assignment-rules/{rule_id}')
        if response.status_code == 200:
            print(f"✓ Deleted assignment rule")
        
        return True
    else:
        print(f"✗ Failed to create assignment rule: {response.status_code}")
        return False


def test_scheduled_messages():
    """Test scheduled message endpoints"""
    print("\n=== Testing Scheduled Messages ===")
    
    # Get existing messages
    response = session.get(f'{BASE_URL}/api/automation/scheduled-messages')
    if response.status_code == 200:
        messages = response.json()
        print(f"✓ Loaded {len(messages)} scheduled messages")
    else:
        print(f"✗ Failed to load scheduled messages: {response.status_code}")
        return False
    
    # Create new scheduled message
    new_message = {
        'target_type': 'conversation',
        'target_id': 1,
        'message_body': 'Test zamanlanmış mesaj',
        'schedule_type': 'once',
        'scheduled_at': '2024-12-31T10:00:00Z'
    }
    
    response = session.post(
        f'{BASE_URL}/api/automation/scheduled-messages',
        json=new_message,
        headers={'Content-Type': 'application/json'}
    )
    
    if response.status_code == 201:
        data = response.json()
        msg_id = data['id']
        print(f"✓ Created scheduled message: ID {msg_id}")
        
        # Cancel it
        response = session.delete(f'{BASE_URL}/api/automation/scheduled-messages/{msg_id}')
        if response.status_code == 200:
            print(f"✓ Cancelled scheduled message")
        
        return True
    else:
        print(f"✗ Failed to create scheduled message: {response.status_code}")
        return False


def test_automation_rules():
    """Test automation rule endpoints"""
    print("\n=== Testing Automation Rules ===")
    
    # Get existing rules
    response = session.get(f'{BASE_URL}/api/automation/rules')
    if response.status_code == 200:
        rules = response.json()
        print(f"✓ Loaded {len(rules)} automation rules")
    else:
        print(f"✗ Failed to load automation rules: {response.status_code}")
        return False
    
    # Create new rule
    new_rule = {
        'name': 'Test Hoş Geldin Mesajı',
        'description': 'Yeni konuşmalara hoş geldin mesajı gönder',
        'is_active': True,
        'trigger_type': 'new_conversation',
        'trigger_config': {},
        'conditions': {},
        'actions': [
            {
                'type': 'send_message',
                'message': 'Merhaba! Size nasıl yardımcı olabilirim?'
            }
        ]
    }
    
    response = session.post(
        f'{BASE_URL}/api/automation/rules',
        json=new_rule,
        headers={'Content-Type': 'application/json'}
    )
    
    if response.status_code == 201:
        data = response.json()
        rule_id = data['id']
        print(f"✓ Created automation rule: ID {rule_id}")
        
        # Toggle it
        response = session.post(f'{BASE_URL}/api/automation/rules/{rule_id}/toggle')
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Toggled rule (is_active: {data['is_active']})")
        
        # Delete it
        response = session.delete(f'{BASE_URL}/api/automation/rules/{rule_id}')
        if response.status_code == 200:
            print(f"✓ Deleted automation rule")
        
        return True
    else:
        print(f"✗ Failed to create automation rule: {response.status_code}")
        return False


def test_workflow_templates():
    """Test workflow template endpoints"""
    print("\n=== Testing Workflow Templates ===")
    
    response = session.get(f'{BASE_URL}/api/automation/workflow-templates')
    if response.status_code == 200:
        templates = response.json()
        print(f"✓ Loaded {len(templates)} workflow templates")
        for template in templates:
            print(f"  - {template['name']} ({template['category']})")
        return True
    else:
        print(f"✗ Failed to load workflow templates: {response.status_code}")
        return False


def test_automation_stats():
    """Test automation statistics"""
    print("\n=== Testing Automation Statistics ===")
    
    response = session.get(f'{BASE_URL}/api/automation/stats')
    if response.status_code == 200:
        stats = response.json()
        print(f"✓ Automation statistics loaded")
        print(f"  Rules: {stats['rules']['active']}/{stats['rules']['total']} active")
        print(f"  Auto-replies: {stats['auto_replies']['active']}/{stats['auto_replies']['total']} active")
        print(f"  Assignment rules: {stats['assignment_rules']['active']}/{stats['assignment_rules']['total']} active")
        print(f"  Executions (30d): {stats['executions_30d']}")
        print(f"  Success rate: {stats['success_rate']}%")
        return True
    else:
        print(f"✗ Failed to load statistics: {response.status_code}")
        return False


def main():
    print("=" * 60)
    print("WhatsApp CRM - Automation Features Test")
    print("=" * 60)
    
    if not login():
        print("\n✗ Cannot proceed without login")
        return
    
    results = {
        'Auto-Replies': test_auto_replies(),
        'Assignment Rules': test_assignment_rules(),
        'Scheduled Messages': test_scheduled_messages(),
        'Automation Rules': test_automation_rules(),
        'Workflow Templates': test_workflow_templates(),
        'Statistics': test_automation_stats()
    }
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    for feature, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{feature:25s} {status}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All automation tests passed!")
        print("\n📚 Next Steps:")
        print("  1. Check AUTOMATION_GUIDE.md for usage examples")
        print("  2. Create your first auto-reply")
        print("  3. Set up assignment rules")
        print("  4. Schedule a test message")
    else:
        print(f"\n⚠ {total - passed} test(s) failed")


if __name__ == '__main__':
    main()
