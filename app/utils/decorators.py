from functools import wraps
from flask_login import current_user
from app.exceptions import AuthorizationError

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            raise AuthorizationError("Authentication required")
        if current_user.role not in ['admin', 'root']:
            raise AuthorizationError("Admin privileges required")
        return f(*args, **kwargs)
    return decorated_function

def root_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            raise AuthorizationError("Authentication required")
        if current_user.role != 'root':
            raise AuthorizationError("Root privileges required")
        return f(*args, **kwargs)
    return decorated_function
