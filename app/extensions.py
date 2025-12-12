from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_cors import CORS
from flask_marshmallow import Marshmallow
import os
from flask import request, make_response

# 初始化扩展
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
ma = Marshmallow()

def init_extensions(app):
    """初始化所有 Flask 扩展"""
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    ma.init_app(app)
    
    # ========== 完整的 CORS 配置 ==========
    cors_origins = app.config.get('CORS_ORIGINS', '*')
    
    # 开发环境配置
    if app.config.get('DEBUG', False):
        cors_origins = [
            'http://localhost:5173',
            'http://localhost:5174',
            'http://127.0.0.1:5173',
            'http://127.0.0.1:5174'
        ]
    
    # 初始化 CORS
    CORS(app, 
         resources={r"/api/*": {"origins": cors_origins}},
         supports_credentials=True,
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept", "X-CSRF-Token"],
         max_age=86400)
