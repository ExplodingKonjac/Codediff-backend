from flask import request
from flask_restful import Resource
from app.models import User
from app.extensions import db
from app.exceptions import APIError, NotFoundError, AuthorizationError
from app.utils.decorators import admin_required, root_required
from app.schemas.admin import UserListQuerySchema, UserUpdateSchema
from flask_login import current_user


class UserList(Resource):
    @admin_required
    def get(self):
        """List all users"""
        schema = UserListQuerySchema()
        args = schema.load(request.args)
        
        page = args['page']
        per_page = args['per_page']
        search = args.get('search')
        sort_by = args['sort']
        order = args['order']
        
        query = User.query
        
        if search:
            query = query.filter(User.username.like(f'%{search}%') | User.email.like(f'%{search}%'))
        
        # Sorting
        if hasattr(User, sort_by):
            col = getattr(User, sort_by)
            query = query.order_by(col.asc() if order == 'asc' else col.desc())
        else:
            query = query.order_by(User.id.asc())
            
        pagination = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        users = [user.to_dict() for user in pagination.items]
        
        return {
            'users': users,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }


class UserDetail(Resource):
    @admin_required
    def put(self, user_id):
        """Modify user (Admin: reset password; Root: everything)"""
        user = User.query.get(user_id)
        if not user:
            raise NotFoundError('User', user_id)
            
        schema = UserUpdateSchema()
        data = schema.load(request.get_json())
        
        # Admin restrictions:
        # - Cannot modify other admins/root
        # - Can only reset password (cannot change role)
        if current_user.role == 'admin':
            if user.role in ['admin', 'root']:
                raise AuthorizationError("Cannot modify other administrators")
            
            if 'role' in data:
                raise AuthorizationError("Only root can change user roles")
                
            if 'password' in data:
                user.set_password(data['password'])
                
        # Root privileges:
        # - Can do anything
        elif current_user.role == 'root':
            if 'role' in data:
                # Prevent demoting self? or removing last root? 
                # For simplicity, allow root to do anything, but warn user in frontend.
                user.role = data['role']
                
            if 'password' in data:
                user.set_password(data['password'])
        
        db.session.commit()
        return user.to_dict()


from flask import Blueprint
admin_bp = Blueprint('admin', __name__)
admin_bp.add_url_rule('/users', view_func=UserList.as_view('user_list'))
admin_bp.add_url_rule('/users/<int:user_id>', view_func=UserDetail.as_view('user_detail'))
