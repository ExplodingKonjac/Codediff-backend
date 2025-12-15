from flask import request, current_app, stream_with_context, Response
from flask_restful import Resource
from flask_login import login_required, current_user
from PIL import Image
from app.models import Session
from app.exceptions import APIError, AuthorizationError
from app.schemas.ai import StreamGenerateCodeQuerySchema
from app.utils.ai_client import CodeGenerationClient, OCRClient
from app.utils.sse import sse_response
import logging

logger = logging.getLogger(__name__)


class StreamGenerateCode(Resource):
    @login_required
    def get(self):
        # Validate query params (Will raise ValidationError handled globally)
        schema = StreamGenerateCodeQuerySchema()
        args = schema.load(request.args)
        # Note: session_id is validated as integer by schema
        
        gen_type = args['type']
        session_id = args['session_id']

        def generate_events():
            try:
                yield from self.generate(gen_type, session_id)
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
    
    def generate(self, gen_type, session_id):
        user_id = current_user.id

        # 获取会话
        session = Session.query.get_or_404(session_id)
        if session.user_id != user_id:
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
        
        code_generation_client = CodeGenerationClient(api_key, api_url, ai_model)
        context = {
            'title': session.title,
            'description': session.description,
            'user_code': session.user_code.get('content') if session.user_code else None,
            'std_code': session.std_code.get('content') if session.std_code else None
        }

        # 确定生成函数
        if gen_type == 'generator':
            generator_func = code_generation_client.generate_generator_stream
        elif gen_type == 'standard':
            generator_func = code_generation_client.generate_standard_stream
        else:
            raise APIError("Invalid generation type")

        for data in generator_func(context):
            yield sse_response('chunk', {'content': data})
        yield sse_response('finish', {})


class StreamOCR(Resource):
    @login_required
    def post(self):
        def generate_events():
            try:
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
                
                if not current_user.ocr_api_key or not current_user.ocr_api_url or not current_user.ocr_api_model:
                    api_key = current_app.config['SYSTEM_OCR_API_KEY']
                    api_url = current_app.config['SYSTEM_OCR_API_URL']
                    ai_model = current_app.config['SYSTEM_OCR_API_MODEL']
                else:
                    api_key = current_user.ocr_api_key
                    api_url = current_user.ocr_api_url
                    ai_model = current_user.ocr_api_model

                ocr_client = OCRClient(api_key, api_url, ai_model)
                
                # Put PIL Image in memory to safely stream response
                img = Image.open(file)
                img.load() # Ensure image is loaded

                for content in ocr_client.perform_ocr_stream(img):
                    yield sse_response('chunk', {'content': content})
                yield sse_response('finish', {})

            except Exception as e:
                logger.error(f'Streaming OCR failed: {str(e)}')
                yield sse_response('error', {'message': str(e)})

        return Response(
            stream_with_context(generate_events()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',
                'Access-Control-Allow-Origin': request.headers.get('Origin', '*'),
                'Access-Control-Allow-Credentials': 'true'
            }
        )


# 蓝图注册
from flask import Blueprint
ai_bp = Blueprint('ai', __name__)
ai_bp.add_url_rule('/stream-generate', view_func=StreamGenerateCode.as_view('stream_generate_code'))
ai_bp.add_url_rule('/stream-ocr', view_func=StreamOCR.as_view('stream_ocr'))
