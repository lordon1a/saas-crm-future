from flask import Blueprint, request, jsonify, session
from models import db
from models_crm import AISettings
from functools import wraps
import hashlib
import base64
import requests
from cryptography.fernet import Fernet
from config import Config

bp = Blueprint('ai_settings', __name__, url_prefix='/api/settings')

def login_required_api(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id') or not session.get('workspace_id'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

def get_fernet():
    """Get Fernet cipher for encryption/decryption"""
    key_material = Config.SECRET_KEY.encode('utf-8')
    digest = hashlib.sha256(key_material).digest()
    return Fernet(base64.urlsafe_b64encode(digest))

@bp.route('/ai', methods=['GET'])
@login_required_api
def get_ai_settings():
    """Get all AI provider settings for workspace"""
    workspace_id = session.get('workspace_id')
    settings = AISettings.query.filter_by(workspace_id=workspace_id).all()
    
    # Create a dict for quick lookup
    settings_dict = {s.provider: s for s in settings}
    
    # Return all three providers with their status
    providers = []
    for provider in ['gemini', 'anthropic', 'openrouter']:
        s = settings_dict.get(provider)
        if s and s.api_key_encrypted:
            # Mask the key for display
            api_key_masked = s.api_key_encrypted[:2] + '***' if s.api_key_encrypted else None
            providers.append({
                'provider': provider,
                'model_name': s.model_name,
                'is_active': s.is_active,
                'has_key': True,
                'api_key_masked': api_key_masked,
            })
        else:
            # Provider not configured yet
            providers.append({
                'provider': provider,
                'model_name': '',
                'is_active': False,
                'has_key': False,
                'api_key_masked': None,
            })
    
    return jsonify({'providers': providers}), 200

@bp.route('/ai', methods=['PUT'])
@login_required_api
def save_ai_settings():
    """Save or update AI provider settings"""
    workspace_id = session.get('workspace_id')
    data = request.get_json()
    
    provider = data.get('provider')
    api_key = data.get('api_key', '').strip()
    model_name = data.get('model_name', '').strip()
    is_active = data.get('is_active', True)
    
    if not provider or provider not in ['gemini', 'anthropic', 'openrouter']:
        return jsonify({'error': 'Invalid provider'}), 400
    
    # Don't save if key is masked
    if api_key == '***':
        # Just update model/active status
        setting = AISettings.query.filter_by(
            workspace_id=workspace_id,
            provider=provider
        ).first()
        if setting:
            try:
                if model_name:
                    setting.model_name = model_name
                setting.is_active = is_active
                db.session.commit()
                return jsonify({'status': 'updated'}), 200
            except Exception as e:
                db.session.rollback()
                return jsonify({'error': str(e)}), 500
        return jsonify({'error': 'No existing settings to update'}), 400
    
    if not api_key:
        return jsonify({'error': 'API key required'}), 400
    
    try:
        # Encrypt API key
        fernet = get_fernet()
        encrypted_key = fernet.encrypt(api_key.encode('utf-8')).decode('utf-8')
        
        # Update or create
        setting = AISettings.query.filter_by(
            workspace_id=workspace_id,
            provider=provider
        ).first()
        
        if setting:
            setting.api_key_encrypted = encrypted_key
            if model_name:
                setting.model_name = model_name
            setting.is_active = is_active
        else:
            setting = AISettings(
                workspace_id=workspace_id,
                provider=provider,
                api_key_encrypted=encrypted_key,
                model_name=model_name,
                is_active=is_active
            )
            db.session.add(setting)
        
        db.session.commit()
        
        # Return format expected by frontend
        api_key_masked = encrypted_key[:2] + '***' if encrypted_key else None
        return jsonify({
            'status': 'saved',
            'provider': provider,
            'model_name': model_name,
            'is_active': is_active,
            'has_key': True,
            'api_key_masked': api_key_masked,
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/ai/test', methods=['POST'])
@login_required_api
def test_ai_key():
    """Test AI provider API key"""
    data = request.get_json()
    provider = data.get('provider')
    api_key = data.get('api_key', '').strip()
    model_name = data.get('model_name', '').strip()
    
    if not provider or not api_key:
        return jsonify({'error': 'Provider and API key required'}), 400
    
    try:
        if provider == 'gemini':
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name or 'gemini-2.5-flash')
            response = model.generate_content('Test')
            return jsonify({'success': True, 'message': 'Gemini connection successful'}), 200
            
        elif provider == 'anthropic':
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=model_name or 'claude-3-5-sonnet-latest',
                max_tokens=10,
                messages=[{'role': 'user', 'content': 'Test'}]
            )
            return jsonify({'success': True, 'message': 'Anthropic connection successful'}), 200
            
        elif provider == 'openrouter':
            import requests
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            }
            payload = {
                'model': model_name or 'minimax/minimax-m2.5:free',
                'messages': [{'role': 'user', 'content': 'Test'}],
                'max_tokens': 10,
            }
            response = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            return jsonify({'success': True, 'message': 'OpenRouter connection successful'}), 200
        
        return jsonify({'error': 'Unknown provider'}), 400
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
