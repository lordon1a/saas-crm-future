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
    
    # CSRF Protection (Temporarily Disabled)
    WTF_CSRF_ENABLED = False
    WTF_CSRF_SECRET_KEY = os.getenv('CSRF_SECRET_KEY', SECRET_KEY)
    WTF_CSRF_TIME_LIMIT = 3600  # 1 saat
    WTF_CSRF_SSL_STRICT = ENV == 'production'
    WTF_CSRF_CHECK_DEFAULT = False
    
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

    # Facebook Lead Ads Integration
    FACEBOOK_APP_ID = os.getenv('FACEBOOK_APP_ID', '').strip()
    FACEBOOK_APP_SECRET = os.getenv('FACEBOOK_APP_SECRET', '').strip()
    FACEBOOK_REDIRECT_URI = os.getenv(
        'FACEBOOK_REDIRECT_URI',
        'http://127.0.0.1:5000/api/v1/integrations/facebook/callback'
    ).strip()
    FACEBOOK_OAUTH_SCOPES = os.getenv(
        'FACEBOOK_OAUTH_SCOPES',
        'leads_retrieval,pages_show_list,pages_manage_metadata'
    ).strip()

    # Google Ads Integration
    GOOGLE_ADS_CLIENT_ID = os.getenv('GOOGLE_ADS_CLIENT_ID', '').strip()
    GOOGLE_ADS_CLIENT_SECRET = os.getenv('GOOGLE_ADS_CLIENT_SECRET', '').strip()
    GOOGLE_ADS_REDIRECT_URI = os.getenv(
        'GOOGLE_ADS_REDIRECT_URI',
        'http://127.0.0.1:5000/api/v1/integrations/google-ads/callback'
    ).strip()
    GOOGLE_ADS_OAUTH_SCOPES = os.getenv(
        'GOOGLE_ADS_OAUTH_SCOPES',
        'https://www.googleapis.com/auth/adwords'
    ).strip()

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
    APP_BASE_URL = os.getenv('APP_BASE_URL', 'http://localhost:5000').rstrip('/')

    # Portal Email Notifications (optional SMTP)
    SMTP_HOST = os.getenv('SMTP_HOST')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USER = os.getenv('SMTP_USER')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
    SMTP_TLS = os.getenv('SMTP_TLS', '1').lower() in ('1', 'true', 'yes')
    SMTP_FROM_EMAIL = os.getenv('SMTP_FROM_EMAIL')
    # EMAIL_PROVIDER options: 'smtp' (default), 'gmail' (requires Google OAuth), 'log' (dev only)
    EMAIL_PROVIDER = os.getenv('EMAIL_PROVIDER', 'smtp').strip().lower()

    # Google Workspace Integration
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '').strip()
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '').strip()
    GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://127.0.0.1:5000/integrations/google/callback').strip()
    _google_scopes_raw = os.getenv(
        'GOOGLE_OAUTH_SCOPES',
        'openid,email,profile,https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.send,https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/drive.readonly'
    )
    GOOGLE_OAUTH_SCOPES = [scope.strip() for scope in _google_scopes_raw.split(',') if scope.strip()]
    GOOGLE_OAUTH_STATE_TTL_SECONDS = int(os.getenv('GOOGLE_OAUTH_STATE_TTL_SECONDS', '600'))
    GOOGLE_TOKEN_ENCRYPTION_KEY = os.getenv('GOOGLE_TOKEN_ENCRYPTION_KEY', '').strip()

    # QuickBooks Integration
    QUICKBOOKS_CLIENT_ID = os.getenv('QUICKBOOKS_CLIENT_ID', '').strip()
    QUICKBOOKS_CLIENT_SECRET = os.getenv('QUICKBOOKS_CLIENT_SECRET', '').strip()
    QUICKBOOKS_REDIRECT_URI = os.getenv('QUICKBOOKS_REDIRECT_URI', 'http://127.0.0.1:5000/integrations/quickbooks/callback').strip()
    QUICKBOOKS_SCOPES = [s.strip() for s in os.getenv('QUICKBOOKS_SCOPES', 'com.intuit.quickbooks.accounting').split(',') if s.strip()]
    QUICKBOOKS_ENVIRONMENT = os.getenv('QUICKBOOKS_ENVIRONMENT', 'sandbox').strip().lower()
    QUICKBOOKS_MAX_RETRIES = int(os.getenv('QUICKBOOKS_MAX_RETRIES', '3'))

    # Google background sync worker
    GOOGLE_SYNC_ENABLED = os.getenv('GOOGLE_SYNC_ENABLED', '1').lower() in ('1', 'true', 'yes')
    GOOGLE_SYNC_INTERVAL_SECONDS = int(os.getenv('GOOGLE_SYNC_INTERVAL_SECONDS', '300'))
    GOOGLE_SYNC_GMAIL_MAX_RESULTS = int(os.getenv('GOOGLE_SYNC_GMAIL_MAX_RESULTS', '50'))
    GOOGLE_SYNC_CALENDAR_DAYS_BACK = int(os.getenv('GOOGLE_SYNC_CALENDAR_DAYS_BACK', '7'))
    GOOGLE_SYNC_CALENDAR_DAYS_FORWARD = int(os.getenv('GOOGLE_SYNC_CALENDAR_DAYS_FORWARD', '30'))

    # Document management storage
    DOCUMENT_MAX_SIZE_MB = int(os.getenv('DOCUMENT_MAX_SIZE_MB', '50'))
    DOCUMENT_STORAGE_BACKEND = os.getenv('DOCUMENT_STORAGE_BACKEND', 'local').strip().lower()
    DOCUMENT_LOCAL_BASE_DIR = os.getenv('DOCUMENT_LOCAL_BASE_DIR', os.path.join('uploads', 'documents'))
    DOCUMENT_S3_ENDPOINT_URL = os.getenv('DOCUMENT_S3_ENDPOINT_URL', '').strip()
    DOCUMENT_S3_REGION = os.getenv('DOCUMENT_S3_REGION', 'us-east-1').strip()
    DOCUMENT_S3_BUCKET = os.getenv('DOCUMENT_S3_BUCKET', '').strip()
    DOCUMENT_S3_ACCESS_KEY = os.getenv('DOCUMENT_S3_ACCESS_KEY', '').strip()
    DOCUMENT_S3_SECRET_KEY = os.getenv('DOCUMENT_S3_SECRET_KEY', '').strip()

    # Medya: indirilen/gönderilen dosyaların saklanacağı klasör
    MEDIA_UPLOAD_FOLDER = os.getenv('MEDIA_UPLOAD_FOLDER', 'uploads')
    
    @classmethod
    def validate(cls):
        """Validate required configuration variables"""
        errors = []
        
        # Always required
        if not cls.SECRET_KEY or len(cls.SECRET_KEY) < 16:
            errors.append('SECRET_KEY must be at least 16 characters')
        
        if not cls.DATABASE_URL:
            errors.append('DATABASE_URL is required')
        
        # Production-specific requirements
        if cls.ENV == 'production':
            if cls.SECRET_KEY in ('dev-secret-key-change-in-production', 'dev-secret-key', 'change-me'):
                errors.append('SECRET_KEY must be changed in production')
            
            if len(cls.SECRET_KEY) < 32:
                errors.append('SECRET_KEY must be at least 32 characters in production')
            
            if '*' in cls.CORS_ORIGINS:
                errors.append('CORS_ORIGINS cannot contain "*" in production')
            
            if not cls.SESSION_COOKIE_SECURE:
                errors.append('SESSION_COOKIE_SECURE must be True in production')
        
        # Warn about missing optional configs
        warnings = []
        
        if not cls.WHATSAPP_TOKEN:
            warnings.append('WHATSAPP_TOKEN not set - WhatsApp features will not work')
        
        if not cls.WHATSAPP_PHONE_NUMBER_ID:
            warnings.append('WHATSAPP_PHONE_NUMBER_ID not set - WhatsApp features will not work')
        
        if not cls.WEBHOOK_VERIFY_TOKEN:
            warnings.append('WEBHOOK_VERIFY_TOKEN not set - Webhook verification will fail')
        
        return errors, warnings
