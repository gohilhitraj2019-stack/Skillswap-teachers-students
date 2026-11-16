import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'skillswap-mvp-default-secret-key-replace-in-prod')
    
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
