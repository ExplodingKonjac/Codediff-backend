from marshmallow import Schema, fields, validate

class StreamGenerateCodeQuerySchema(Schema):
    type = fields.String(required=True, validate=validate.OneOf(['generator', 'standard']))
    session_id = fields.Integer(required=True)
