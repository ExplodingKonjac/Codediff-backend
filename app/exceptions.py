from flask import jsonify, request
import logging
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)

class APIError(Exception):
    """自定义 API 异常"""
    def __init__(self, message, status_code=400, payload=None):
        self.message = message
        self.status_code = status_code
        self.payload = payload or {}

class ValidationError(APIError):
    """验证错误"""
    def __init__(self, errors, message="Validation failed"):
        super().__init__(message, 422, {'errors': errors})

class AuthenticationError(APIError):
    """认证错误"""
    def __init__(self, message="Authentication required"):
        super().__init__(message, 401)

class AuthorizationError(APIError):
    """授权错误"""
    def __init__(self, message="Not authorized"):
        super().__init__(message, 403)

class NotFoundError(APIError):
    """资源未找到"""
    def __init__(self, resource_type, resource_id=None):
        message = f'{resource_type} not found'
        if resource_id:
            message += f' (ID: {resource_id})'
        super().__init__(message, 404)

class RateLimitExceeded(APIError):
    """速率限制超出"""
    def __init__(self, limit, period):
        message = f'Rate limit exceeded. Maximum {limit} requests per {period}'
        super().__init__(message, 429)

class SandboxError(APIError):
    """沙箱执行错误"""
    def __init__(self, message, details=None):
        payload = {'details': details} if details else {}
        super().__init__(message, 500, payload)

class DiffError(APIError):
    """对拍错误"""
    def __init__(self, message, details=None):
        payload = {'details': details} if details else {}
        super().__init__(message, 500, payload)

def register_error_handlers(app):
    """注册全局错误处理器"""
    
    @app.errorhandler(APIError)
    def handle_api_error(error):
        """处理自定义 API 异常"""
        response = {
            'error': True,
            'message': error.message,
            'code': error.status_code,
            **error.payload
        }
        logger.error(f'API Error [{error.status_code}]: {error.message}')
        return jsonify(response), error.status_code
    
    from marshmallow.exceptions import ValidationError as MarshmallowValidationError
    
    @app.errorhandler(MarshmallowValidationError)
    def handle_marshmallow_validation_error(error):
        """处理 Marshmallow 验证错误"""
        # error.messages 是一个字典，包含字段和对应的错误列表
        return handle_api_error(ValidationError(error.messages, "Validation failed"))
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        """处理 HTTP 异常"""
        # 特别处理 422 Unprocessable Entity
        if error.code == 422:
            # 尝试获取验证错误详情
            if hasattr(error, 'data') and 'messages' in error.data:
                errors = error.data['messages']
                return handle_api_error(ValidationError(errors, "Validation failed"))
        
        response = {
            'error': True,
            'message': error.description,
            'code': error.code
        }
        logger.error(f'HTTP Exception [{error.code}]: {error.description}')
        return jsonify(response), error.code
    
    @app.errorhandler(404)
    def handle_not_found(error):
        """处理 404 Not Found"""
        response = {
            'error': True,
            'message': 'Resource not found',
            'code': 404,
            'path': request.path
        }
        logger.warning(f'404 Not Found: {request.path}')
        return jsonify(response), 404
    
    @app.errorhandler(429)
    def handle_rate_limit(error):
        """处理速率限制错误"""
        response = {
            'error': True,
            'message': 'Too many requests',
            'code': 429,
            'retry_after': error.retry_after if hasattr(error, 'retry_after') else 60
        }
        logger.warning(f'Rate limit exceeded from {request.remote_addr}')
        return jsonify(response), 429
    
    @app.errorhandler(500)
    def handle_server_error(error):
        """处理服务器内部错误"""
        response = {
            'error': True,
            'message': 'Internal server error',
            'code': 500,
            'request_id': request.headers.get('X-Request-ID', 'unknown')
        }
        
        # 详细日志 (不暴露给客户端)
        logger.exception(f'Server Error: {str(error)}')
        logger.error(f'Request: {request.method} {request.path}')
        logger.error(f'Headers: {dict(request.headers)}')
        logger.error(f'Body: {request.get_data(as_text=True)}')
        
        return jsonify(response), 500
    
    @app.errorhandler(Exception)
    def handle_generic_exception(error):
        """处理未捕获的异常"""
        logger.exception(f'Unhandled Exception: {str(error)}')
        
        response = {
            'error': True,
            'message': 'An unexpected error occurred',
            'code': 500,
            'request_id': request.headers.get('X-Request-ID', 'unknown')
        }
        
        return jsonify(response), 500
    
    # 添加请求ID中间件
    @app.before_request
    def add_request_id():
        """为每个请求添加唯一ID"""
        import uuid
        request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
        request.environ['X-Request-ID'] = request_id
        logger.info(f'Request [{request_id}] {request.method} {request.path}')
    
    # 添加响应日志
    @app.after_request
    def log_response(response):
        """记录响应信息"""
        request_id = request.environ.get('X-Request-ID', 'unknown')
        logger.info(f'Response [{request_id}] {response.status_code} {request.path}')
        response.headers['X-Request-ID'] = request_id
        return response