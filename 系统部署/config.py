import os

# 获取项目根目录
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TEMPLATES_AUTO_RELOAD = True  # 自动重新加载模板
    
    # Database - 使用绝对路径
    db_path = os.path.join(BASE_DIR, "instance", "douyin_system.db")
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 
        f'sqlite:///{db_path}?check_same_thread=False&timeout=30')
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'check_same_thread': False,
            'timeout': 30
        },
        'pool_pre_ping': True
    }
    
    # Upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = 'uploads'
    
    # Session
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # LLM Configuration
    LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'ollama')  # ollama, openai, azure
    LLM_MODEL = os.environ.get('LLM_MODEL', 'qwen2.5:7b')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'http://localhost:11434')
    LLM_API_KEY = os.environ.get('LLM_API_KEY', '')

    # Mail Configuration (SMTP)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', '')
    
    # Public Platform Base URL
    PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', 'http://localhost:5001')


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    # Use PostgreSQL in production
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 
        'postgresql://user:password@localhost/douyin_system')


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
