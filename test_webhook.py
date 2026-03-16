"""
Test script to simulate incoming WhatsApp message
"""
import requests
import json

# Test webhook payload (Meta WhatsApp format)
test_payload = {
    "object": "whatsapp_business_account",
    "entry": [{
        "changes": [{
            "value": {
                "messaging_product": "whatsapp",
                "metadata": {
                    "phone_number_id": "123456789"
                },
                "contacts": [{
                    "profile": {
                        "name": "Test Müşteri"
                    },
                    "wa_id": "905551234567"
                }],
                "messages": [{
                    "from": "905551234567",
                    "id": "wamid.test123",
                    "timestamp": "1234567890",
                    "type": "text",
                    "text": {
                        "body": "Merhaba, sipariş durumu nedir?"
                    }
                }]
            }
        }]
    }]
}

# Send POST request to webhook
url = "http://localhost:5000/webhook"
response = requests.post(url, json=test_payload)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")

# Get conversations to verify
conversations_response = requests.get("http://localhost:5000/api/conversations")
print(f"\nConversations: {json.dumps(conversations_response.json(), indent=2, ensure_ascii=False)}")
