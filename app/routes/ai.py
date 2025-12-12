from flask import request, stream_with_context, Response, current_app
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
# from pix2text import Pix2Text
from tempfile import NamedTemporaryFile
from PIL import Image
from app.models import Session
from app.utils.ai_client import CodeGenerationClient, OCRClient
from app.utils.sse import sse_response
from app.exceptions import APIError, AuthorizationError
import logging

logger = logging.getLogger(__name__)
code_generation_client = CodeGenerationClient()
ocr_client = OCRClient()
# ocr_model = Pix2Text()

class GenerateCode(Resource):
    @jwt_required()
    def post(self):
        current_user = int(get_jwt_identity())
        data = request.get_json()

        if not data or 'type' not in data or 'session_id' not in data:
            raise APIError("Missing required fields")

        gen_type = data['type']  # 'generator' or 'standard'
        session_id = data['session_id']

        # 获取会话
        session = Session.query.get_or_404(session_id)
        if session.user_id != current_user:
            raise AuthorizationError("Not your session")

        # 获取用户AI配置
        user = session.user
        
        # Atomic fallback: if ANY user config is missing, use system config for ALL
        if user.ai_api_key and user.ai_api_url and user.ai_model:
            api_key = user.ai_api_key
            api_url = user.ai_api_url
            ai_model = user.ai_model
        else:
            api_key = current_app.config['SYSTEM_AI_API_KEY']
            api_url = current_app.config['SYSTEM_AI_API_URL']
            ai_model = current_app.config['SYSTEM_AI_MODEL']

        if not api_key or not api_url:
            raise APIError("AI configuration is missing (neither user nor system config found)")

        ai_config = {
            'api_key': api_key,
            'api_url': api_url,
            'ai_model': ai_model,
            'context': {
                'title': session.title,
                'description': session.description,
                'user_code': session.user_code.get('content') if session.user_code else None,
                'std_code': session.std_code.get('content') if session.std_code else None
            }
        }

        # 调用AI生成
        if gen_type == 'generator':
            result = code_generation_client.generate_generator(**ai_config)
        elif gen_type == 'standard':
            result = code_generation_client.generate_standard(**ai_config)
        else:
            raise APIError("Invalid generation type")

        return {'generated_code': result, 'lang': 'cpp', 'std': 'c++20'}, 200


class StreamGenerateCode(Resource):
    @jwt_required()
    def get(self):
        # 生成 SSE 流
        def generate_events():
            try:
                current_user = int(get_jwt_identity())

                if not request.args or 'type' not in request.args or 'session_id' not in request.args:
                    raise APIError("Missing required fields")

                gen_type = request.args['type']
                session_id = int(request.args['session_id'])

                # 获取会话
                session = Session.query.get_or_404(session_id)
                if session.user_id != current_user:
                    raise AuthorizationError("Not your session")

                # 获取用户AI配置
                user = session.user
                
                # Atomic fallback: if ANY user config is missing, use system config for ALL
                if user.ai_api_key and user.ai_api_url and user.ai_model:
                    api_key = user.ai_api_key
                    api_url = user.ai_api_url
                    ai_model = user.ai_model
                else:
                    api_key = current_app.config['SYSTEM_AI_API_KEY']
                    api_url = current_app.config['SYSTEM_AI_API_URL']
                    ai_model = current_app.config['SYSTEM_AI_MODEL']

                if not api_key or not api_url:
                    raise APIError("AI configuration is missing (neither user nor system config found)")

                ai_config = {
                    'api_key': api_key,
                    'api_url': api_url,
                    'ai_model': ai_model,
                    'context': {
                        'title': session.title,
                        'description': session.description,
                        'user_code': session.user_code.get('content') if session.user_code else None,
                        'std_code': session.std_code.get('content') if session.std_code else None
                    }
                }

                # 确定生成函数
                if gen_type == 'generator':
                    generator_func = code_generation_client.generate_generator_stream
                elif gen_type == 'standard':
                    generator_func = code_generation_client.generate_standard_stream
                else:
                    raise APIError("Invalid generation type")

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


class OCRProcessor(Resource):
    @jwt_required()
    def post(self):
        file = request.files.get('image')
        if not file or not file.filename:
            raise APIError("No image file provided", 400)
        
        # 验证文件类型
        allowed_extensions = {'png', 'jpg', 'jpeg', 'bmp', 'webp'}
        if not file.filename.rsplit('.', 1)[1].lower() in allowed_extensions:
            raise APIError("Invalid file type. Only image files are allowed", 400)
        
        # 验证文件大小 (最大 5MB)
        if file.content_length > 5 * 1024 * 1024:
            raise APIError("File too large. Maximum size is 5MB", 400)

        with NamedTemporaryFile('wb+', delete=True) as image_file:
            Image.open(file).save(image_file, format='JPEG')
            image_file.flush()
            return {'text': ocr_client.perform_ocr(image_file.name)}, 200

# 蓝图注册
from flask import Blueprint
ai_bp = Blueprint('ai', __name__)
ai_bp.add_url_rule('/generate', view_func=GenerateCode.as_view('generate_code'))
ai_bp.add_url_rule('/stream-generate', view_func=StreamGenerateCode.as_view('stream_generate_code'))
ai_bp.add_url_rule('/ocr', view_func=OCRProcessor.as_view('ocr_processor'))
