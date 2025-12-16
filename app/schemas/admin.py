from marshmallow import Schema, fields, validate

class UserListQuerySchema(Schema):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Integer(load_default=10, validate=validate.Range(min=1, max=100))
    search = fields.String(load_default='')
    sort = fields.String(load_default='id', validate=validate.OneOf(['id', 'username', 'email', 'created_at', 'role']))
    order = fields.String(load_default='asc', validate=validate.OneOf(['asc', 'desc']))

class UserUpdateSchema(Schema):
    role = fields.String(validate=validate.OneOf(['user', 'admin']))
    password = fields.String(validate=validate.Length(min=6))
