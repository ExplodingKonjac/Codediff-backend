from flask_jwt_extended import decode_token
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
import logging

logger = logging.getLogger(__name__)

def decode_jwt_token(token):
    """
    解码 JWT 令牌，处理各种错误情况
    """
    try:
        decoded = decode_token(token)
        return decoded['sub']
    except ExpiredSignatureError:
        logger.warning("JWT token has expired")
        raise
    except InvalidTokenError as e:
        logger.error(f"Invalid JWT token: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error decoding JWT: {str(e)}")
        raise