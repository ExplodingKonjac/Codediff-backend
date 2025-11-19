import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # 基础配置
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-please-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    ENV = os.getenv('FLASK_ENV', 'development')
    
    # 重要：设置 JWT 身份类型为字符串
    JWT_IDENTITY_CLAIM = 'sub'  # JWT 标准中的 subject 声明

    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'sqlite:///' + os.path.join(os.path.dirname(__file__), 'app.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT 配置
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key')
    JWT_ACCESS_TOKEN_EXPIRES = 3600  # 1小时
    JWT_REFRESH_TOKEN_EXPIRES = 2592000  # 30天
    
    # 沙箱配置
    SANDBOX_EXECUTABLE = os.getenv('SANDBOX_EXECUTABLE', 'bwrap')
    RLIMIT_WRAPPER_EXECUTABLE = os.getenv('RLIMIT_WRAPPER_EXECUTABLE', './tools/rlimit_wrapper')
    TESTLIB_PATH = os.getenv('TESTLIB_PATH', './tools/testlib.h')
    MAX_EXEC_TIME = int(os.getenv('MAX_EXEC_TIME', '5'))  # 秒
    MAX_MEMORY_MB = int(os.getenv('MAX_MEMORY_MB', '256'))
    
    # AI 配置
    DEFAULT_AI_MODEL = os.getenv('DEFAULT_AI_MODEL', 'gpt-4o')
    AI_TIMEOUT = int(os.getenv('AI_TIMEOUT', '60'))  # 秒

class DevelopmentConfig(Config):
    DEBUG = True
    PROPAGATE_EXCEPTIONS = True

class ProductionConfig(Config):
    DEBUG = False
    # 生产环境额外配置
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True
    }
    JWT_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
