from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template
import logging
import secrets
from models import db, User, Workspace, TeamInvitation
from config import Config
from services.auth_manager import AuthManager
from services.audit_service import AuditService
from services.security_service import SecurityService
from services.team_service import TeamService

logger = logging.getLogger(__name__)
bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET'])
def login_page():
    if session.get('user_id'):
        return redirect(url_for('index'))
    return render_template('login.html')

@bp.route('/login', methods=['POST'])
def login():
    try:
        from flask import session as flask_session
        from utils.permissions import check_login_attempts, record_login_attempt
        
        data = request.get_json(silent=True) or request.form.to_dict() or {}
        email = str(data.get('email', '')).strip().lower()
        password = str(data.get('password', ''))
        two_factor_token = str(data.get('two_factor_token', '')).strip()

        if not email or not password:
            return jsonify({'error': 'Email ve şifre gereklidir'}), 400

        # BRUTE-FORCE PROTECTION: Check if login attempts exceeded
        ip_address = request.remote_addr
        allowed, wait_minutes, reason = check_login_attempts(email, ip_address)
        
        if not allowed:
            logger.warning(
                f'SECURITY: Login blocked for {email} from {ip_address} - {reason}'
            )
            return jsonify({
                'error': reason,
                'wait_minutes': wait_minutes,
                'locked_out': True
            }), 429

        user = AuthManager.authenticate_user(email, password)
        if not user:
            # Record failed attempt
            record_login_attempt(
                email=email,
                ip_address=ip_address,
                success=False,
                user_agent=request.headers.get('User-Agent', '')
            )
            
            logger.warning('Başarısız giriş denemesi: %s from %s', email, ip_address)
            return jsonify({'error': 'Email veya şifre hatalı'}), 401
        
        # Check if user is active (not deactivated)
        if not user.is_active:
            logger.warning('Deactivated user login attempt: %s', email)
            return jsonify({'error': 'Hesabınız devre dışı bırakılmış. Lütfen workspace yöneticinizle iletişime geçin.'}), 403

        try:
            if not SecurityService.is_ip_allowed(user.workspace_id, request.remote_addr):
                return jsonify({'error': 'IP erişimi engellendi'}), 403
        except Exception as exc:
            logger.error('IP whitelist check failed during login for user %s: %s', user.id, exc)

        try:
            if SecurityService.get_2fa_status(user.id):
                if not two_factor_token:
                    return jsonify({'error': '2FA kodu gerekli', 'needs_2fa': True}), 401
                if not SecurityService.verify_login_2fa(user.id, two_factor_token):
                    return jsonify({'error': '2FA kodu geçersiz', 'needs_2fa': True}), 401
        except Exception as exc:
            logger.error('2FA check failed during login for user %s: %s', user.id, exc)

        # Session'ı permanent yap (config'deki PERMANENT_SESSION_LIFETIME kullanılır)
        flask_session.permanent = True
        session_token = secrets.token_urlsafe(32)
        session['user_id'] = user.id
        session['workspace_id'] = user.workspace_id
        session['user_name'] = user.name
        session['user_email'] = user.email
        session['user_role'] = user.role
        session['session_token'] = session_token

        # Record successful login attempt
        record_login_attempt(
            email=email,
            ip_address=ip_address,
            success=True,
            user_agent=request.headers.get('User-Agent', '')
        )

        timeout_minutes = max(5, int(Config.PERMANENT_SESSION_LIFETIME / 60))
        try:
            SecurityService.record_session_activity(
                workspace_id=user.workspace_id,
                user_id=user.id,
                session_token=session_token,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                timeout_minutes=timeout_minutes,
            )
        except Exception as exc:
            logger.error('Session activity write failed during login for user %s: %s', user.id, exc)
        AuditService.log_event(user.workspace_id, user.id, 'auth.login', 'user', entity_id=user.id)
        return jsonify({'status': 'ok', 'name': user.name, 'role': user.role}), 200
    except Exception as exc:
        logger.exception('Unexpected login error: %s', exc)
        db.session.rollback()
        return jsonify({'error': 'Giris sirasinda beklenmeyen bir hata olustu'}), 500

@bp.route('/logout')
def logout():
    if session.get('workspace_id') and session.get('user_id'):
        AuditService.log_event(session.get('workspace_id'), session.get('user_id'), 'auth.logout', 'user', entity_id=session.get('user_id'))
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

        try:
            SecurityService.ensure_rbac_seed(workspace.id)
            SecurityService.assign_role(workspace.id, user.id, 'Admin')
        except Exception as exc:
            logger.warning('RBAC seed during register failed: %s', exc)

        # 3. Otomatik session login
        from flask import session as flask_session
        flask_session.permanent = True  # Session'ı permanent yap
        session['user_id'] = user.id
        session['workspace_id'] = workspace.id
        session['user_name'] = user.name
        session['user_email'] = user.email
        session['user_role'] = user.role
        session['session_token'] = secrets.token_urlsafe(32)

        timeout_minutes = max(5, int(Config.PERMANENT_SESSION_LIFETIME / 60))
        SecurityService.record_session_activity(
            workspace_id=workspace.id,
            user_id=user.id,
            session_token=session['session_token'],
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', ''),
            timeout_minutes=timeout_minutes,
        )

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

@bp.route('/accept-invitation/<token>', methods=['GET'])
def accept_invitation_page(token):
    """Display invitation acceptance form"""
    # Validate token and get invitation details
    invitation = TeamInvitation.query.filter_by(token=token).first()
    
    if not invitation:
        return render_template('accept_invitation.html', 
                             error='Geçersiz davet linki',
                             invitation=None)
    
    # Check if already accepted
    if invitation.status != 'pending':
        return render_template('accept_invitation.html',
                             error=f'Bu davet {invitation.status} durumunda',
                             invitation=None)
    
    # Check expiration
    from datetime import datetime
    if invitation.expires_at < datetime.utcnow():
        invitation.status = 'expired'
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update expired invitation: {str(e)}")
        
        return render_template('accept_invitation.html',
                             error='Bu davet süresi dolmuş',
                             invitation=None)
    
    # Get workspace details
    workspace = Workspace.query.get(invitation.workspace_id)
    inviter = User.query.get(invitation.inviter_id)
    
    return render_template('accept_invitation.html',
                         invitation=invitation,
                         workspace=workspace,
                         inviter=inviter,
                         error=None)

@bp.route('/accept-invitation', methods=['POST'])
def accept_invitation():
    """Process invitation acceptance and create user account"""
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    token = data.get('token', '').strip()
    name = data.get('name', '').strip()
    password = data.get('password', '')
    
    # Validate inputs
    if not all([token, name, password]):
        return jsonify({'error': 'Tüm alanları doldurunuz'}), 400
    
    if len(password) < 8:
        return jsonify({'error': 'Parola en az 8 karakter olmalıdır'}), 400
    
    try:
        # Hash password
        password_hash = AuthManager.hash_password(password)
        
        # Use TeamService to accept invitation
        user = TeamService.accept_invitation(token, name, password_hash)
        
        # Create session for new user
        from flask import session as flask_session
        flask_session.permanent = True
        session_token = secrets.token_urlsafe(32)
        session['user_id'] = user.id
        session['workspace_id'] = user.workspace_id
        session['user_name'] = user.name
        session['user_email'] = user.email
        session['user_role'] = user.role
        session['session_token'] = session_token
        
        # Record session activity
        timeout_minutes = max(5, int(Config.PERMANENT_SESSION_LIFETIME / 60))
        try:
            SecurityService.record_session_activity(
                workspace_id=user.workspace_id,
                user_id=user.id,
                session_token=session_token,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                timeout_minutes=timeout_minutes,
            )
        except Exception as exc:
            logger.error(f'Session activity write failed for new user {user.id}: {str(exc)}')
        
        # Log audit event
        try:
            AuditService.log_event(
                user.workspace_id, 
                user.id, 
                'team.invitation_accepted', 
                'user', 
                entity_id=user.id
            )
        except Exception as exc:
            logger.error(f'Audit log failed for invitation acceptance: {str(exc)}')
        
        logger.info(f"User {user.id} accepted invitation and created account")
        
        return jsonify({'status': 'ok', 'redirect': '/'}), 200
        
    except ValueError as e:
        # Business logic errors from TeamService
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception(f'Unexpected error during invitation acceptance: {str(e)}')
        db.session.rollback()
        return jsonify({'error': 'Davet kabul edilirken bir hata oluştu'}), 500

@bp.route('/forgot-password', methods=['GET'])
def forgot_password_page():
    """Display forgot password form"""
    if session.get('user_id'):
        return redirect(url_for('index'))
    return render_template('forgot_password.html')

@bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Process forgot password request and send reset email"""
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    email = data.get('email', '').strip().lower()
    
    if not email:
        return jsonify({'error': 'Email adresi gereklidir'}), 400
    
    try:
        # Create reset token (returns None if user not found, but we don't reveal that)
        token = AuthManager.create_password_reset_token(email, request.remote_addr)
        
        # Always return success to prevent email enumeration attacks
        # If user exists, send email; if not, just pretend we did
        if token:
            from models import User
            user = User.query.filter_by(email=email).first()
            if user:
                from services.email_hub_service import EmailHubService
                EmailHubService.send_password_reset_email(
                    user_email=user.email,
                    user_name=user.name,
                    reset_token=token
                )
        
        # Log audit event (only if user exists)
        if token:
            user = User.query.filter_by(email=email).first()
            if user:
                try:
                    AuditService.log_event(
                        user.workspace_id,
                        user.id,
                        'auth.password_reset_requested',
                        'user',
                        entity_id=user.id
                    )
                except Exception as exc:
                    logger.error(f'Audit log failed for password reset request: {str(exc)}')
        
        return jsonify({
            'status': 'ok',
            'message': 'Eğer bu email adresi kayıtlıysa, şifre sıfırlama linki gönderildi.'
        }), 200
        
    except Exception as e:
        logger.exception(f'Unexpected error during forgot password: {str(e)}')
        db.session.rollback()
        return jsonify({'error': 'Bir hata oluştu, lütfen tekrar deneyin'}), 500

@bp.route('/reset-password', methods=['GET'])
def reset_password_page():
    """Display reset password form"""
    if session.get('user_id'):
        return redirect(url_for('index'))
    
    token = request.args.get('token', '').strip()
    if not token:
        return render_template('reset_password.html', error='Geçersiz sıfırlama linki')
    
    # Verify token
    user = AuthManager.verify_reset_token(token)
    if not user:
        return render_template('reset_password.html', error='Bu link geçersiz veya süresi dolmuş')
    
    return render_template('reset_password.html', token=token, user=user)

@bp.route('/reset-password', methods=['POST'])
def reset_password():
    """Process password reset with token"""
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    token = data.get('token', '').strip()
    new_password = data.get('password', '')
    
    if not token or not new_password:
        return jsonify({'error': 'Token ve yeni şifre gereklidir'}), 400
    
    if len(new_password) < 8:
        return jsonify({'error': 'Şifre en az 8 karakter olmalıdır'}), 400
    
    try:
        # Verify token and get user before resetting
        user = AuthManager.verify_reset_token(token)
        if not user:
            return jsonify({'error': 'Bu link geçersiz veya süresi dolmuş'}), 400
        
        # Reset password
        success = AuthManager.reset_password_with_token(token, new_password)
        
        if not success:
            return jsonify({'error': 'Şifre sıfırlama başarısız oldu'}), 400
        
        # Log audit event
        try:
            AuditService.log_event(
                user.workspace_id,
                user.id,
                'auth.password_reset_completed',
                'user',
                entity_id=user.id
            )
        except Exception as exc:
            logger.error(f'Audit log failed for password reset completion: {str(exc)}')
        
        logger.info(f"User {user.id} successfully reset password")
        
        return jsonify({
            'status': 'ok',
            'message': 'Şifreniz başarıyla değiştirildi. Giriş yapabilirsiniz.',
            'redirect': '/login'
        }), 200
        
    except Exception as e:
        logger.exception(f'Unexpected error during password reset: {str(e)}')
        db.session.rollback()
        return jsonify({'error': 'Bir hata oluştu, lütfen tekrar deneyin'}), 500
