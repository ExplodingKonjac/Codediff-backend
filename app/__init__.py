from flask import Flask, jsonify, request
from app.config import config
from app.extensions import init_extensions
from app.routes.auth import auth_bp
from app.routes.sessions import sessions_bp
from app.routes.diff import diff_bp
from app.routes.ai import ai_bp
from app.exceptions import register_error_handlers
import logging
import time

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # 配置日志
    logging.basicConfig(
        level=logging.INFO if app.config['DEBUG'] else logging.WARNING,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    app.logger.info(f"Starting application in {config_name} mode")
    
    # 初始化扩展
    init_extensions(app)
    
    # 注册 CLI 命令
    from app.commands import register_commands
    register_commands(app)
    
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
    
    # 调试端点：查看 CORS 配置
    @app.route('/debug/cors')
    def debug_cors():
        return jsonify({
            'cors_origins': app.config.get('CORS_ORIGINS'),
            'debug_mode': app.config.get('DEBUG'),
            'env': app.config.get('ENV'),
            'allowed_headers': [
                'Content-Type',
                'Authorization',
                'X-Requested-With',
                'Accept',
                'X-CSRF-Token',
                'X-XSRF-TOKEN'
            ]
        }), 200
    
    # CORS 预检请求处理
    @app.after_request
    def after_request(response):
        """统一处理响应头"""
        origin = request.headers.get('Origin')
        if origin:
            # 允许所有来源或配置的来源
            allowed_origins = app.config.get('CORS_ORIGINS', '*')
            if allowed_origins == '*' or origin in allowed_origins:
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Credentials'] = 'true'
        
        # 暴露必要的头部
        response.headers['Access-Control-Expose-Headers'] = 'Content-Type,Authorization,X-Requested-With'
        
        return response
    
    return app