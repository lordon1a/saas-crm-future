from flask import Blueprint, request, jsonify, session
from models import db, MessageTemplate, User
from functools import wraps

bp = Blueprint('templates', __name__, url_prefix='/api/settings')

def login_required_api(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'error': 'Unauthorized'}), 401
        if not session.get('workspace_id'):
            return jsonify({'error': 'Workspace context missing'}), 401
        return f(*args, **kwargs)
    return decorated

@bp.route('/templates', methods=['GET'])
@login_required_api
def get_templates():
    """Workspace'e ait tüm mesaj şablonlarını listele"""
    workspace_id = session.get('workspace_id')
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    
    pagination = MessageTemplate.query.filter_by(workspace_id=workspace_id).order_by(
        MessageTemplate.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    result = []
    for t in pagination.items:
        result.append({
            'id': t.id,
            'name': t.name,
            'body': t.body,
            'category': t.category,
            'language': t.language,
            'created_at': t.created_at.isoformat()
        })
    
    return jsonify({
        'templates': result,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page
    }), 200

@bp.route('/templates', methods=['POST'])
@login_required_api
def create_template():
    """Yeni mesaj şablonu oluştur"""
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json()
    
    name = data.get('name', '').strip()
    body = data.get('body', '').strip()
    category = data.get('category', 'custom').strip()
    language = data.get('language', 'tr').strip()
    
    if not name or not body:
        return jsonify({'error': 'Şablon adı ve içeriği zorunludur'}), 400
    
    template = MessageTemplate(
        workspace_id=workspace_id,
        name=name,
        body=body,
        category=category,
        language=language,
        created_by=user_id
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
    """Mesaj şablonunu güncelle"""
    workspace_id = session.get('workspace_id')
    template = MessageTemplate.query.filter_by(id=template_id, workspace_id=workspace_id).first()
    
    if not template:
        return jsonify({'error': 'Şablon bulunamadı'}), 404
    
    data = request.get_json()
    
    if 'name' in data:
        template.name = data['name'].strip()
    if 'body' in data:
        template.body = data['body'].strip()
    if 'category' in data:
        template.category = data['category'].strip()
    if 'language' in data:
        template.language = data['language'].strip()
    
    db.session.commit()
    
    return jsonify({'status': 'updated'}), 200

@bp.route('/templates/<int:template_id>', methods=['DELETE'])
@login_required_api
def delete_template(template_id):
    """Mesaj şablonunu sil"""
    workspace_id = session.get('workspace_id')
    template = MessageTemplate.query.filter_by(id=template_id, workspace_id=workspace_id).first()
    
    if not template:
        return jsonify({'error': 'Şablon bulunamadı'}), 404
    
    db.session.delete(template)
    db.session.commit()
    
    return jsonify({'status': 'deleted'}), 200

@bp.route('/workspace', methods=['GET'])
@login_required_api
def get_workspace_settings():
    """Workspace ayarlarını getir"""
    from models import Workspace
    workspace_id = session.get('workspace_id')
    workspace = Workspace.query.get(workspace_id)
    
    if not workspace:
        return jsonify({'error': 'Workspace not found'}), 404
    
    return jsonify({
        'id': workspace.id,
        'company_name': workspace.company_name,
        'whatsapp_phone_number_id': workspace.whatsapp_phone_number_id or '',
        'waba_id': workspace.waba_id or '',
        'has_token': bool(workspace.whatsapp_access_token)
    }), 200

@bp.route('/workspace', methods=['PUT'])
@login_required_api
def update_workspace_settings():
    """Workspace ayarlarını güncelle"""
    from models import Workspace
    workspace_id = session.get('workspace_id')
    workspace = Workspace.query.get(workspace_id)
    
    if not workspace:
        return jsonify({'error': 'Workspace not found'}), 404
    
    data = request.get_json()
    
    if 'company_name' in data:
        workspace.company_name = data['company_name'].strip()
    if 'whatsapp_phone_number_id' in data:
        workspace.whatsapp_phone_number_id = data['whatsapp_phone_number_id'].strip() or None
    if 'whatsapp_access_token' in data:
        workspace.whatsapp_access_token = data['whatsapp_access_token'].strip() or None
    if 'waba_id' in data:
        workspace.waba_id = data['waba_id'].strip() or None
    
    db.session.commit()
    
    return jsonify({'status': 'updated'}), 200

@bp.route('/team', methods=['GET'])
@login_required_api
def get_team_members():
    """Workspace takım üyelerini listele"""
    workspace_id = session.get('workspace_id')
    users = User.query.filter_by(workspace_id=workspace_id).order_by(User.id.asc()).all()
    
    result = []
    for u in users:
        result.append({
            'id': u.id,
            'name': u.name,
            'email': u.email,
            'role': u.role
        })
    
    return jsonify(result), 200

@bp.route('/team', methods=['POST'])
@login_required_api
def create_team_member():
    """Yeni takım üyesi oluştur"""
    from werkzeug.security import generate_password_hash
    workspace_id = session.get('workspace_id')
    data = request.get_json()
    
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    role = data.get('role', 'agent').strip()
    
    if not name or not email or not password:
        return jsonify({'error': 'Ad, e-posta ve şifre zorunludur'}), 400
    
    # E-posta kontrolü
    existing = User.query.filter_by(email=email).first()
    if existing:
        return jsonify({'error': 'Bu e-posta adresi zaten kullanılıyor'}), 409
    
    user = User(
        workspace_id=workspace_id,
        name=name,
        email=email,
        password_hash=generate_password_hash(password),
        role=role
    )
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'role': user.role
    }), 201

@bp.route('/team/<int:user_id>', methods=['DELETE'])
@login_required_api
def delete_team_member(user_id):
    """Takım üyesini sil"""
    workspace_id = session.get('workspace_id')
    current_user_id = session.get('user_id')
    
    # Kendini silmeye çalışıyor mu?
    if user_id == current_user_id:
        return jsonify({'error': 'Kendi hesabınızı silemezsiniz'}), 400
    
    user = User.query.filter_by(id=user_id, workspace_id=workspace_id).first()
    
    if not user:
        return jsonify({'error': 'Kullanıcı bulunamadı'}), 404
    
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({'status': 'deleted'}), 200

@bp.route('/profile', methods=['GET'])
@login_required_api
def get_profile():
    """Kullanıcı profil bilgilerini getir"""
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'role': user.role
    }), 200

@bp.route('/profile', methods=['PUT'])
@login_required_api
def update_profile():
    """Kullanıcı profil bilgilerini güncelle"""
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.get_json()
    
    if 'name' in data:
        user.name = data['name'].strip()
    
    db.session.commit()
    
    return jsonify({'status': 'updated'}), 200

@bp.route('/profile/password', methods=['PUT'])
@login_required_api
def change_password():
    """Kullanıcı şifresini değiştir"""
    from werkzeug.security import check_password_hash, generate_password_hash
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.get_json()
    current_password = data.get('current_password', '').strip()
    new_password = data.get('new_password', '').strip()
    
    if not current_password or not new_password:
        return jsonify({'error': 'Mevcut ve yeni şifre zorunludur'}), 400
    
    # Mevcut şifre kontrolü
    if not check_password_hash(user.password_hash, current_password):
        return jsonify({'error': 'Mevcut şifre hatalı'}), 401
    
    if len(new_password) < 6:
        return jsonify({'error': 'Yeni şifre en az 6 karakter olmalıdır'}), 400
    
    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    
    return jsonify({'status': 'updated'}), 200
