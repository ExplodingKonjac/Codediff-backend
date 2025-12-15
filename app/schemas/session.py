from marshmallow import Schema, fields, validate

class CodeContentSchema(Schema):
    lang = fields.String(load_default='cpp')
    std = fields.String(load_default='c++17')
    content = fields.String(load_default='')

class SessionCreateSchema(Schema):
    title = fields.String(required=True, validate=validate.Length(min=1))
    description = fields.String(load_default='')
    user_code = fields.Nested(CodeContentSchema, required=True)
    std_code = fields.Nested(CodeContentSchema, required=True)
    gen_code = fields.Nested(CodeContentSchema, load_default=dict)

class SessionUpdateSchema(Schema):
    title = fields.String(validate=validate.Length(min=1))
    description = fields.String()
    user_code = fields.Nested(CodeContentSchema)
    std_code = fields.Nested(CodeContentSchema)
    gen_code = fields.Nested(CodeContentSchema)

class SessionListQuerySchema(Schema):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Integer(load_default=10, validate=validate.Range(min=1, max=100))
    sort = fields.String(load_default='updated_at', validate=validate.OneOf(['created_at', 'updated_at', 'title']))
    order = fields.String(load_default='desc', validate=validate.OneOf(['asc', 'desc']))
