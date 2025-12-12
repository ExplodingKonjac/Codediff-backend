import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # 基础配置
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-please-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    ENV = os.getenv('FLASK_ENV', 'development')

    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'sqlite:///' + os.path.join(os.path.dirname(__file__), 'app.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 沙箱配置
    SANDBOX_EXECUTABLE = os.getenv('SANDBOX_EXECUTABLE', 'bwrap')
    RLIMIT_WRAPPER_EXECUTABLE = os.getenv('RLIMIT_WRAPPER_EXECUTABLE', './tools/rlimit_wrapper')
    CHECKER_EXECUTABLE_PREFIX = os.getenv('CHECKER_EXECUTABLE_PREFIX', './tools/checkers/')
    TESTLIB_PATH = os.getenv('TESTLIB_PATH', './tools/testlib.h')
    
    PROG_TIME_LIMIT = int(os.getenv('PROG_TIME_LIMIT', '5'))  # 秒
    PROG_MEMORY_LIMIT = int(os.getenv('PROG_MEMORY_LIMIT', '256')) # MB
    PROG_OUTPUT_LIMIT = int(os.getenv('PROG_OUTPUT_LIMIT', '16')) # KB

    COMPILER_TIME_LIMIT = int(os.getenv('MAX_COMPILER_EXEC_TIME', '15'))  # 秒
    COMPILER_MEMORY_LIMIT = int(os.getenv('MAX_COMPILER_EXEC_MEM', '512')) # MB
    COMPILER_OUTPUT_LIMIT = int(os.getenv('MAX_COMPILER_EXEC_OUTPUT', '16384')) # KB
    
    CHECKER_TIME_LIMIT = int(os.getenv('MAX_COMPILER_EXEC_TIME', '2'))  # 秒
    CHECKER_MEMORY_LIMIT = int(os.getenv('MAX_COMPILER_EXEC_MEM', '256')) # MB
    CHECKER_OUTPUT_LIMIT = int(os.getenv('MAX_COMPILER_EXEC_OUTPUT', '16')) # KB

    # AI 配置
    AI_TIMEOUT = int(os.getenv('AI_TIMEOUT', '60'))  # 秒
    
    SYSTEM_AI_API_KEY = os.getenv('SYSTEM_AI_API_KEY')
    SYSTEM_AI_API_URL = os.getenv('SYSTEM_AI_API_URL')
    SYSTEM_AI_MODEL = os.getenv('SYSTEM_AI_MODEL')

    # 邮件配置
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.getenv('MAIL_PORT', '8025'))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'false').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')

class DevelopmentConfig(Config):
    DEBUG = True
    PROPAGATE_EXCEPTIONS = True
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

class ProductionConfig(Config):
    DEBUG = False
    # 生产环境额外配置
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True
    }

    SESSION_COOKIE_SECURE = True

config: dict[str, type[Config]] = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
