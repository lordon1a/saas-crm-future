from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template
import logging
from models import db, User, Workspace
from services.auth_manager import AuthManager

logger = logging.getLogger(__name__)
bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET'])
def login_page():
    if session.get('user_id'):
        return redirect(url_for('index'))
    return render_template('login.html')

@bp.route('/login', methods=['POST'])
def login():
    from flask import session as flask_session
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email ve şifre gereklidir'}), 400

    user = AuthManager.authenticate_user(email, password)
    if not user:
        logger.warning('Başarısız giriş denemesi: %s', email)
        return jsonify({'error': 'Email veya şifre hatalı'}), 401

    # Session'ı permanent yap (config'deki PERMANENT_SESSION_LIFETIME kullanılır)
    flask_session.permanent = True
    session['user_id'] = user.id
    session['workspace_id'] = user.workspace_id
    session['user_name'] = user.name
    session['user_email'] = user.email
    session['user_role'] = user.role
    return jsonify({'status': 'ok', 'name': user.name, 'role': user.role}), 200

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login_page'))

@bp.route('/register', methods=['GET'])
def register_page():
    if session.get('user_id'):
        return redirect(url_for('index'))
    return render_template('register.html')

@bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    company_name = data.get('company_name', '').strip()
    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not all([company_name, full_name, email, password]):
        return jsonify({'error': 'Tüm alanları doldurunuz'}), 400

    if len(password) < 8:
        return jsonify({'error': 'Parola en az 8 karakter olmalıdır'}), 400

    # Email kontrolü
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Bu email adresi zaten kullanımda'}), 409

    try:
        # 1. Workspace oluştur
        workspace = Workspace(company_name=company_name)
        db.session.add(workspace)
        db.session.flush()  # ID almak için flush

        # 2. Admin kullanıcı oluştur
        password_hash = AuthManager.hash_password(password)
        user = User(
            workspace_id=workspace.id,
            name=full_name,
            email=email,
            password_hash=password_hash,
            role='admin'
        )
        db.session.add(user)
        db.session.commit()

        # 3. Otomatik session login
        from flask import session as flask_session
        flask_session.permanent = True  # Session'ı permanent yap
        session['user_id'] = user.id
        session['workspace_id'] = workspace.id
        session['user_name'] = user.name
        session['user_email'] = user.email
        session['user_role'] = user.role

        return jsonify({'status': 'ok', 'redirect': '/'}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Kayıt sırasında bir hata oluştu'}), 500

@bp.route('/api/me')
def me():
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify({
        'id': session['user_id'],
        'workspace_id': session.get('workspace_id'),
        'name': session['user_name'],
        'email': session['user_email'],
        'role': session['user_role']
    }), 200

@bp.route('/api/account/profile', methods=['PUT'])
def update_profile():
    """Kullanıcı adı ve e-posta güncelle"""
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    data  = request.get_json()
    name  = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()

    if not name or not email:
        return jsonify({'error': 'Ad ve e-posta zorunlu'}), 400

    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'Kullanıcı bulunamadı'}), 404

    # E-posta başkası tarafından kullanılıyor mu?
    if email != user.email:
        existing = User.query.filter_by(email=email).first()
        if existing:
            return jsonify({'error': 'Bu e-posta adresi zaten kullanımda'}), 409

    user.name  = name
    user.email = email
    db.session.commit()

    # Session'ı güncelle
    session['user_name']  = name
    session['user_email'] = email

    return jsonify({'status': 'ok', 'name': name, 'email': email}), 200

@bp.route('/api/account/password', methods=['PUT'])
def update_password():
    """Şifre değiştir"""
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    data     = request.get_json()
    current  = data.get('current_password', '')
    new_pw   = data.get('new_password', '')

    if not current or not new_pw:
        return jsonify({'error': 'Tüm alanlar zorunlu'}), 400
    if len(new_pw) < 8:
        return jsonify({'error': 'Yeni şifre en az 8 karakter olmalı'}), 400

    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'Kullanıcı bulunamadı'}), 404

    if not AuthManager.verify_password(user.password_hash, current):
        return jsonify({'error': 'Mevcut şifre yanlış'}), 401

    user.password_hash = AuthManager.hash_password(new_pw)
    db.session.commit()

    return jsonify({'status': 'ok'}), 200
