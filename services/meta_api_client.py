import requests
import os
from config import Config

class MetaAPIClient:
    def __init__(self, access_token=None, phone_number_id=None):
        """Initialize Meta API client"""
        self.access_token = access_token or os.getenv('WHATSAPP_TOKEN')
        self.phone_number_id = phone_number_id or os.getenv('WHATSAPP_PHONE_NUMBER_ID')
        self.base_url = Config.META_API_BASE_URL
    
    def send_text_message(self, to, message):
        """Send text message via WhatsApp"""
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'messaging_product': 'whatsapp',
            'to': to,
            'type': 'text',
            'text': {
                'body': message
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            message_id = data.get('messages', [{}])[0].get('id')
            
            return {
                'success': True,
                'message_id': message_id,
                'error': None
            }
        
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'message_id': None,
                'error': str(e)
            }

    def send_image(self, to, image_url, caption=None):
        """Send image by URL (public URL that Meta can fetch)."""
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {'Authorization': f'Bearer {self.access_token}', 'Content-Type': 'application/json'}
        payload = {
            'messaging_product': 'whatsapp',
            'to': to.replace('+', ''),
            'type': 'image',
            'image': {'link': image_url}
        }
        if caption:
            payload['image']['caption'] = caption[:1024]
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=15)
            r.raise_for_status()
            data = r.json()
            return {'success': True, 'message_id': data.get('messages', [{}])[0].get('id'), 'error': None}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'message_id': None, 'error': str(e)}

    def send_document(self, to, document_url, caption=None, filename=None):
        """Send document by URL."""
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {'Authorization': f'Bearer {self.access_token}', 'Content-Type': 'application/json'}
        doc = {'link': document_url}
        if filename:
            doc['filename'] = filename[:256]
        payload = {
            'messaging_product': 'whatsapp',
            'to': to.replace('+', ''),
            'type': 'document',
            'document': doc
        }
        if caption:
            payload['document']['caption'] = caption[:1024]
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=15)
            r.raise_for_status()
            data = r.json()
            return {'success': True, 'message_id': data.get('messages', [{}])[0].get('id'), 'error': None}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'message_id': None, 'error': str(e)}
    
    def mark_message_as_read(self, message_id):
        """Mark message as read"""
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'messaging_product': 'whatsapp',
            'status': 'read',
            'message_id': message_id
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            return {'success': True}
        
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}
