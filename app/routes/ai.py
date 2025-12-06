from flask import request, stream_with_context, Response
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import Session
from app.utils.ai_client import AIClient
from app.utils.sse import sse_response
from app.extensions import db
import logging

logger = logging.getLogger(__name__)
ai_client = AIClient()

class GenerateCode(Resource):
    @jwt_required()
    def post(self):
        current_user = int(get_jwt_identity())
        data = request.get_json()

        if not data or 'type' not in data or 'session_id' not in data:
            return {'error': 'invalid_request', 'message': 'Missing required fields'}, 400

        gen_type = data['type']  # 'generator' or 'standard'
        session_id = data['session_id']

        # 获取会话
        session = Session.query.get_or_404(session_id)
        if session.user_id != current_user:
            return {'error': 'forbidden', 'message': 'Not your session'}, 403

        # 获取用户AI配置
        user = session.user
        ai_config = {
            'api_key': user.ai_api_key,
            'api_url': user.ai_api_url,
            'ai_model': user.ai_model,
            'context': {
                'title': session.title,
                'description': session.description,
                'user_code': session.user_code.get('content') if session.user_code else None,
                'std_code': session.std_code.get('content') if session.std_code else None
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
            print(f"result: {result}")

            return {'generated_code': result, 'lang': 'cpp', 'std': 'c++20'}, 200

        except Exception as e:
            return {
                'error': 'ai_generation_failed',
                'message': str(e),
                'details': 'AI service might be unavailable or misconfigured'
            }, 503


class StreamGenerateCode(Resource):
    @jwt_required()
    def get(self):
        current_user = int(get_jwt_identity())

        if not request.args or 'type' not in request.args or 'session_id' not in request.args:
            return {'error': 'invalid_request', 'message': 'Missing required fields'}, 400

        gen_type = request.args['type']
        session_id = int(request.args['session_id'])

        # 获取会话
        session = Session.query.get_or_404(session_id)
        if session.user_id != current_user:
            return {'error': 'forbidden', 'message': 'Not your session'}, 403

        # 获取用户AI配置
        user = session.user
        if not user or not user.ai_api_key or not user.ai_api_url:
            return {'error': 'ai_config_missing', 'message': 'AI configuration is not set up'}, 400

        ai_config = {
            'api_key': user.ai_api_key,
            'api_url': user.ai_api_url,
            'ai_model': user.ai_model,
            'context': {
                'title': session.title,
                'description': session.description,
                'user_code': session.user_code.get('content') if session.user_code else None,
                'std_code': session.std_code.get('content') if session.std_code else None
            }
        }

        # 确定生成函数
        if gen_type == 'generator':
            generator_func = ai_client.generate_generator_stream
        elif gen_type == 'standard':
            generator_func = ai_client.generate_standard_stream
        else:
            return {'error': 'invalid_type', 'message': 'Invalid generation type'}, 400

        # 生成 SSE 流
        def generate_events():
            try:
                for event, data in generator_func(**ai_config):
                    if event == 'code_chunk':
                        yield sse_response(event, {'content': data})
                    elif event == 'error':
                        yield sse_response(event, {'message': data})
                    elif event == 'finish':
                        yield sse_response(event, {})

            except Exception as e:
                logger.error(f'Streaming generation failed: {str(e)}')
                yield sse_response('error', {'message': str(e)})

        return Response(
            stream_with_context(generate_events()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',  # 禁用 Nginx 缓冲
                'Access-Control-Allow-Origin': request.headers.get('Origin', '*'),
                'Access-Control-Allow-Credentials': 'true'
            }
        )


# 蓝图注册
from flask import Blueprint
ai_bp = Blueprint('ai', __name__)
ai_bp.add_url_rule('/generate', view_func=GenerateCode.as_view('generate_code'))
ai_bp.add_url_rule('/stream-generate', view_func=StreamGenerateCode.as_view('stream_generate_code'))
