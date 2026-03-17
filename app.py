from flask import Flask, request, render_template, session, redirect, url_for, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from functools import wraps
import logging
import os
from datetime import datetime
from urllib.parse import urlparse

load_dotenv()

from config import Config
from realtime import socketio
from flask_socketio import emit, join_room, leave_room

app = Flask(__name__)
app.config.from_object(Config)
socketio.init_app(app, cors_allowed_origins='*')

# Production hardening checks
if Config.ENV == 'production':
    weak_secret_keys = {
        '',
        'dev-secret-key-change-in-production',
        'dev-secret-key',
        'change-me',
    }
    if not Config.SECRET_KEY or Config.SECRET_KEY in weak_secret_keys or len(Config.SECRET_KEY) < 32:
        raise RuntimeError('SECRET_KEY must be strong and at least 32 chars in production')

# CORS: Config'teki origin listesi
cors_origins = Config.CORS_ORIGINS
if Config.ENV == 'production' and ('*' in cors_origins or not cors_origins):
    raise RuntimeError('CORS_ORIGINS cannot contain "*" in production')

CORS(app, origins=cors_origins if isinstance(cors_origins, list) else [cors_origins])

# Logging
log_level = getattr(logging, Config.LOG_LEVEL, logging.INFO)
logging.basicConfig(
    level=log_level,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)
if Config.LOG_FILE:
    try:
        os.makedirs(os.path.dirname(Config.LOG_FILE) or '.', exist_ok=True)
        fh = logging.FileHandler(Config.LOG_FILE, encoding='utf-8')
        fh.setLevel(log_level)
        fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
        logging.getLogger().addHandler(fh)
    except Exception as e:
        logger.warning('Log dosyası açılamadı: %s', e)

# Rate limiting (login brute-force koruması)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=['200 per day'],
    storage_uri=os.getenv('RATELIMIT_STORAGE_URI', 'memory://'),  # production'da redis kullanılabilir
)

from models import db
from models_crm import SessionActivity
from routes import webhook, api
from routes import auth as auth_route
from routes import settings as settings_route
from routes import templates as templates_route
from routes import automation as automation_route
from routes import pipeline as pipeline_route
from routes import portal as portal_route
from routes import public_api as public_api_route
from routes import api_docs as api_docs_route
from routes import google_integration as google_integration_route
from routes import quickbooks_integration as quickbooks_integration_route
from routes import collaboration as collaboration_route
from routes import system_health as system_health_route
from routes import email_tracking as email_tracking_route
from routes import analytics as analytics_route
from routes.telegram import telegram_bp
from routes.contacts import contacts_bp
from routes.tasks import tasks_bp
from routes import custom_fields as custom_fields_route
from routes.scheduled_messages import scheduled_messages_bp
from routes.documents import documents_bp
from routes.email_hub import email_hub_bp
from services import portal_notification_service  # noqa: F401
from services.security_service import SecurityService

db.init_app(app)

app.register_blueprint(webhook.bp)
app.register_blueprint(api.bp)
app.register_blueprint(auth_route.bp)
app.register_blueprint(settings_route.bp)
app.register_blueprint(templates_route.bp)
app.register_blueprint(automation_route.bp)
app.register_blueprint(pipeline_route.bp)
app.register_blueprint(portal_route.bp)
app.register_blueprint(public_api_route.bp)
app.register_blueprint(api_docs_route.bp)
app.register_blueprint(google_integration_route.bp)
app.register_blueprint(quickbooks_integration_route.bp)
app.register_blueprint(collaboration_route.bp)
app.register_blueprint(system_health_route.bp)
app.register_blueprint(email_tracking_route.bp)
app.register_blueprint(analytics_route.bp)
app.register_blueprint(telegram_bp)
app.register_blueprint(contacts_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(custom_fields_route.bp)
app.register_blueprint(scheduled_messages_bp)
app.register_blueprint(documents_bp)
app.register_blueprint(email_hub_bp)

# Login endpoint'ine rate limit uygula
app.view_functions['auth.login'] = limiter.limit(Config.RATELIMIT_LOGIN)(app.view_functions['auth.login'])


@socketio.on('connect')
def socket_connect():
    if not session.get('user_id'):
        return False
    return True


@socketio.on('join_workspace')
def socket_join_workspace(payload):
    if not session.get('user_id'):
        return

    workspace_id = session.get('workspace_id')
    target_workspace_id = (payload or {}).get('workspace_id')
    if str(target_workspace_id) != str(workspace_id):
        return

    join_room(f'ws_{workspace_id}')
    emit('socket_connected', {'workspace_id': workspace_id})


@socketio.on('join_contact_room')
def socket_join_contact_room(payload):
    if not session.get('user_id'):
        return

    contact_id = (payload or {}).get('contact_id')
    if not contact_id:
        return
    join_room(f'contact_{contact_id}')


@socketio.on('leave_contact_room')
def socket_leave_contact_room(payload):
    if not session.get('user_id'):
        return

    contact_id = (payload or {}).get('contact_id')
    if not contact_id:
        return
    leave_room(f'contact_{contact_id}')

def _parse_origin_host(origin_value):
    try:
        parsed = urlparse(origin_value)
        return parsed.netloc.lower()
    except Exception:
        return ''


def _build_allowed_origin_hosts():
    hosts = {request.host.lower()}
    for origin in (cors_origins if isinstance(cors_origins, list) else [cors_origins]):
        if not origin or origin == '*':
            continue
        host = _parse_origin_host(origin)
        if host:
            hosts.add(host)
    return hosts


@app.before_request
def enforce_csrf_origin_check():
    if request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
        return None

    if request.path.startswith('/webhook'):
        return None

    if request.endpoint in {'auth.login', 'auth.register'}:
        return None

    if not session.get('user_id'):
        return None

    candidate = request.headers.get('Origin') or request.headers.get('Referer')
    if not candidate:
        return jsonify({'error': 'CSRF validation failed'}), 403

    candidate_host = _parse_origin_host(candidate)
    if not candidate_host:
        return jsonify({'error': 'CSRF validation failed'}), 403

    allowed_hosts = _build_allowed_origin_hosts()
    if candidate_host not in allowed_hosts:
        return jsonify({'error': 'CSRF validation failed'}), 403

    return None


@app.before_request
def enforce_active_session_timeout():
    if not session.get('user_id'):
        return None

    if request.endpoint in {'auth.logout'}:
        return None

    session_token = session.get('session_token')
    if not session_token:
        session.clear()
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Session expired'}), 401
        return redirect(url_for('auth.login_page'))

    row = SessionActivity.query.filter_by(session_token=session_token, is_active=True).first()
    if not row:
        session.clear()
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Session expired'}), 401
        return redirect(url_for('auth.login_page'))

    if row.expires_at and row.expires_at < datetime.utcnow():
        row.is_active = False
        db.session.commit()
        session.clear()
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Session expired'}), 401
        return redirect(url_for('auth.login_page'))

    timeout_minutes = max(5, int(Config.PERMANENT_SESSION_LIFETIME / 60))
    SecurityService.record_session_activity(
        workspace_id=session.get('workspace_id'),
        user_id=session.get('user_id'),
        session_token=session_token,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', ''),
        timeout_minutes=timeout_minutes,
    )
    return None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('auth.login_page'))
        return f(*args, **kwargs)
    return decorated


@app.route('/')
@login_required
def index():
    return render_template('index.html')


@app.route('/channels')
@login_required
def channels():
    return render_template('channels.html')


@app.route('/settings')
@login_required
def settings_page():
    return render_template('settings.html')


@app.route('/analytics')
@login_required
def analytics():
    return render_template('analytics.html')


@app.route('/account')
@login_required
def account_page():
    return render_template('account.html')


@app.route('/contacts')
@login_required
def contacts_page():
    return render_template('contacts.html')


@app.route('/companies')
@login_required
def companies_page():
    return render_template('companies.html')


@app.route('/broadcast')
@login_required
def broadcast():
    return render_template('broadcast.html')


@app.route('/automation')
@login_required
def automation():
    return render_template('automation.html')


@app.route('/pipeline')
@login_required
def pipeline():
    return render_template('pipeline.html')


@app.route('/tasks')
@login_required
def tasks_page():
    return render_template('tasks.html')


@app.route('/documents')
@login_required
def documents_page():
    return render_template('documents.html')


@app.route('/analytics-dashboard')
@login_required
def analytics_dashboard():
    return render_template('analytics.html')


with app.app_context():
    db.create_all()
    
    # Eski DB'de messages tablosuna media sutunlari yoksa ekle (SQLite uyumluluk)
    try:
        uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if uri.startswith('sqlite'):
            from sqlalchemy import text
            with db.engine.connect() as conn:
                r = conn.execute(text('PRAGMA table_info(messages)'))
                cols = [row[1] for row in r.fetchall()]
                need_commit = False
                if 'media_type' not in cols:
                    conn.execute(text('ALTER TABLE messages ADD COLUMN media_type VARCHAR(20)'))
                    need_commit = True
                    logger.info('messages.media_type column added')
                if 'media_url' not in cols:
                    conn.execute(text('ALTER TABLE messages ADD COLUMN media_url VARCHAR(500)'))
                    need_commit = True
                    logger.info('messages.media_url column added')
                if 'channel' not in cols:
                    conn.execute(text("ALTER TABLE messages ADD COLUMN channel VARCHAR(20) NOT NULL DEFAULT 'whatsapp'"))
                    need_commit = True
                    logger.info('messages.channel column added')

                r_ws = conn.execute(text('PRAGMA table_info(workspaces)'))
                ws_cols = [row[1] for row in r_ws.fetchall()]
                if 'telegram_bot_token' not in ws_cols:
                    conn.execute(text('ALTER TABLE workspaces ADD COLUMN telegram_bot_token TEXT'))
                    need_commit = True
                    logger.info('workspaces.telegram_bot_token column added')

                r_cust = conn.execute(text('PRAGMA table_info(customers)'))
                customer_cols = [row[1] for row in r_cust.fetchall()]
                if 'telegram_chat_id' not in customer_cols:
                    conn.execute(text('ALTER TABLE customers ADD COLUMN telegram_chat_id VARCHAR(100)'))
                    conn.execute(text('CREATE INDEX IF NOT EXISTS idx_customers_telegram_chat_id ON customers(telegram_chat_id)'))
                    need_commit = True
                    logger.info('customers.telegram_chat_id column added')

                r_contacts = conn.execute(text('PRAGMA table_info(contacts)'))
                contact_cols = [row[1] for row in r_contacts.fetchall()]
                if 'telegram_chat_id' not in contact_cols:
                    conn.execute(text('ALTER TABLE contacts ADD COLUMN telegram_chat_id VARCHAR(100)'))
                    conn.execute(text('CREATE INDEX IF NOT EXISTS idx_contacts_telegram_chat_id ON contacts(telegram_chat_id)'))
                    need_commit = True
                    logger.info('contacts.telegram_chat_id column added')
                if need_commit:
                    conn.commit()
    except Exception as e:
        logger.warning('Media/telegram columns migration skip: %s', e)

    # PostgreSQL auto-migration for telegram/channel columns
    try:
        uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if uri.startswith('postgres'):
            from sqlalchemy import text
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS channel VARCHAR(20) NOT NULL DEFAULT 'whatsapp'"))
                conn.execute(text('ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS telegram_bot_token TEXT'))
                conn.execute(text('ALTER TABLE customers ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(100)'))
                conn.execute(text('ALTER TABLE contacts ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(100)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS idx_customers_telegram_chat_id ON customers(telegram_chat_id)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS idx_contacts_telegram_chat_id ON contacts(telegram_chat_id)'))
                conn.commit()
    except Exception as e:
        logger.warning('PostgreSQL telegram migration skip: %s', e)
    
    # Auto-migration: Google Drive attachments table
    try:
        from sqlalchemy import text, inspect
        inspector = inspect(db.engine)
        
        # Check if drive_attachments table exists
        if 'drive_attachments' not in inspector.get_table_names():
            logger.info('🔄 Creating drive_attachments table...')
            
            if uri.startswith('sqlite'):
                # SQLite syntax
                db.session.execute(text("""
                    CREATE TABLE drive_attachments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        workspace_id INTEGER NOT NULL,
                        drive_file_id VARCHAR(200) NOT NULL,
                        file_name VARCHAR(500) NOT NULL,
                        mime_type VARCHAR(100),
                        file_size BIGINT,
                        thumbnail_url VARCHAR(1000),
                        web_view_link VARCHAR(1000),
                        entity_type VARCHAR(50) NOT NULL,
                        entity_id INTEGER NOT NULL,
                        attached_by INTEGER,
                        attached_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        notes TEXT,
                        FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                        FOREIGN KEY (attached_by) REFERENCES users(id)
                    )
                """))
            else:
                # PostgreSQL syntax
                db.session.execute(text("""
                    CREATE TABLE drive_attachments (
                        id SERIAL PRIMARY KEY,
                        workspace_id INTEGER NOT NULL,
                        drive_file_id VARCHAR(200) NOT NULL,
                        file_name VARCHAR(500) NOT NULL,
                        mime_type VARCHAR(100),
                        file_size BIGINT,
                        thumbnail_url VARCHAR(1000),
                        web_view_link VARCHAR(1000),
                        entity_type VARCHAR(50) NOT NULL,
                        entity_id INTEGER NOT NULL,
                        attached_by INTEGER,
                        attached_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        notes TEXT,
                        FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                        FOREIGN KEY (attached_by) REFERENCES users(id)
                    )
                """))
            
            # Create indexes
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_drive_attachments_workspace 
                ON drive_attachments(workspace_id)
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_drive_attachments_file 
                ON drive_attachments(drive_file_id)
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_drive_attachments_entity 
                ON drive_attachments(entity_type, entity_id)
            """))
            
            db.session.commit()
            logger.info('✅ drive_attachments table created successfully!')
        else:
            logger.info('✓ drive_attachments table already exists')
            
    except Exception as e:
        logger.warning('Drive attachments migration skip: %s', e)
    
    # Auto-seed demo user for production
    try:
        from models import User, Workspace
        from services.auth_manager import AuthManager
        
        # Check if admin@example.com exists
        demo_user = User.query.filter_by(email='admin@example.com').first()
        
        if not demo_user:
            logger.info('🌱 Demo user not found, creating...')
            
            # Get first workspace or create one
            demo_workspace = Workspace.query.first()
            if not demo_workspace:
                demo_workspace = Workspace(company_name='Demo Company')
                db.session.add(demo_workspace)
                db.session.flush()
            
            # Create demo admin user
            password_hash = AuthManager.hash_password('admin123')
            demo_user = User(
                workspace_id=demo_workspace.id,
                name='Demo Admin',
                email='admin@example.com',
                password_hash=password_hash,
                role='admin'
            )
            db.session.add(demo_user)
            db.session.commit()
            
            logger.info('✅ Demo user created!')
            logger.info('   Email: admin@example.com')
            logger.info('   Password: admin123')
        else:
            # User exists, ensure password is admin123
            logger.info('✓ Demo user exists, verifying password...')
            if not AuthManager.verify_password(demo_user.password_hash, 'admin123'):
                logger.info('🔄 Resetting demo user password to admin123...')
                demo_user.password_hash = AuthManager.hash_password('admin123')
                db.session.commit()
                logger.info('✅ Demo user password reset!')
            else:
                logger.info('✓ Demo user password is correct')
        
        # Auto-seed demo data if workspace is empty
        try:
            from models_crm import Company
            workspace_id = demo_user.workspace_id
            company_count = Company.query.filter_by(workspace_id=workspace_id).count()
            
            if company_count == 0:
                logger.info('🌱 No demo data found, creating sample data...')
                # Import and run seed function
                import sys
                import os
                sys.path.insert(0, os.path.dirname(__file__))
                from seed_demo_data import seed_demo_data
                seed_demo_data()
                logger.info('✅ Demo data created!')
            else:
                logger.info(f'✓ Demo data exists ({company_count} companies)')
        except Exception as e:
            logger.warning('Demo data seed skip: %s', e)
            
    except Exception as e:
        logger.warning('Demo user seed skip: %s', e)
    
    logger.info('Database tables created successfully!')
    logger.info('Server starting on http://localhost:5000')


if __name__ == '__main__':
    socketio.run(app, debug=Config.DEBUG, port=int(os.getenv('PORT', 5000)), host='0.0.0.0')
