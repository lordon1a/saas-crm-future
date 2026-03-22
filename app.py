from gevent import monkey
monkey.patch_all()

from flask import Flask, request, render_template, session, redirect, url_for, jsonify
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
from functools import wraps
import logging
import os
import ipaddress
import uuid
import atexit
from datetime import datetime, UTC
from urllib.parse import urlparse

load_dotenv()

from config import Config
import realtime
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config.from_object(Config)

# Eventlet-safe SQLAlchemy engine tuning for Render/runtime stability.
db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
engine_options = dict(app.config.get('SQLALCHEMY_ENGINE_OPTIONS') or {})
engine_options.setdefault('pool_pre_ping', True)

if not str(db_uri).startswith('sqlite'):
    # Render'da gevent worker ile QueuePool lock sorunlari gorulebiliyor.
    # NullPool kullanarak her istek icin temiz baglanti ac/kapat yapariz.
    from sqlalchemy.pool import NullPool
    engine_options['poolclass'] = NullPool
    engine_options.pop('pool_size', None)
    engine_options.pop('max_overflow', None)
    engine_options.pop('pool_timeout', None)
    engine_options.setdefault('pool_recycle', 1800)
else:
    # SQLite için StaticPool (tek connection, lock contention önler)
    from sqlalchemy.pool import StaticPool
    engine_options['poolclass'] = StaticPool
    connect_args = dict(engine_options.get('connect_args') or {})
    connect_args.setdefault('check_same_thread', False)
    connect_args.setdefault('timeout', 30)  # 30 saniye lock timeout
    engine_options['connect_args'] = connect_args

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options

realtime.socketio = SocketIO(
    app,
    cors_allowed_origins=Config.CORS_ORIGINS,
    async_mode='gevent',
    engineio_logger=False,
    logger=False,
    always_connect=True,
)
socketio = realtime.socketio

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


def _is_internal_or_socket_request():
    if request.path.startswith('/socket.io'):
        return True

    remote = request.remote_addr or ''
    try:
        addr = ipaddress.ip_address(remote)
        return addr.is_private or addr.is_loopback
    except ValueError:
        return False


limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[],
    default_limits_exempt_when=_is_internal_or_socket_request,
    storage_uri=os.getenv('RATELIMIT_STORAGE_URI', 'memory://'),  # production'da redis kullanılabilir
    swallow_errors=True,
)

# CSRF Protection
csrf = CSRFProtect(app)

from models import db
from models_crm import SessionActivity
from models_contact_timeline import ContactNote, ContactActivityLog
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
from routes.calendar import calendar_bp
from routes.notifications import notifications_bp
from routes import custom_fields as custom_fields_route
from routes import team as team_route
from routes import assignments as assignments_route
from routes.scheduled_messages import scheduled_messages_bp
from routes.documents import documents_bp
from routes.email_hub import email_hub_bp
from routes.import_wizard import import_bp
from routes.pipeline_settings import pipeline_settings_bp
from routes.search import search_bp
from services import portal_notification_service  # noqa: F401
from services.security_service import SecurityService
from services.task_scheduler import TaskScheduler
from utils.exceptions import (
    AppException, ValidationError, NotFoundError, 
    UnauthorizedError, ForbiddenError, ConflictError,
    RateLimitError, ExternalServiceError
)

db.init_app(app)

# Auto-run migrations on startup (for Render free tier without shell access)
def run_migrations():
    """Run pending database migrations automatically on startup"""
    try:
        # Only run on PostgreSQL (production)
        if not str(app.config.get('SQLALCHEMY_DATABASE_URI', '')).startswith('sqlite'):
            logger.info("Checking for pending migrations...")
            
            # Import here to avoid circular imports
            import psycopg2
            from urllib.parse import urlparse
            
            database_url = app.config.get('SQLALCHEMY_DATABASE_URI')
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            
            conn = psycopg2.connect(database_url)
            cur = conn.cursor()
            
            # === DEAL_STAGES TABLE MIGRATIONS ===
            # Check if rotting_days column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='deal_stages' AND column_name='rotting_days'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add rotting_days column...")
                cur.execute("""
                    ALTER TABLE deal_stages 
                    ADD COLUMN rotting_days INTEGER DEFAULT NULL
                """)
                conn.commit()
                logger.info("✓ Added rotting_days column")
            
            # Check if is_active column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='deal_stages' AND column_name='is_active'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add is_active column...")
                cur.execute("""
                    ALTER TABLE deal_stages 
                    ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL
                """)
                conn.commit()
                logger.info("✓ Added is_active column")
            
            # === DEALS TABLE MIGRATIONS ===
            # Check if stage_entered_at column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='deals' AND column_name='stage_entered_at'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add stage_entered_at column...")
                cur.execute("""
                    ALTER TABLE deals 
                    ADD COLUMN stage_entered_at TIMESTAMP DEFAULT NOW() NOT NULL
                """)
                conn.commit()
                logger.info("✓ Added stage_entered_at column")
            
            # Check if is_deleted column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='deals' AND column_name='is_deleted'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add is_deleted column...")
                cur.execute("""
                    ALTER TABLE deals 
                    ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE NOT NULL
                """)
                conn.commit()
                logger.info("✓ Added is_deleted column")
            
            # Check if deleted_at column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='deals' AND column_name='deleted_at'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add deleted_at column...")
                cur.execute("""
                    ALTER TABLE deals 
                    ADD COLUMN deleted_at TIMESTAMP DEFAULT NULL
                """)
                conn.commit()
                logger.info("✓ Added deleted_at column")
            
            # Check if updated_at column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='deals' AND column_name='updated_at'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add updated_at column...")
                cur.execute("""
                    ALTER TABLE deals 
                    ADD COLUMN updated_at TIMESTAMP DEFAULT NOW()
                """)
                conn.commit()
                logger.info("✓ Added updated_at column")
            
            # Check if version column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='deals' AND column_name='version'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add version column...")
                cur.execute("""
                    ALTER TABLE deals 
                    ADD COLUMN version INTEGER DEFAULT 0 NOT NULL
                """)
                conn.commit()
                logger.info("✓ Added version column")
            
            # Check if closed_at column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='deals' AND column_name='closed_at'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add closed_at column...")
                cur.execute("""
                    ALTER TABLE deals 
                    ADD COLUMN closed_at TIMESTAMP DEFAULT NULL
                """)
                conn.commit()
                logger.info("✓ Added closed_at column")
            
            # Check if contact_id column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='deals' AND column_name='contact_id'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add contact_id column...")
                cur.execute("""
                    ALTER TABLE deals 
                    ADD COLUMN contact_id INTEGER REFERENCES contacts(id)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_deals_contact_id 
                    ON deals(contact_id)
                """)
                conn.commit()
                logger.info("✓ Added contact_id column to deals")
            
            # Check if next_step column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='deals' AND column_name='next_step'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add next_step column...")
                cur.execute("""
                    ALTER TABLE deals 
                    ADD COLUMN next_step VARCHAR(500)
                """)
                conn.commit()
                logger.info("✓ Added next_step column")
            
            # Check if next_step_due_at column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='deals' AND column_name='next_step_due_at'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add next_step_due_at column...")
                cur.execute("""
                    ALTER TABLE deals 
                    ADD COLUMN next_step_due_at TIMESTAMP
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_deals_next_step_due_at 
                    ON deals(next_step_due_at)
                """)
                conn.commit()
                logger.info("✓ Added next_step_due_at column")
            
            # Check if last_activity_at column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='deals' AND column_name='last_activity_at'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add last_activity_at column...")
                cur.execute("""
                    ALTER TABLE deals 
                    ADD COLUMN last_activity_at TIMESTAMP
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_deals_last_activity_at 
                    ON deals(last_activity_at)
                """)
                conn.commit()
                logger.info("✓ Added last_activity_at column")
            
            # Check if revenue_type column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='deals' AND column_name='revenue_type'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add revenue_type column...")
                cur.execute("""
                    ALTER TABLE deals 
                    ADD COLUMN revenue_type VARCHAR(20) DEFAULT 'one_time' NOT NULL
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_deals_revenue_type 
                    ON deals(revenue_type)
                """)
                conn.commit()
                logger.info("✓ Added revenue_type column")
            
            # Check if mrr column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='deals' AND column_name='mrr'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add mrr column...")
                cur.execute("""
                    ALTER TABLE deals 
                    ADD COLUMN mrr NUMERIC(12, 2) DEFAULT 0
                """)
                conn.commit()
                logger.info("✓ Added mrr column")
            
            # Check if arr column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='deals' AND column_name='arr'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add arr column...")
                cur.execute("""
                    ALTER TABLE deals 
                    ADD COLUMN arr NUMERIC(12, 2) DEFAULT 0
                """)
                conn.commit()
                logger.info("✓ Added arr column")
            
            # Check if renewal_date column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='deals' AND column_name='renewal_date'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add renewal_date column...")
                cur.execute("""
                    ALTER TABLE deals 
                    ADD COLUMN renewal_date DATE
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_deals_renewal_date 
                    ON deals(renewal_date)
                """)
                conn.commit()
                logger.info("✓ Added renewal_date column")
            
            # Check if churn_risk column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='deals' AND column_name='churn_risk'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add churn_risk column...")
                cur.execute("""
                    ALTER TABLE deals 
                    ADD COLUMN churn_risk VARCHAR(20) DEFAULT 'low' NOT NULL
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_deals_churn_risk 
                    ON deals(churn_risk)
                """)
                conn.commit()
                logger.info("✓ Added churn_risk column")
            
            # Check if forecast_category column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='deals' AND column_name='forecast_category'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add forecast_category column...")
                cur.execute("""
                    ALTER TABLE deals 
                    ADD COLUMN forecast_category VARCHAR(20) DEFAULT 'pipeline' NOT NULL
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_deals_forecast_category 
                    ON deals(forecast_category)
                """)
                conn.commit()
                logger.info("✓ Added forecast_category column")
            
            # Check if win_loss_reason_id column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='deals' AND column_name='win_loss_reason_id'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add win_loss_reason_id column...")
                cur.execute("""
                    ALTER TABLE deals 
                    ADD COLUMN win_loss_reason_id INTEGER REFERENCES win_loss_reasons(id)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_deals_win_loss_reason_id 
                    ON deals(win_loss_reason_id)
                """)
                conn.commit()
                logger.info("✓ Added win_loss_reason_id column")
            
            # === CONTACTS TABLE MIGRATIONS ===
            # Check if display_order column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='contacts' AND column_name='display_order'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add display_order column to contacts...")
                cur.execute("""
                    ALTER TABLE contacts 
                    ADD COLUMN display_order INTEGER DEFAULT 0 NOT NULL
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_contacts_display_order 
                    ON contacts(display_order)
                """)
                conn.commit()
                logger.info("✓ Added display_order column to contacts")
            
            # Check if is_starred column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='contacts' AND column_name='is_starred'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add is_starred column to contacts...")
                cur.execute("""
                    ALTER TABLE contacts 
                    ADD COLUMN is_starred BOOLEAN DEFAULT FALSE NOT NULL
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_contacts_is_starred 
                    ON contacts(is_starred)
                """)
                conn.commit()
                logger.info("✓ Added is_starred column to contacts")
            
            # Check if last_activity_at column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='contacts' AND column_name='last_activity_at'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add last_activity_at column to contacts...")
                cur.execute("""
                    ALTER TABLE contacts 
                    ADD COLUMN last_activity_at TIMESTAMP
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_contacts_last_activity_at 
                    ON contacts(last_activity_at)
                """)
                conn.commit()
                logger.info("✓ Added last_activity_at column to contacts")
            
            # === COMPANIES TABLE MIGRATIONS ===
            # Check if display_order column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='companies' AND column_name='display_order'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add display_order column to companies...")
                cur.execute("""
                    ALTER TABLE companies 
                    ADD COLUMN display_order INTEGER DEFAULT 0 NOT NULL
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_companies_display_order 
                    ON companies(display_order)
                """)
                conn.commit()
                logger.info("✓ Added display_order column to companies")
            
            # === SUPER_ADMINS TABLE MIGRATION ===
            # Check if super_admins table exists
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name='super_admins'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: create super_admins table...")
                cur.execute("""
                    CREATE TABLE super_admins (
                        id SERIAL PRIMARY KEY,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        name VARCHAR(100) NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        last_login TIMESTAMP,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                conn.commit()
                logger.info("✓ Created super_admins table")
            
            # Check if impersonate_logs table exists
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name='impersonate_logs'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: create impersonate_logs table...")
                cur.execute("""
                    CREATE TABLE impersonate_logs (
                        id SERIAL PRIMARY KEY,
                        super_admin_id INTEGER REFERENCES super_admins(id),
                        workspace_id INTEGER REFERENCES workspaces(id),
                        started_at TIMESTAMP DEFAULT NOW(),
                        ended_at TIMESTAMP,
                        ip_address VARCHAR(50)
                    )
                """)
                conn.commit()
                logger.info("✓ Created impersonate_logs table")
            
            # === USERS TABLE MIGRATIONS (Team Member System) ===
            # Check if is_active column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='users' AND column_name='is_active'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add is_active column to users...")
                cur.execute("""
                    ALTER TABLE users 
                    ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL
                """)
                conn.commit()
                logger.info("✓ Added is_active column to users")
            
            # Check if created_at column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='users' AND column_name='created_at'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add created_at column to users...")
                cur.execute("""
                    ALTER TABLE users 
                    ADD COLUMN created_at TIMESTAMP DEFAULT NOW()
                """)
                conn.commit()
                logger.info("✓ Added created_at column to users")
            
            # Check if last_login column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='users' AND column_name='last_login'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add last_login column to users...")
                cur.execute("""
                    ALTER TABLE users 
                    ADD COLUMN last_login TIMESTAMP DEFAULT NULL
                """)
                conn.commit()
                logger.info("✓ Added last_login column to users")
            
            # Check if deleted_at column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='users' AND column_name='deleted_at'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add deleted_at column to users...")
                cur.execute("""
                    ALTER TABLE users 
                    ADD COLUMN deleted_at TIMESTAMP DEFAULT NULL
                """)
                conn.commit()
                logger.info("✓ Added deleted_at column to users")
            
            # === TEAM_INVITATIONS TABLE ===
            # Check if team_invitations table exists
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name='team_invitations'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: create team_invitations table...")
                cur.execute("""
                    CREATE TABLE team_invitations (
                        id SERIAL PRIMARY KEY,
                        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                        email VARCHAR(255) NOT NULL,
                        role VARCHAR(50) NOT NULL DEFAULT 'member',
                        token VARCHAR(255) NOT NULL UNIQUE,
                        invited_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        invited_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        expires_at TIMESTAMP NOT NULL,
                        status VARCHAR(50) NOT NULL DEFAULT 'pending'
                    )
                """)
                conn.commit()
                logger.info("✓ Created team_invitations table")
            
            # === COMPANIES TABLE - assigned_to column ===
            # Check if assigned_to column exists in companies
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='companies' AND column_name='assigned_to'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add assigned_to column to companies...")
                cur.execute("""
                    ALTER TABLE companies 
                    ADD COLUMN assigned_to INTEGER REFERENCES users(id) ON DELETE SET NULL
                """)
                conn.commit()
                logger.info("✓ Added assigned_to column to companies")
            
            # === CONTACTS TABLE - assigned_to column ===
            # Check if assigned_to column exists in contacts (Customer table)
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='customers' AND column_name='assigned_to'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add assigned_to column to customers...")
                cur.execute("""
                    ALTER TABLE customers 
                    ADD COLUMN assigned_to INTEGER REFERENCES users(id) ON DELETE SET NULL
                """)
                conn.commit()
                logger.info("✓ Added assigned_to column to customers")
            
            # Check if assigned_to column exists in contacts table
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='contacts' AND column_name='assigned_to'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add assigned_to column to contacts...")
                cur.execute("""
                    ALTER TABLE contacts 
                    ADD COLUMN assigned_to INTEGER REFERENCES users(id) ON DELETE SET NULL
                """)
                conn.commit()
                logger.info("✓ Added assigned_to column to contacts")
            
            # === TAGS TABLE MIGRATION ===
            # Check if tags table exists
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name='tags'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: create tags table...")
                cur.execute("""
                    CREATE TABLE tags (
                        id SERIAL PRIMARY KEY,
                        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                        name VARCHAR(100) NOT NULL,
                        color VARCHAR(7) DEFAULT '#6366f1',
                        created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                        UNIQUE (workspace_id, name)
                    )
                """)
                cur.execute("""
                    CREATE INDEX idx_tags_workspace_id ON tags(workspace_id)
                """)
                conn.commit()
                logger.info("✓ Created tags table")
            
            # Check if contact_tags table exists
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name='contact_tags'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: create contact_tags table...")
                cur.execute("""
                    CREATE TABLE contact_tags (
                        id SERIAL PRIMARY KEY,
                        contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                        tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                        created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                        UNIQUE (contact_id, tag_id)
                    )
                """)
                cur.execute("""
                    CREATE INDEX idx_contact_tags_contact_id ON contact_tags(contact_id)
                """)
                cur.execute("""
                    CREATE INDEX idx_contact_tags_tag_id ON contact_tags(tag_id)
                """)
                conn.commit()
                logger.info("✓ Created contact_tags table")
            
            # === LEAD MANAGEMENT MIGRATIONS ===
            # Check if lead_source column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='contacts' AND column_name='lead_source'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add lead_source column to contacts...")
                cur.execute("""
                    ALTER TABLE contacts 
                    ADD COLUMN lead_source VARCHAR(100)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_contact_lead_source 
                    ON contacts(lead_source)
                """)
                conn.commit()
                logger.info("✓ Added lead_source column to contacts")
            
            # Check if lifecycle_stage column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='contacts' AND column_name='lifecycle_stage'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add lifecycle_stage column to contacts...")
                cur.execute("""
                    ALTER TABLE contacts 
                    ADD COLUMN lifecycle_stage VARCHAR(50) DEFAULT 'lead' NOT NULL
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_contact_lifecycle_stage 
                    ON contacts(lifecycle_stage)
                """)
                conn.commit()
                logger.info("✓ Added lifecycle_stage column to contacts")
            
            # Check if qualified_at column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='contacts' AND column_name='qualified_at'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add qualified_at column to contacts...")
                cur.execute("""
                    ALTER TABLE contacts 
                    ADD COLUMN qualified_at TIMESTAMP
                """)
                conn.commit()
                logger.info("✓ Added qualified_at column to contacts")
            
            # Check if converted_at column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='contacts' AND column_name='converted_at'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add converted_at column to contacts...")
                cur.execute("""
                    ALTER TABLE contacts 
                    ADD COLUMN converted_at TIMESTAMP
                """)
                conn.commit()
                logger.info("✓ Added converted_at column to contacts")
            
            # === CALENDAR TASK MANAGEMENT MIGRATIONS ===
            # Check if start_time column exists in tasks
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='tasks' AND column_name='start_time'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: add calendar fields to tasks...")
                cur.execute("""
                    ALTER TABLE tasks 
                    ADD COLUMN start_time TIMESTAMP
                """)
                conn.commit()
                logger.info("✓ Added start_time column to tasks")
            
            # Check if end_time column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='tasks' AND column_name='end_time'
            """)
            
            if not cur.fetchone():
                cur.execute("""
                    ALTER TABLE tasks 
                    ADD COLUMN end_time TIMESTAMP
                """)
                conn.commit()
                logger.info("✓ Added end_time column to tasks")
            
            # Check if timezone column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='tasks' AND column_name='timezone'
            """)
            
            if not cur.fetchone():
                cur.execute("""
                    ALTER TABLE tasks 
                    ADD COLUMN timezone VARCHAR(50) DEFAULT 'UTC' NOT NULL
                """)
                conn.commit()
                logger.info("✓ Added timezone column to tasks")
            
            # Check if task_type column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='tasks' AND column_name='task_type'
            """)
            
            if not cur.fetchone():
                cur.execute("""
                    ALTER TABLE tasks 
                    ADD COLUMN task_type VARCHAR(50) DEFAULT 'task' NOT NULL
                """)
                conn.commit()
                logger.info("✓ Added task_type column to tasks")
            
            # Check if contact_id column exists in tasks
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='tasks' AND column_name='contact_id'
            """)
            
            if not cur.fetchone():
                cur.execute("""
                    ALTER TABLE tasks 
                    ADD COLUMN contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL
                """)
                conn.commit()
                logger.info("✓ Added contact_id column to tasks")
            
            # Create indexes on tasks table
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_workspace_start_time 
                ON tasks(workspace_id, start_time)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_type 
                ON tasks(task_type)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_contact_id 
                ON tasks(contact_id)
            """)
            conn.commit()
            logger.info("✓ Created indexes on tasks table")
            
            # Check if task_notifications table exists
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name='task_notifications'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: create task_notifications table...")
                cur.execute("""
                    CREATE TABLE task_notifications (
                        id SERIAL PRIMARY KEY,
                        workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                        task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        notify_at TIMESTAMP NOT NULL,
                        message VARCHAR(500) NOT NULL,
                        notification_type VARCHAR(50) DEFAULT 'task_reminder' NOT NULL,
                        is_sent BOOLEAN DEFAULT FALSE NOT NULL,
                        sent_at TIMESTAMP,
                        is_read BOOLEAN DEFAULT FALSE NOT NULL,
                        read_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT NOW() NOT NULL
                    )
                """)
                conn.commit()
                logger.info("✓ Created task_notifications table")
                
                # Create indexes on task_notifications
                cur.execute("""
                    CREATE INDEX idx_notification_workspace_id 
                    ON task_notifications(workspace_id)
                """)
                cur.execute("""
                    CREATE INDEX idx_notification_task_id 
                    ON task_notifications(task_id)
                """)
                cur.execute("""
                    CREATE INDEX idx_notification_user_id 
                    ON task_notifications(user_id)
                """)
                cur.execute("""
                    CREATE INDEX idx_notification_notify_at 
                    ON task_notifications(notify_at)
                """)
                cur.execute("""
                    CREATE INDEX idx_notification_pending 
                    ON task_notifications(is_sent, notify_at)
                """)
                cur.execute("""
                    CREATE INDEX idx_notification_user_unread 
                    ON task_notifications(user_id, is_read)
                """)
                cur.execute("""
                    CREATE INDEX idx_notification_workspace_user 
                    ON task_notifications(workspace_id, user_id)
                """)
                conn.commit()
                logger.info("✓ Created indexes on task_notifications table")
            
            # Check if notification_preferences table exists
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name='notification_preferences'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: create notification_preferences table...")
                cur.execute("""
                    CREATE TABLE notification_preferences (
                        id SERIAL PRIMARY KEY,
                        workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        task_reminder_enabled BOOLEAN DEFAULT TRUE NOT NULL,
                        task_overdue_enabled BOOLEAN DEFAULT TRUE NOT NULL,
                        task_assigned_enabled BOOLEAN DEFAULT TRUE NOT NULL,
                        task_updated_enabled BOOLEAN DEFAULT FALSE NOT NULL,
                        reminder_minutes_before INTEGER DEFAULT 15 NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                        updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
                        UNIQUE (workspace_id, user_id)
                    )
                """)
                conn.commit()
                logger.info("✓ Created notification_preferences table")
                
                # Create indexes on notification_preferences
                cur.execute("""
                    CREATE INDEX idx_notification_pref_workspace_id 
                    ON notification_preferences(workspace_id)
                """)
                cur.execute("""
                    CREATE INDEX idx_notification_pref_user_id 
                    ON notification_preferences(user_id)
                """)
                conn.commit()
                logger.info("✓ Created indexes on notification_preferences table")
            
            # Check if search_logs table exists
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name='search_logs'
            """)
            
            if not cur.fetchone():
                logger.info("Running migration: create search_logs table...")
                cur.execute("""
                    CREATE TABLE search_logs (
                        id SERIAL PRIMARY KEY,
                        workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        search_query VARCHAR(500) NOT NULL,
                        search_type VARCHAR(50) NOT NULL,
                        entity_type VARCHAR(50),
                        results_count INTEGER DEFAULT 0 NOT NULL,
                        search_duration_ms INTEGER,
                        filters_applied TEXT,
                        clicked_result_id INTEGER,
                        clicked_result_type VARCHAR(50),
                        user_agent VARCHAR(500),
                        ip_address VARCHAR(45),
                        created_at TIMESTAMP DEFAULT NOW() NOT NULL
                    )
                """)
                conn.commit()
                logger.info("✓ Created search_logs table")
                
                # Create indexes on search_logs
                cur.execute("""
                    CREATE INDEX idx_search_logs_workspace_id 
                    ON search_logs(workspace_id)
                """)
                cur.execute("""
                    CREATE INDEX idx_search_logs_user_id 
                    ON search_logs(user_id)
                """)
                cur.execute("""
                    CREATE INDEX idx_search_logs_search_type 
                    ON search_logs(search_type)
                """)
                cur.execute("""
                    CREATE INDEX idx_search_logs_created_at 
                    ON search_logs(created_at)
                """)
                cur.execute("""
                    CREATE INDEX idx_search_logs_workspace_user 
                    ON search_logs(workspace_id, user_id)
                """)
                conn.commit()
                logger.info("✓ Created indexes on search_logs table")
            
            cur.close()
            conn.close()
            logger.info("✓ All migrations completed")
            
            # === LOGIN ATTEMPTS TABLE (BRUTE-FORCE PROTECTION) ===
            # Import and run the migration
            try:
                from migrations.add_login_attempts_table import upgrade as login_attempts_upgrade
                
                # Reconnect for this migration
                conn = psycopg2.connect(database_url)
                cur = conn.cursor()
                
                logger.info("Running migration: add login_attempts table...")
                login_attempts_upgrade(conn, cur)
                
                cur.close()
                conn.close()
                logger.info("✓ Login attempts migration completed")
            except Exception as e:
                logger.warning(f"Login attempts migration failed (may already exist): {e}")
            
    except Exception as e:
        logger.warning(f"Migration check failed (may be normal if already applied): {e}")

def create_default_pipelines():
    """Create default pipeline for workspaces that don't have one"""
    try:
        from models_crm import Pipeline, DealStage
        from sqlalchemy import text
        
        # Get all workspaces
        workspaces = db.session.execute(text("SELECT id FROM workspaces")).fetchall()
        
        for workspace in workspaces:
            workspace_id = workspace[0]
            
            # Check if workspace already has a pipeline
            existing = Pipeline.query.filter_by(workspace_id=workspace_id).first()
            if existing:
                continue
            
            # Create default pipeline
            pipeline = Pipeline(
                workspace_id=workspace_id,
                name='Sales Pipeline',
                is_default=True
            )
            db.session.add(pipeline)
            db.session.flush()
            
            # Create default stages
            stages = [
                {'name': 'Lead', 'order': 1, 'probability': 10, 'rotting_days': 7},
                {'name': 'Qualified', 'order': 2, 'probability': 25, 'rotting_days': 7},
                {'name': 'Proposal', 'order': 3, 'probability': 50, 'rotting_days': 14},
                {'name': 'Negotiation', 'order': 4, 'probability': 75, 'rotting_days': 14},
                {'name': 'Closed Won', 'order': 5, 'probability': 100, 'rotting_days': None},
                {'name': 'Closed Lost', 'order': 6, 'probability': 0, 'rotting_days': None}
            ]
            
            for stage_data in stages:
                stage = DealStage(
                    pipeline_id=pipeline.id,
                    name=stage_data['name'],
                    order=stage_data['order'],
                    probability=stage_data['probability'],
                    rotting_days=stage_data['rotting_days'],
                    is_active=True
                )
                db.session.add(stage)
            
            db.session.commit()
            logger.info(f"✓ Created default pipeline for workspace {workspace_id}")
            
    except Exception as e:
        logger.warning(f"Failed to create default pipelines: {e}")
        db.session.rollback()

def check_db_schema():
    """Check if database schema matches models - runs on every startup"""
    try:
        from sqlalchemy import inspect
        from models_crm import Deal, DealStage, Pipeline
        
        inspector = inspect(db.engine)
        issues = []
        
        # Check critical tables
        for table_name, model in [
            ('deals', Deal),
            ('deal_stages', DealStage),
            ('pipelines', Pipeline),
        ]:
            if not inspector.has_table(table_name):
                issues.append(f"TABLE MISSING: {table_name}")
                continue
            
            db_cols = {c['name'] for c in inspector.get_columns(table_name)}
            model_cols = {c.name for c in model.__table__.columns}
            missing = model_cols - db_cols
            
            if missing:
                issues.append(f"COLUMNS MISSING [{table_name}]: {missing}")
        
        if issues:
            for issue in issues:
                logger.critical(f"⚠️  SCHEMA MISMATCH: {issue}")
            logger.critical("⚠️  Run migrations or check auto-migration logs above")
        else:
            logger.info("✓ Schema validation: OK")
            
    except Exception as e:
        logger.warning(f"Schema check failed: {e}")

# Run migrations with app context
with app.app_context():
    try:
        run_migrations()
        create_default_pipelines()
        check_db_schema()
    except Exception as e:
        logger.error(f"Failed to run migrations: {e}")



@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()

app.register_blueprint(webhook.bp)
app.register_blueprint(api.bp)
app.register_blueprint(auth_route.bp)
app.register_blueprint(settings_route.bp)
app.register_blueprint(templates_route.bp)
app.register_blueprint(automation_route.bp)
app.register_blueprint(pipeline_route.bp)
app.register_blueprint(pipeline_settings_bp)
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
from routes.contacts_file_upload import contacts_files_bp
app.register_blueprint(contacts_files_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(notifications_bp)
app.register_blueprint(custom_fields_route.bp)
app.register_blueprint(scheduled_messages_bp)
app.register_blueprint(documents_bp)
app.register_blueprint(email_hub_bp)
app.register_blueprint(import_bp)
app.register_blueprint(team_route.bp)
app.register_blueprint(assignments_route.bp)
from routes.super_admin import bp as super_admin_bp
app.register_blueprint(super_admin_bp)
app.register_blueprint(search_bp)

# CSRF Exemptions for webhooks (external services)
csrf.exempt(webhook.bp)
csrf.exempt(telegram_bp)

# Initialize TaskScheduler for background jobs (notifications, overdue tasks)
TaskScheduler.init_scheduler(app)
atexit.register(TaskScheduler.shutdown)

# Login endpoint'ine rate limit uygula
try:
    app.view_functions['auth.login'] = limiter.limit(Config.RATELIMIT_LOGIN)(app.view_functions['auth.login'])
except Exception as exc:
    logger.error('Failed to attach login rate limiter: %s', exc)

# Global API rate limiting
@app.before_request
def apply_rate_limiting():
    """Apply rate limiting to all API endpoints"""
    # Skip non-API endpoints
    if not request.path.startswith('/api/'):
        return None
    
    # Skip internal requests
    if request.path.startswith('/socket.io'):
        return None
    
    # Skip webhook endpoints (they have their own rate limiting)
    if request.path.startswith('/webhook'):
        return None
    
    # Get rate limit based on HTTP method
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        limit = '100 per minute'
    elif request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        limit = '50 per minute'
    else:
        limit = '100 per minute'
    
    # Apply rate limit
    try:
        limiter.limit(limit)(lambda: None)()
    except Exception as e:
        logger.warning(f'Rate limit exceeded: {request.remote_addr} - {request.path}')
        return jsonify({
            'error': 'Rate limit exceeded. Please try again later.',
            'retry_after': 60
        }), 429
    
    return None


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
    if candidate_host in allowed_hosts:
        return None

    # Allow same-machine requests regardless of port (dev proxies, e.g. Windsurf preview)
    _localhost_ips = {'localhost', '127.0.0.1', '::1', '0.0.0.0'}
    candidate_ip = candidate_host.split(':')[0].lower()
    server_ip = request.host.split(':')[0].lower()
    if candidate_ip in _localhost_ips and server_ip in _localhost_ips:
        return None

    return jsonify({'error': 'CSRF validation failed'}), 403


@app.before_request
def enforce_active_session_timeout():
    # Skip auth check for login/logout pages and static files
    if not session.get('user_id'):
        return None

    if request.endpoint in {'auth.logout', 'auth.login_page', 'auth.login', 'auth.register', 'auth.register_page', 'static', 'landing'}:
        return None

    session_token = session.get('session_token')
    if not session_token:
        session.clear()
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Session expired'}), 401
        return redirect(url_for('auth.login_page'))

    try:
        row = SessionActivity.query.filter_by(session_token=session_token, is_active=True).first()
        if not row:
            session.clear()
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Session expired'}), 401
            return redirect(url_for('auth.login_page'))

        if row.expires_at:
            # Ensure both datetimes are timezone-aware for comparison
            expires_at_utc = row.expires_at.replace(tzinfo=UTC) if row.expires_at.tzinfo is None else row.expires_at
            if expires_at_utc < datetime.now(UTC):
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
    except Exception as e:
        logger.error(f'Session validation error: {e}')
        session.clear()
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Session error'}), 401
        return redirect(url_for('auth.login_page'))
    
    return None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('auth.login_page'))
        return f(*args, **kwargs)
    return decorated


# ============================================================================
# GLOBAL ERROR HANDLERS
# ============================================================================

@app.errorhandler(AppException)
def handle_app_exception(error):
    """Handle custom application exceptions"""
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    logger.error(f'{error.__class__.__name__}: {error.message}')
    return response


@app.errorhandler(ValidationError)
def handle_validation_error(error):
    """Handle validation errors"""
    return jsonify({'error': error.message}), 400


@app.errorhandler(NotFoundError)
def handle_not_found_error(error):
    """Handle not found errors"""
    return jsonify({'error': error.message}), 404


@app.errorhandler(UnauthorizedError)
def handle_unauthorized_error(error):
    """Handle unauthorized errors"""
    return jsonify({'error': error.message}), 401


@app.errorhandler(ForbiddenError)
def handle_forbidden_error(error):
    """Handle forbidden errors"""
    return jsonify({'error': error.message}), 403


@app.errorhandler(ConflictError)
def handle_conflict_error(error):
    """Handle conflict errors"""
    return jsonify({'error': error.message}), 409


@app.errorhandler(RateLimitError)
def handle_rate_limit_error(error):
    """Handle rate limit errors"""
    return jsonify({'error': error.message}), 429


@app.errorhandler(ExternalServiceError)
def handle_external_service_error(error):
    """Handle external service errors"""
    return jsonify({'error': error.message}), 502


@app.errorhandler(404)
def handle_404(error):
    """Handle 404 errors"""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Resource not found'}), 404
    return render_template('landing.html'), 404


@app.errorhandler(500)
def handle_500(error):
    """Handle 500 errors"""
    logger.error(f'Internal server error: {error}', exc_info=True)
    db.session.rollback()  # Rollback any failed transactions
    
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('landing.html'), 500


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    """Handle all unexpected errors"""
    logger.error(f'Unexpected error: {error}', exc_info=True)
    db.session.rollback()
    
    # Don't expose internal error details in production
    if Config.ENV == 'production':
        error_message = 'An unexpected error occurred'
    else:
        error_message = str(error)
    
    if request.path.startswith('/api/'):
        return jsonify({'error': error_message}), 500
    return render_template('landing.html'), 500


@app.route('/')
def landing():
    if session.get('user_id'):
        return render_template('index.html')
    return render_template('landing.html')


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


@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard page with dark theme"""
    stats = {
        'total_contacts': 0,
        'active_deals': 0,
        'monthly_revenue': 0,
        'pending_tasks': 0,
        'pipeline_discovery': 0,
        'pipeline_proposal': 0,
        'pipeline_negotiation': 0,
        'pipeline_closing': 0,
    }
    return render_template('dashboard.html', stats=stats, current_user=type('obj', (object,), {'name': session.get('user_name', 'User')})())


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


@app.route('/team')
@login_required
def team_page():
    return render_template('team.html')


@app.route('/analytics-dashboard')
@login_required
def analytics_dashboard():
    return render_template('analytics_dashboard.html')


with app.app_context():
    # SQLite için WAL mode ve PRAGMA ayarları (database is locked hatasını önler)
    from sqlalchemy import event
    
    @event.listens_for(db.engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """SQLite bağlantılarında WAL mode ve timeout ayarlarını etkinleştirir"""
        # Render/production ortaminda PostgreSQL kullanilir; PRAGMA sadece SQLite icindir.
        if db.engine.url.get_backend_name() != 'sqlite':
            return
        cursor = dbapi_connection.cursor()
        try:
            # Write-Ahead Logging: Eşzamanlı okuma/yazma desteği
            cursor.execute("PRAGMA journal_mode=WAL")
            # Synchronous mode: Performans/güvenlik dengesi
            cursor.execute("PRAGMA synchronous=NORMAL")
            # Busy timeout: Lock beklemesi (30 saniye)
            cursor.execute("PRAGMA busy_timeout=30000")
        finally:
            cursor.close()
    
    # Validate configuration
    errors, warnings = Config.validate()
    
    if errors:
        logger.error('❌ Configuration validation failed:')
        for error in errors:
            logger.error(f'  - {error}')
        raise RuntimeError('Configuration validation failed. Please check your environment variables.')
    
    if warnings:
        logger.warning('⚠️  Configuration warnings:')
        for warning in warnings:
            logger.warning(f'  - {warning}')
    
    logger.info('✅ Configuration validated successfully')
    
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
                if 'is_deleted' not in contact_cols:
                    conn.execute(text('ALTER TABLE contacts ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0'))
                    need_commit = True
                    logger.info('contacts.is_deleted column added')
                if 'deleted_at' not in contact_cols:
                    conn.execute(text('ALTER TABLE contacts ADD COLUMN deleted_at TIMESTAMP'))
                    need_commit = True
                    logger.info('contacts.deleted_at column added')

                r_companies = conn.execute(text('PRAGMA table_info(companies)'))
                company_cols = [row[1] for row in r_companies.fetchall()]
                if 'is_deleted' not in company_cols:
                    conn.execute(text('ALTER TABLE companies ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0'))
                    need_commit = True
                    logger.info('companies.is_deleted column added')
                if 'deleted_at' not in company_cols:
                    conn.execute(text('ALTER TABLE companies ADD COLUMN deleted_at TIMESTAMP'))
                    need_commit = True
                    logger.info('companies.deleted_at column added')

                r_deals = conn.execute(text('PRAGMA table_info(deals)'))
                deal_cols = [row[1] for row in r_deals.fetchall()]
                if 'is_deleted' not in deal_cols:
                    conn.execute(text('ALTER TABLE deals ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0'))
                    need_commit = True
                    logger.info('deals.is_deleted column added')
                if 'deleted_at' not in deal_cols:
                    conn.execute(text('ALTER TABLE deals ADD COLUMN deleted_at TIMESTAMP'))
                    need_commit = True
                    logger.info('deals.deleted_at column added')

                r_activities = conn.execute(text('PRAGMA table_info(activities)'))
                activity_cols = [row[1] for row in r_activities.fetchall()]
                if 'is_deleted' not in activity_cols:
                    conn.execute(text('ALTER TABLE activities ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0'))
                    need_commit = True
                    logger.info('activities.is_deleted column added')
                if 'deleted_at' not in activity_cols:
                    conn.execute(text('ALTER TABLE activities ADD COLUMN deleted_at TIMESTAMP'))
                    need_commit = True
                    logger.info('activities.deleted_at column added')

                r_notes = conn.execute(text('PRAGMA table_info(notes)'))
                notes_cols = [row[1] for row in r_notes.fetchall()]
                if 'is_internal' not in notes_cols:
                    conn.execute(text('ALTER TABLE notes ADD COLUMN is_internal BOOLEAN NOT NULL DEFAULT 0'))
                    conn.execute(text('CREATE INDEX IF NOT EXISTS idx_notes_is_internal ON notes(is_internal)'))
                    need_commit = True
                    logger.info('notes.is_internal column added')

                r_conv = conn.execute(text('PRAGMA table_info(conversations)'))
                conv_cols = [row[1] for row in r_conv.fetchall()]
                if 'public_id' not in conv_cols:
                    conn.execute(text('ALTER TABLE conversations ADD COLUMN public_id VARCHAR(36)'))
                    need_commit = True
                    logger.info('conversations.public_id column added')

                missing_public_ids = conn.execute(
                    text("SELECT id FROM conversations WHERE public_id IS NULL OR TRIM(public_id) = ''")
                ).fetchall()
                for row in missing_public_ids:
                    conn.execute(
                        text('UPDATE conversations SET public_id = :public_id WHERE id = :id'),
                        {'public_id': str(uuid.uuid4()), 'id': row[0]}
                    )
                    need_commit = True

                conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_public_id ON conversations(public_id)'))
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
                conn.execute(text('ALTER TABLE notes ADD COLUMN IF NOT EXISTS is_internal BOOLEAN NOT NULL DEFAULT FALSE'))
                conn.execute(text('ALTER TABLE contacts ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE'))
                conn.execute(text('ALTER TABLE contacts ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP'))
                conn.execute(text('ALTER TABLE companies ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE'))
                conn.execute(text('ALTER TABLE companies ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP'))
                conn.execute(text('ALTER TABLE deals ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE'))
                conn.execute(text('ALTER TABLE deals ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP'))
                conn.execute(text('ALTER TABLE activities ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE'))
                conn.execute(text('ALTER TABLE activities ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP'))
                conn.execute(text('ALTER TABLE conversations ADD COLUMN IF NOT EXISTS public_id VARCHAR(36)'))

                missing_public_ids = conn.execute(
                    text("SELECT id FROM conversations WHERE public_id IS NULL OR TRIM(public_id) = ''")
                ).fetchall()
                for row in missing_public_ids:
                    conn.execute(
                        text('UPDATE conversations SET public_id = :public_id WHERE id = :id'),
                        {'public_id': str(uuid.uuid4()), 'id': row[0]}
                    )

                conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_public_id ON conversations(public_id)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS idx_customers_telegram_chat_id ON customers(telegram_chat_id)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS idx_contacts_telegram_chat_id ON contacts(telegram_chat_id)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS idx_notes_is_internal ON notes(is_internal)'))
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
    
    # Auto-migration: User preferences table
    try:
        from sqlalchemy import text, inspect
        inspector = inspect(db.engine)
        
        # Check if user_preferences table exists
        if 'user_preferences' not in inspector.get_table_names():
            logger.info('🔄 Creating user_preferences table...')
            
            if uri.startswith('sqlite'):
                # SQLite syntax
                db.session.execute(text("""
                    CREATE TABLE user_preferences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        workspace_id INTEGER NOT NULL,
                        preference_key VARCHAR(100) NOT NULL,
                        preference_value TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id),
                        FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                        UNIQUE(user_id, workspace_id, preference_key)
                    )
                """))
            else:
                # PostgreSQL syntax
                db.session.execute(text("""
                    CREATE TABLE user_preferences (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        workspace_id INTEGER NOT NULL,
                        preference_key VARCHAR(100) NOT NULL,
                        preference_value TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id),
                        FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                        UNIQUE(user_id, workspace_id, preference_key)
                    )
                """))
            
            # Create indexes
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_preferences_user 
                ON user_preferences(user_id, workspace_id)
            """))
            
            db.session.commit()
            logger.info('✅ user_preferences table created successfully!')
        else:
            logger.info('✓ user_preferences table already exists')
            
    except Exception as e:
        logger.warning('User preferences migration skip: %s', e)
    
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


@app.route('/theme-preview')
def theme_preview():
    """Dark theme preview page"""
    return render_template('theme_preview.html')


@app.route('/health')
def health():
    """Simple health check endpoint"""
    return {'status': 'ok'}, 200


if __name__ == '__main__':
    socketio.run(app, debug=Config.DEBUG, port=int(os.getenv('PORT', 5000)), host='0.0.0.0')
