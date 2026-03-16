import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Environment
    ENV = os.getenv('FLASK_ENV', 'development').lower()
    DEBUG = os.getenv('FLASK_DEBUG', '1' if ENV == 'development' else '0').lower() in ('1', 'true', 'yes')

    # Database
    # PostgreSQL için Render/Heroku uyumluluğu: postgres:// -> postgresql://
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///whatsapp_crm.db')
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Production için optimize edilmiş connection pool
    if ENV == 'production' and 'postgresql://' in DATABASE_URL:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,      # Bağlantı sağlığını kontrol et
            'pool_recycle': 280,        # 4.5 dakikada bir bağlantıları yenile (Render timeout: 5dk)
            'pool_size': 5,             # Minimum connection pool size
            'max_overflow': 10,         # Maksimum ekstra bağlantı
            'pool_timeout': 30,         # Bağlantı bekleme timeout (saniye)
            'connect_args': {
                'connect_timeout': 10,  # PostgreSQL bağlantı timeout
                'options': '-c statement_timeout=30000'  # Query timeout: 30 saniye
            }
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
        }

    # Flask - Production'da SECRET_KEY zorunlu
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        if ENV == 'production':
            raise RuntimeError('SECRET_KEY environment variable must be set in production')
        SECRET_KEY = 'dev-secret-key-change-in-production'  # Sadece development için
    
    # Session ayarları
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = ENV == 'production'
    SESSION_COOKIE_SAMESITE = os.getenv(
        'SESSION_COOKIE_SAMESITE',
        'Strict' if ENV == 'production' else 'Lax'
    )
    PERMANENT_SESSION_LIFETIME = int(os.getenv('SESSION_LIFETIME_HOURS', '24')) * 3600  # Varsayılan: 24 saat

    # CORS: production'da belirli origin'ler verin (örn. https://app.example.com)
    _cors_origins_raw = os.getenv('CORS_ORIGINS', '*')
    CORS_ORIGINS = [origin.strip() for origin in _cors_origins_raw.split(',') if origin.strip()]

    # Rate limiting (login)
    RATELIMIT_LOGIN = os.getenv('RATELIMIT_LOGIN', '5 per minute')

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
    LOG_FILE = os.getenv('LOG_FILE', '')  # Örn. logs/app.log

    # Meta WhatsApp API
    WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
    WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID')
    WEBHOOK_VERIFY_TOKEN = os.getenv('WEBHOOK_VERIFY_TOKEN')

    # API Settings
    META_API_BASE_URL = 'https://graph.facebook.com/v18.0'
    PUBLIC_API_RATE_LIMIT_PER_HOUR = int(os.getenv('PUBLIC_API_RATE_LIMIT_PER_HOUR', '1000'))
    PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv('PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS', '3600'))
    WEBHOOK_TIMEOUT_SECONDS = int(os.getenv('WEBHOOK_TIMEOUT_SECONDS', '10'))
    WEBHOOK_RETRY_ATTEMPTS = int(os.getenv('WEBHOOK_RETRY_ATTEMPTS', '3'))
    WEBHOOK_RETRY_BASE_SECONDS = int(os.getenv('WEBHOOK_RETRY_BASE_SECONDS', '1'))
    WEBHOOK_SIGNATURE_HEADER = os.getenv('WEBHOOK_SIGNATURE_HEADER', 'X-WhatsAppCRM-Signature')

    # Customer Portal
    PORTAL_JWT_SECRET = os.getenv('PORTAL_JWT_SECRET', SECRET_KEY)
    PORTAL_JWT_EXP_HOURS = int(os.getenv('PORTAL_JWT_EXP_HOURS', '24'))
    PORTAL_BASE_URL = os.getenv('PORTAL_BASE_URL', 'http://localhost:5000/portal')

    # Portal Email Notifications (optional SMTP)
    SMTP_HOST = os.getenv('SMTP_HOST')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USER = os.getenv('SMTP_USER')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
    SMTP_TLS = os.getenv('SMTP_TLS', '1').lower() in ('1', 'true', 'yes')
    SMTP_FROM_EMAIL = os.getenv('SMTP_FROM_EMAIL')

    # Google Workspace Integration
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '').strip()
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '').strip()
    GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://127.0.0.1:5000/integrations/google/callback').strip()
    _google_scopes_raw = os.getenv(
        'GOOGLE_OAUTH_SCOPES',
        'openid,email,profile,https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/drive.readonly'
    )
    GOOGLE_OAUTH_SCOPES = [scope.strip() for scope in _google_scopes_raw.split(',') if scope.strip()]
    GOOGLE_OAUTH_STATE_TTL_SECONDS = int(os.getenv('GOOGLE_OAUTH_STATE_TTL_SECONDS', '600'))
    GOOGLE_TOKEN_ENCRYPTION_KEY = os.getenv('GOOGLE_TOKEN_ENCRYPTION_KEY', '').strip()

    # Medya: indirilen/gönderilen dosyaların saklanacağı klasör
    MEDIA_UPLOAD_FOLDER = os.getenv('MEDIA_UPLOAD_FOLDER', 'uploads')
