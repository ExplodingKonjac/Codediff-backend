from flask import Flask
from app.config import config
from app.extensions import init_extensions
from app.routes.auth import auth_bp
from app.routes.sessions import sessions_bp
from app.routes.diff import diff_bp
from app.routes.ai import ai_bp
from app.exceptions import register_error_handlers

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # 初始化扩展
    init_extensions(app)
    
    # 注册蓝图
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(sessions_bp, url_prefix='/api/sessions')
    app.register_blueprint(diff_bp, url_prefix='/api/diff')
    app.register_blueprint(ai_bp, url_prefix='/api/ai')
    
    # 注册错误处理器
    register_error_handlers(app)
    
    # 健康检查端点
    @app.route('/health')
    def health_check():
        return {'status': 'ok', 'timestamp': time.time()}, 200
    
    return app
