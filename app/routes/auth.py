from flask import request, jsonify
from flask_restful import Resource
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity,
    set_access_cookies, set_refresh_cookies,
    unset_jwt_cookies
)
from app.models import User, VerificationCode
from app.extensions import db
from app.exceptions import APIError
from app.utils.email_sender import send_verification_email
import random
from datetime import datetime, timedelta, timezone

class SendVerificationCode(Resource):
    def post(self):
        """发送验证码"""
        data = request.get_json()
        if not data or 'email' not in data:
            raise APIError('Email is required', 400)
            
        email = data['email']
        
        # 检查邮箱是否已被注册
        if User.query.filter_by(email=email).first():
            raise APIError('Email already registered', 409)
            
        # 生成6位验证码
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        # 保存到数据库
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        ver_code = VerificationCode(email=email, code=code, expires_at=expires_at)
        db.session.add(ver_code)
        db.session.commit()
        
        # 发送邮件
        if send_verification_email(email, code):
            return {'message': 'Verification code sent'}, 200
        else:
            raise APIError('Failed to send verification email', 500)


class Register(Resource):
    def options(self):
        """处理预检请求"""
        return '', 204
    
    def post(self):
        """用户注册"""
        data = request.get_json()
        
        required_fields = ('username', 'email', 'password', 'verification_code')
        if not data or not all(k in data for k in required_fields):
            raise APIError('Missing required fields', 400)
        
        # 验证验证码
        ver_code = VerificationCode.query.filter_by(
            email=data['email'], 
            code=data['verification_code'],
            used=False
        ).order_by(VerificationCode.created_at.desc()).first()
        
        if not ver_code or not ver_code.is_valid():
            raise APIError('Invalid or expired verification code', 400)
        
        # 检查用户名/邮箱是否已存在
        if User.query.filter_by(username=data['username']).first():
            raise APIError('Username already exists', 409)
        
        if User.query.filter_by(email=data['email']).first():
            raise APIError('Email already exists', 409)
        
        # 标记验证码为已使用
        ver_code.used = True
        
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
auth_bp.add_url_rule('/send-code', view_func=SendVerificationCode.as_view('send_code'))
auth_bp.add_url_rule('/register', view_func=Register.as_view('register'))
auth_bp.add_url_rule('/login', view_func=Login.as_view('login'))
auth_bp.add_url_rule('/logout', view_func=Logout.as_view('logout'))
auth_bp.add_url_rule('/me', view_func=UserProfile.as_view('user_profile'))