from flask import request, jsonify
from flask_restful import Resource
from flask_login import login_required, current_user
from app.models import Session, TestCase
from app.extensions import db
from app.exceptions import APIError
from datetime import datetime, timezone
import logging
import json

class SessionList(Resource):
    @login_required
    def get(self):
        """获取用户所有会话 (元信息)"""
        user_id = current_user.id
        
        # 分页参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        sort_by = request.args.get('sort', 'updated_at')
        order = request.args.get('order', 'desc')
        
        # 构建查询
        query = Session.query.filter_by(user_id=user_id)
        
        # 排序
        if sort_by in ['created_at', 'updated_at', 'title']:
            if order == 'asc':
                query = query.order_by(getattr(Session, sort_by).asc())
            else:
                query = query.order_by(getattr(Session, sort_by).desc())
        
        # 分页
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # 构建响应
        sessions = [{
            'id': session.id,
            'title': session.title,
            'description': session.description[:100] + '...' if session.description and len(session.description) > 100 else session.description,
            'created_at': session.created_at.isoformat(),
            'updated_at': session.updated_at.isoformat(),
            'test_case_count': len(session.test_cases),
            'success_rate': self._calculate_success_rate(session.test_cases)
        } for session in pagination.items]
        
        return {
            'sessions': sessions,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }
    
    def _calculate_success_rate(self, test_cases):
        """计算成功率"""
        if not test_cases:
            return 0.0
        ac_count = sum(1 for tc in test_cases if tc.status == 'AC')
        return round((ac_count / len(test_cases)) * 100, 1)
    
    @login_required
    def post(self):
        """创建新会话"""
        user_id = current_user.id
        data = request.get_json()
        
        if not data or 'title' not in data:
            raise APIError('Title is required', 400)
        
        # 验证代码字段
        required_fields = ['user_code', 'std_code']
        for field in required_fields:
            if field not in data or not isinstance(data[field], dict) or 'content' not in data[field]:
                raise APIError(f'Invalid {field} format', 400)
        
        # 创建新会话
        session = Session(
            user_id=user_id,
            title=data['title'],
            description=data.get('description', ''),
            user_code={
                'lang': data['user_code'].get('lang', 'cpp'),
                'std': data['user_code'].get('std', 'c++17'),
                'content': data['user_code']['content']
            },
            std_code={
                'lang': data['std_code'].get('lang', 'cpp'),
                'std': data['std_code'].get('std', 'c++17'),
                'content': data['std_code']['content']
            }
        )
        
        # 可选字段
        if 'gen_code' in data and data['gen_code'] and 'content' in data['gen_code']:
            session.gen_code = {
                'lang': data['gen_code'].get('lang', 'cpp'),
                'std': data['gen_code'].get('std', 'c++17'),
                'content': data['gen_code']['content']
            }
        
        db.session.add(session)
        db.session.commit()
        
        return session.to_dict(), 201

class SessionDetail(Resource):
    @login_required
    def get(self, session_id):
        """获取会话详情"""
        user_id = current_user.id
        session = Session.query.get_or_404(session_id)
        
        if session.user_id != user_id:
            raise APIError('Not your session', 403)
        
        return session.to_dict(include_cases=True)
    
    @login_required
    def put(self, session_id):
        """更新会话"""
        user_id = current_user.id
        session = Session.query.get_or_404(session_id)
        
        if session.user_id != user_id:
            raise APIError('Not your session', 403)
        
        data = request.get_json()

        # 更新字段
        updatable_fields = ['title', 'description']
        for field in updatable_fields:
            if field in data:
                setattr(session, field, data[field])
        
        # 更新代码
        code_fields = ['user_code', 'gen_code', 'std_code']
        for field in code_fields:
            if field in data and isinstance(data[field], dict):
                current_value = getattr(session, field) or {}
                updated_value = {
                    'lang': data[field].get('lang', current_value.get('lang', 'cpp')),
                    'std': data[field].get('std', current_value.get('std', 'c++17')),
                    'content': data[field].get('content', current_value.get('content', ''))
                }
                setattr(session, field, updated_value)
        
        session.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        return session.to_dict()
    
    @login_required
    def delete(self, session_id):
        """删除会话"""
        user_id = current_user.id
        session = Session.query.get_or_404(session_id)
        
        if session.user_id != user_id:
            raise APIError('Not your session', 403)
        
        db.session.delete(session)
        db.session.commit()
        
        return {'message': 'Session deleted successfully'}, 200

# 蓝图注册
from flask import Blueprint
sessions_bp = Blueprint('sessions', __name__)
sessions_bp.add_url_rule('', view_func=SessionList.as_view('session_list'), strict_slashes=False)
sessions_bp.add_url_rule('/<int:session_id>', view_func=SessionDetail.as_view('session_detail'))
