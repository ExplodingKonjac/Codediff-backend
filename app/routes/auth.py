from flask import request, jsonify
from flask_restful import Resource
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User, VerificationCode
from app.extensions import db
from app.exceptions import APIError
from app.schemas.auth import SendVerificationCodeSchema, RegisterSchema, LoginSchema, UserProfileUpdateSchema
from app.utils.email_sender import send_verification_email
import random
from datetime import datetime, timedelta, timezone

class SendVerificationCode(Resource):
    def post(self):
        """发送验证码"""
        schema = SendVerificationCodeSchema()
        data = schema.load(request.get_json())
        
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
        schema = RegisterSchema()
        data = schema.load(request.get_json())
        
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
            ai_model=data.get('ai_model', ''),
            ocr_api_key=data.get('ocr_api_key', ''),
            ocr_api_url=data.get('ocr_api_url', ''),
            ocr_model=data.get('ocr_model', '')
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()

        # 注册成功后自动登录
        login_user(user)
        
        return {'user': user.to_dict(), 'message': 'Registration successful'}, 201


class Login(Resource):
    def options(self):
        return '', 204
    
    def post(self):
        """用户登录"""
        schema = LoginSchema()
        data = schema.load(request.get_json())
        
        # 尝试按用户名或邮箱查找
        user = User.query.filter(
            (User.username == data['identifier']) | (User.email == data['identifier'])
        ).first()
        
        if not user:
            raise APIError('Unknown user', 401)
        if not user.check_password(data['password']):
            raise APIError('Incorrect password', 401)
        
        # Flask-Login 登录
        remember = data.get('remember', False)
        if not login_user(user, remember=remember):
             raise APIError('Login failed', 400) # Should verify calling login_user
        
        return {'user': user.to_dict(), 'message': 'Login successful'}


class Logout(Resource):
    def options(self):
        return '', 204

    @login_required
    def post(self):
        """用户登出"""
        logout_user()
        return {"message": "Logout successful"}


class UserProfile(Resource):
    @login_required
    def get(self):
        """获取当前用户信息"""
        return current_user.to_dict()
    
    @login_required
    def put(self):
        """更新当前用户信息"""
        schema = UserProfileUpdateSchema()
        data = schema.load(request.get_json())
        user = current_user
        
        # 1. Handle Email Update (Verification Required)
        if 'email' in data and data['email'] != user.email:
            self._verify_sensitive_action(data, user)
            
            # 验证验证码
            if 'verification_code' not in data:
                raise APIError('Verification code is required', 400)
                
            ver_code = VerificationCode.query.filter_by(
                email=data['email'], 
                code=data['verification_code'],
                used=False
            ).order_by(VerificationCode.created_at.desc()).first()
            
            if not ver_code or not ver_code.is_valid():
                raise APIError('Invalid or expired verification code', 400)
            
            if User.query.filter_by(email=data['email']).first():
                raise APIError('Email already exists', 409)
                
            # 标记验证码已使用
            ver_code.used = True
            user.email = data['email']
        
        # 2. Handle Password Update
        if 'new_password' in data:
            self._verify_sensitive_action(data, user)
            user.set_password(data['new_password'])

        # 3. Handle Simple Fields Update
        simple_fields = [
            'ai_api_key', 'ai_api_url', 'ai_model', 
            'ocr_api_key', 'ocr_api_url', 'ocr_model'
        ]
        for field in simple_fields:
            if field in data:
                setattr(user, field, data[field])
        
        db.session.commit()
        return user.to_dict()

    def _verify_sensitive_action(self, data, user):
        """验证敏感操作所需的密码校验"""
        if 'password' not in data:
            raise APIError('Current password is required', 400)
        if not user.check_password(data['password']):
            raise APIError('Current password is incorrect', 403)


from flask import Blueprint
auth_bp = Blueprint('auth', __name__)
auth_bp.add_url_rule('/send-code', view_func=SendVerificationCode.as_view('send_code'))
auth_bp.add_url_rule('/register', view_func=Register.as_view('register'))
auth_bp.add_url_rule('/login', view_func=Login.as_view('login'))
auth_bp.add_url_rule('/logout', view_func=Logout.as_view('logout'))
auth_bp.add_url_rule('/me', view_func=UserProfile.as_view('user_profile'))
