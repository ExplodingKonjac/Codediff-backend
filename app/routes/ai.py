from flask import request, jsonify
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import Session
from app.utils.ai_client import AIClient
from app.extensions import db

ai_client = AIClient()

class GenerateCode(Resource):
    @jwt_required()
    def post(self):
        """AI 代码生成接口"""
        current_user = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'type' not in data or 'session_id' not in data:
            return {'error': 'invalid_request', 'message': 'Missing required fields'}, 400
        
        gen_type = data['type']  # 'generator' or 'standard'
        session_id = data['session_id']
        
        # 获取会话
        session = Session.query.get_or_404(session_id)
        if session.user_id != current_user['id']:
            return {'error': 'forbidden', 'message': 'Not your session'}, 403
        
        # 获取用户AI配置
        user = session.user
        ai_config = {
            'api_key': user.ai_api_key,
            'api_url': user.ai_api_url,
            'context': {
                'title': session.title,
                'description': session.description,
                'user_code': session.user_code.get('content', '') if session.user_code else '',
                'std_code': session.std_code.get('content', '') if session.std_code else ''
            }
        }
        
        try:
            # 调用AI生成
            if gen_type == 'generator':
                result = ai_client.generate_generator(**ai_config)
            elif gen_type == 'standard':
                result = ai_client.generate_standard(**ai_config)
            else:
                return {'error': 'invalid_type', 'message': 'Invalid generation type'}, 400
            
            return {
                'generated_code': result['code'],
                'language': result.get('language', 'cpp'),
                'confidence': result.get('confidence', 0.95)
            }, 200
            
        except Exception as e:
            return {
                'error': 'ai_generation_failed',
                'message': str(e),
                'details': 'AI service might be unavailable or misconfigured'
            }, 503

# 蓝图注册
from flask import Blueprint
ai_bp = Blueprint('ai', __name__)
ai_bp.add_url_rule('/generate', view_func=GenerateCode.as_view('generate_code'))
