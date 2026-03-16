from flask import Flask, request, render_template, session, redirect, url_for, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from functools import wraps
import logging
import os
from urllib.parse import urlparse

load_dotenv()

from config import Config

app = Flask(__name__)
app.config.from_object(Config)

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
from routes import email_tracking as email_tracking_route
from routes.contacts import contacts_bp
from routes.tasks import tasks_bp
from services import portal_notification_service  # noqa: F401

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
app.register_blueprint(email_tracking_route.bp)
app.register_blueprint(contacts_bp)
app.register_blueprint(tasks_bp)

# Login endpoint'ine rate limit uygula
app.view_functions['auth.login'] = limiter.limit(Config.RATELIMIT_LOGIN)(app.view_functions['auth.login'])


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
                if need_commit:
                    conn.commit()
    except Exception as e:
        logger.warning('Media columns migration skip: %s', e)
    logger.info('Database tables created successfully!')
    logger.info('Server starting on http://localhost:5000')


if __name__ == '__main__':
    app.run(debug=Config.DEBUG, port=int(os.getenv('PORT', 5000)), host='0.0.0.0')
