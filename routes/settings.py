from flask import Blueprint, request, jsonify, session
from models import db, Workspace, User, MessageTemplate
from models_crm import PortalBranding
from services.auth_manager import AuthManager
import re

bp = Blueprint('settings', __name__, url_prefix='/api/settings')

DEFAULT_PORTAL_BRANDING = {
    'logo_url': '',
    'primary_color': '#7c3aed',
    'secondary_color': '#8b5cf6',
    'custom_domain': '',
    'custom_css': '',
}


def _normalize_hex_color(value, fallback):
    raw = (value or '').strip().lower()
    if re.fullmatch(r'#[0-9a-f]{6}', raw):
        return raw
    return fallback


def _serialize_portal_branding(row):
    if not row:
        return dict(DEFAULT_PORTAL_BRANDING)

    return {
        'logo_url': row.logo_url or '',
        'primary_color': _normalize_hex_color(row.primary_color, DEFAULT_PORTAL_BRANDING['primary_color']),
        'secondary_color': _normalize_hex_color(row.secondary_color, DEFAULT_PORTAL_BRANDING['secondary_color']),
        'custom_domain': row.custom_domain or '',
        'custom_css': row.custom_css or '',
    }

def login_required_api(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id') or not session.get('workspace_id'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('user_role') != 'admin':
            return jsonify({'error': 'Admin yetkisi gereklidir'}), 403
        return f(*args, **kwargs)
    return decorated

# ─── Workspace Genel Bilgi ──────────────────────────────────────────────────

@bp.route('/workspace', methods=['GET'])
@login_required_api
def get_workspace():
    """Mevcut workspace bilgilerini döndür"""
    workspace_id = session.get('workspace_id')
    ws = Workspace.query.get_or_404(workspace_id)
    return jsonify({
        'id': ws.id,
        'company_name': ws.company_name,
        'whatsapp_phone_number_id': ws.whatsapp_phone_number_id or '',
        'whatsapp_access_token': '***' if ws.whatsapp_access_token else '',
        'waba_id': ws.waba_id or '',
        'created_at': ws.created_at.isoformat()
    }), 200

@bp.route('/workspace', methods=['PUT'])
@login_required_api
@admin_required
def update_workspace():
    """Workspace bilgilerini güncelle (şirket adı + WhatsApp API credentials)"""
    workspace_id = session.get('workspace_id')
    ws = Workspace.query.get_or_404(workspace_id)
    data = request.get_json()

    if 'company_name' in data and data['company_name'].strip():
        ws.company_name = data['company_name'].strip()

    if 'whatsapp_phone_number_id' in data:
        ws.whatsapp_phone_number_id = data['whatsapp_phone_number_id'].strip() or None

    if 'whatsapp_access_token' in data and data['whatsapp_access_token'] != '***':
        ws.whatsapp_access_token = data['whatsapp_access_token'].strip() or None

    if 'waba_id' in data:
        ws.waba_id = data['waba_id'].strip() or None

    db.session.commit()
    return jsonify({'status': 'updated', 'company_name': ws.company_name}), 200

@bp.route('/workspace/test-whatsapp', methods=['POST'])
@login_required_api
@admin_required
def test_whatsapp_connection():
    """WhatsApp API bağlantısını test et"""
    workspace_id = session.get('workspace_id')
    ws = Workspace.query.get_or_404(workspace_id)
    
    if not ws.whatsapp_phone_number_id or not ws.whatsapp_access_token:
        return jsonify({'success': False, 'error': 'Eksik yapılandırma (Phone Number ID veya Access Token yok)'}), 400
        
    import requests
    from config import Config
    
    url = f"{Config.META_API_BASE_URL}/{ws.whatsapp_phone_number_id}"
    headers = {'Authorization': f'Bearer {ws.whatsapp_access_token}'}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.ok:
            data = response.json()
            return jsonify({
                'success': True,
                'data': {
                    'verified_name': data.get('verified_name'),
                    'display_phone_number': data.get('display_phone_number'),
                    'quality_rating': data.get('quality_rating')
                }
            }), 200
        else:
            error_data = response.json().get('error', {})
            return jsonify({
                'success': False,
                'error': error_data.get('message', 'Bilinmeyen Meta API hatası')
            }), response.status_code
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/portal-branding', methods=['GET'])
@login_required_api
def get_portal_branding():
    """Get workspace portal branding configuration"""
    workspace_id = session.get('workspace_id')
    branding = PortalBranding.query.filter_by(workspace_id=workspace_id).first()

    payload = _serialize_portal_branding(branding)
    payload['workspace_id'] = workspace_id
    return jsonify(payload), 200


@bp.route('/portal-branding', methods=['PUT'])
@login_required_api
@admin_required
def update_portal_branding():
    """Update white-label branding settings for customer portal"""
    workspace_id = session.get('workspace_id')
    data = request.get_json(silent=True) or {}

    branding = PortalBranding.query.filter_by(workspace_id=workspace_id).first()
    if not branding:
        branding = PortalBranding(workspace_id=workspace_id)
        db.session.add(branding)

    branding.logo_url = (data.get('logo_url') or '').strip() or None
    branding.primary_color = _normalize_hex_color(
        data.get('primary_color'),
        DEFAULT_PORTAL_BRANDING['primary_color']
    )
    branding.secondary_color = _normalize_hex_color(
        data.get('secondary_color'),
        DEFAULT_PORTAL_BRANDING['secondary_color']
    )

    custom_domain = (data.get('custom_domain') or '').strip().lower()
    if custom_domain and not re.fullmatch(r'[a-z0-9.-]+', custom_domain):
        return jsonify({'error': 'Geçersiz domain formatı'}), 400
    branding.custom_domain = custom_domain or None

    custom_css = data.get('custom_css')
    branding.custom_css = custom_css.strip() if isinstance(custom_css, str) else None

    db.session.commit()

    payload = _serialize_portal_branding(branding)
    payload['workspace_id'] = workspace_id
    return jsonify(payload), 200

# ─── Takım Üyesi Yönetimi ───────────────────────────────────────────────────

@bp.route('/team', methods=['GET'])
@login_required_api
def get_team():
    """Workspace'teki tüm kullanıcıları listele"""
    workspace_id = session.get('workspace_id')
    users = User.query.filter_by(workspace_id=workspace_id).all()
    return jsonify([{
        'id': u.id,
        'name': u.name,
        'email': u.email,
        'role': u.role
    } for u in users]), 200

@bp.route('/team', methods=['POST'])
@login_required_api
@admin_required
def invite_team_member():
    """Yeni takım üyesi ekle (admin yetkisi gerekir)"""
    workspace_id = session.get('workspace_id')
    data = request.get_json()

    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', 'agent')

    if not all([name, email, password]):
        return jsonify({'error': 'Ad, email ve şifre zorunludur'}), 400

    if role not in ['admin', 'agent']:
        return jsonify({'error': 'Geçersiz rol'}), 400

    if len(password) < 8:
        return jsonify({'error': 'Şifre en az 8 karakter olmalıdır'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Bu email zaten kullanımda'}), 409

    user = User(
        workspace_id=workspace_id,
        name=name,
        email=email,
        password_hash=AuthManager.hash_password(password),
        role=role
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({
        'status': 'created',
        'user': {'id': user.id, 'name': user.name, 'email': user.email, 'role': user.role}
    }), 201

@bp.route('/team/<int:user_id>', methods=['PUT'])
@login_required_api
@admin_required
def update_team_member(user_id):
    """Takım üyesinin rolünü güncelle"""
    workspace_id = session.get('workspace_id')
    user = User.query.filter_by(id=user_id, workspace_id=workspace_id).first_or_404()

    if user.id == session.get('user_id'):
        return jsonify({'error': 'Kendi rolünüzü değiştiremezsiniz'}), 400

    data = request.get_json()
    role = data.get('role')
    if role not in ['admin', 'agent']:
        return jsonify({'error': 'Geçersiz rol'}), 400

    user.role = role
    db.session.commit()
    return jsonify({'status': 'updated'}), 200

@bp.route('/team/<int:user_id>', methods=['DELETE'])
@login_required_api
@admin_required
def remove_team_member(user_id):
    """Takım üyesini workspace'ten çıkar"""
    workspace_id = session.get('workspace_id')
    user = User.query.filter_by(id=user_id, workspace_id=workspace_id).first_or_404()

    if user.id == session.get('user_id'):
        return jsonify({'error': 'Kendinizi silemezsiniz'}), 400

    db.session.delete(user)
    db.session.commit()
    return jsonify({'status': 'deleted'}), 200

# ─── Şablonlu Mesajlar ──────────────────────────────────────────────────────

@bp.route('/templates', methods=['GET'])
@login_required_api
def get_templates():
    """Workspace şablonlarını listele"""
    workspace_id = session.get('workspace_id')
    templates = MessageTemplate.query.filter_by(workspace_id=workspace_id).order_by(MessageTemplate.created_at.desc()).all()
    return jsonify([{
        'id': t.id,
        'name': t.name,
        'body': t.body,
        'category': t.category,
        'language': t.language,
        'created_at': t.created_at.isoformat()
    } for t in templates]), 200

@bp.route('/templates', methods=['POST'])
@login_required_api
def create_template():
    """Yeni şablon oluştur"""
    workspace_id = session.get('workspace_id')
    data = request.get_json()

    name = data.get('name', '').strip()
    body = data.get('body', '').strip()
    category = data.get('category', 'custom')
    language = data.get('language', 'tr')

    if not name or not body:
        return jsonify({'error': 'Şablon adı ve içeriği zorunludur'}), 400

    template = MessageTemplate(
        workspace_id=workspace_id,
        name=name,
        body=body,
        category=category,
        language=language,
        created_by=session.get('user_id')
    )
    db.session.add(template)
    db.session.commit()

    return jsonify({
        'id': template.id,
        'name': template.name,
        'body': template.body,
        'category': template.category
    }), 201

@bp.route('/templates/<int:template_id>', methods=['PUT'])
@login_required_api
def update_template(template_id):
    """Şablonu güncelle"""
    workspace_id = session.get('workspace_id')
    template = MessageTemplate.query.filter_by(id=template_id, workspace_id=workspace_id).first_or_404()
    data = request.get_json()

    if 'name' in data: template.name = data['name'].strip()
    if 'body' in data: template.body = data['body'].strip()
    if 'category' in data: template.category = data['category']

    db.session.commit()
    return jsonify({'status': 'updated'}), 200

@bp.route('/templates/<int:template_id>', methods=['DELETE'])
@login_required_api
def delete_template(template_id):
    """Şablonu sil"""
    workspace_id = session.get('workspace_id')
    template = MessageTemplate.query.filter_by(id=template_id, workspace_id=workspace_id).first_or_404()
    db.session.delete(template)
    db.session.commit()
    return jsonify({'status': 'deleted'}), 200

# ─── Profil Ayarları ────────────────────────────────────────────────────────

@bp.route('/profile', methods=['GET'])
@login_required_api
def get_profile():
    """Mevcut kullanıcının profil bilgilerini döndür"""
    user_id = session.get('user_id')
    user = User.query.get_or_404(user_id)
    return jsonify({
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'role': user.role
    }), 200

@bp.route('/profile', methods=['PUT'])
@login_required_api
def update_profile():
    """Profil bilgilerini güncelle (ad soyad)"""
    user_id = session.get('user_id')
    user = User.query.get_or_404(user_id)
    data = request.get_json()

    if 'name' in data and data['name'].strip():
        user.name = data['name'].strip()
        db.session.commit()
        # Session'daki name'i de güncellemek gerekebilir (opsiyonel)
        return jsonify({'status': 'updated', 'name': user.name}), 200
    
    return jsonify({'error': 'Geçersiz veri'}), 400

@bp.route('/profile/password', methods=['PUT'])
@login_required_api
def change_password():
    """Şifre değiştir"""
    user_id = session.get('user_id')
    user = User.query.get_or_404(user_id)
    data = request.get_json()

    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return jsonify({'error': 'Mevcut ve yeni şifre gereklidir'}), 400

    if not AuthManager.verify_password(user.password_hash, current_password):
        return jsonify({'error': 'Mevcut şifre hatalı'}), 400

    if len(new_password) < 8:
        return jsonify({'error': 'Yeni şifre en az 8 karakter olmalıdır'}), 400

    user.password_hash = AuthManager.hash_password(new_password)
    db.session.commit()

    return jsonify({'status': 'updated'}), 200
