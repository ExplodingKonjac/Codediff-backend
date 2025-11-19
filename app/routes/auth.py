from flask import request, jsonify
from flask_restful import Resource
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity,
    set_access_cookies, set_refresh_cookies,
    unset_jwt_cookies
)
from app.models import User
from app.extensions import db
from app.exceptions import APIError
from werkzeug.security import check_password_hash

class Register(Resource):
    def options(self):
        """处理预检请求"""
        return '', 204
    
    def post(self):
        """用户注册"""
        data = request.get_json()
        
        if not data or not all(k in data for k in ('username', 'email', 'password')):
            raise APIError('Missing required fields', 400)
        
        # 检查用户名/邮箱是否已存在
        if User.query.filter_by(username=data['username']).first():
            raise APIError('Username already exists', 409)
        
        if User.query.filter_by(email=data['email']).first():
            raise APIError('Email already exists', 409)
        
        # 创建新用户
        user = User(
            username=data['username'],
            email=data['email'],
            ai_api_key=data.get('ai_api_key', ''),
            ai_api_url=data.get('ai_api_url', ''),
            ai_model=data.get('ai_model', '')
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()

        user_id = str(user.id)  # 转换为字符串

        # 生成令牌
        access_token = create_access_token(identity=user_id)
        refresh_token = create_refresh_token(identity=user_id)
        
        response_data = {
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token
        }

        response = jsonify(response_data)
        
        # 设置 cookies (可选)
        set_access_cookies(response, access_token)
        set_refresh_cookies(response, refresh_token)
        
        return response, 201


class Login(Resource):
    def options(self):
        return '', 204
    
    def post(self):
        """用户登录"""
        data = request.get_json()
        
        if not data or not all(k in data for k in ('identifier', 'password')):
            raise APIError('Missing credentials', 400)
        
        # 尝试按用户名或邮箱查找
        user = User.query.filter(
            (User.username == data['identifier']) | (User.email == data['identifier'])
        ).first()
        
        if not user or not user.check_password(data['password']):
            raise APIError('Invalid credentials', 401)
        
        # 更新最后登录时间
        user.last_login = db.func.current_timestamp()
        db.session.commit()

        user_id = str(user.id)
        
        # 生成令牌
        access_token = create_access_token(identity=user_id)
        refresh_token = create_refresh_token(identity=user_id)
        
        response_data = {
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token
        }
        
        response = jsonify(response_data)
        
        set_access_cookies(response, access_token)
        set_refresh_cookies(response, refresh_token)
        
        return response


class Logout(Resource):
    def options(self):
        return '', 204

    @jwt_required()
    def post(self):
        """用户登出"""
        response = jsonify({"message": "Logout successful"})
        unset_jwt_cookies(response)
        return response

    def options(self):
        return '', 204


class UserProfile(Resource):
    @jwt_required()
    def get(self):
        """获取当前用户信息"""
        current_user_id = get_jwt_identity()
        
        try:
            user_id = int(current_user_id)
        except (ValueError, TypeError):
            raise APIError('Invalid user ID', 401)
        
        user = User.query.get(user_id)
        if not user:
            raise APIError('User not found', 404)
        
        return user.to_dict()
    
    @jwt_required()
    def put(self):
        """更新当前用户信息"""
        current_user_id = get_jwt_identity()
        
        try:
            user_id = int(current_user_id)
        except (ValueError, TypeError):
            raise APIError('Invalid user ID', 401)
        
        user = User.query.get(user_id)
        if not user:
            raise APIError('User not found', 404)
        
        data = request.get_json()
        
        # 更新可修改字段
        if 'username' in data and data['username'] != user.username:
            if User.query.filter_by(username=data['username']).first():
                raise APIError('Username already exists', 409)
            user.username = data['username']
        
        if 'email' in data and data['email'] != user.email:
            if 'password' not in data:
                raise APIError('Current password is required', 400)
            if not user.check_password(data['password']):
                raise APIError('Current password is incorrect', 403)
            if User.query.filter_by(email=data['email']).first():
                raise APIError('Email already exists', 409)
            user.email = data['email']
        
        if 'ai_api_key' in data:
            user.ai_api_key = data['ai_api_key']
        
        if 'ai_api_url' in data:
            user.ai_api_url = data['ai_api_url']
        
        if 'ai_model' in data:
            user.ai_model = data['ai_model']
        
        if 'new_password' in data:
            if 'password' not in data:
                raise APIError('Current password is required', 400)
            if not user.check_password(data['password']):
                raise APIError('Current password is incorrect', 403)
            user.set_password(data['new_password'])
        
        db.session.commit()
        return user.to_dict()

# 蓝图注册
from flask import Blueprint
auth_bp = Blueprint('auth', __name__)
auth_bp.add_url_rule('/register', view_func=Register.as_view('register'))
auth_bp.add_url_rule('/login', view_func=Login.as_view('login'))
auth_bp.add_url_rule('/logout', view_func=Logout.as_view('logout'))
auth_bp.add_url_rule('/me', view_func=UserProfile.as_view('user_profile'))