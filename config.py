import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'skillswap-mvp-default-secret-key-replace-in-prod')
    
    # Custom Non-Obvious Admin URL Configuration
    ADMIN_ROUTE_PREFIX = os.getenv('ADMIN_ROUTE_PREFIX', '/control-center-8f7b2a9d').strip()
    if not ADMIN_ROUTE_PREFIX.startswith('/'):
        ADMIN_ROUTE_PREFIX = '/' + ADMIN_ROUTE_PREFIX
    ADMIN_ROUTE_PREFIX = ADMIN_ROUTE_PREFIX.rstrip('/')

    # Security & Cookie Management (HttpOnly, SameSite, Secure flags)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() in ('true', '1')
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() in ('true', '1')
    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.getenv('SESSION_LIFETIME_HOURS', 8)))

    # Admin Login Rate Limiting & Account Lockout
    ADMIN_MAX_LOGIN_ATTEMPTS = int(os.getenv('ADMIN_MAX_LOGIN_ATTEMPTS', 5))
    ADMIN_LOCKOUT_MINUTES = int(os.getenv('ADMIN_LOCKOUT_MINUTES', 15))

    # SQLite default path inside instance/
    INSTANCE_PATH = BASE_DIR / 'instance'
    INSTANCE_PATH.mkdir(parents=True, exist_ok=True)
    
    database_url = os.getenv('DATABASE_URL', f"sqlite:///{INSTANCE_PATH / 'skillswap.db'}")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Platform settings
    DEFAULT_FREE_TRIAL_CREDITS = int(os.getenv('DEFAULT_FREE_TRIAL_CREDITS', 50))
    DEFAULT_COMMISSION_PERCENT = int(os.getenv('DEFAULT_COMMISSION_PERCENT', 20))
    CREDIT_TO_INR_RATE = float(os.getenv('CREDIT_TO_INR_RATE', 10.0))
    CANCELLATION_WINDOW_HOURS = int(os.getenv('CANCELLATION_WINDOW_HOURS', 2))
    
    # Payment Gateway
    RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', '').strip()
    RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', '').strip()
    ENABLE_PAYMENT_SIMULATOR = os.getenv('ENABLE_PAYMENT_SIMULATOR', 'True').lower() in ('true', '1', 'yes')

class DevelopmentConfig(Config):
    DEBUG = True

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    DEFAULT_FREE_TRIAL_CREDITS = 50
    DEFAULT_COMMISSION_PERCENT = 20

class ProductionConfig(Config):
    DEBUG = False

config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
