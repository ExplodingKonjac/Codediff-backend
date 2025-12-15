from marshmallow import Schema, fields, validate

class SendVerificationCodeSchema(Schema):
    email = fields.String(required=True, validate=validate.Email())

class RegisterSchema(Schema):
    username = fields.String(required=True, validate=validate.Length(min=3, max=80))
    email = fields.String(required=True, validate=validate.Email())
    password = fields.String(required=True, validate=validate.Length(min=6))
    verification_code = fields.String(required=True, validate=validate.Length(equal=6))
    
    ai_api_key = fields.String(load_default='')
    ai_api_url = fields.String(load_default='')
    ai_model = fields.String(load_default='')
    ocr_api_key = fields.String(load_default='')
    ocr_api_url = fields.String(load_default='')
    ocr_model = fields.String(load_default='')

class LoginSchema(Schema):
    identifier = fields.String(required=True)
    password = fields.String(required=True)
    remember = fields.Boolean(load_default=False)

class UserProfileUpdateSchema(Schema):
    username = fields.String(validate=validate.Length(min=3, max=80))
    email = fields.Email()
    password = fields.String() # Current password (required for sensitive changes)
    new_password = fields.String(validate=validate.Length(min=6))
    verification_code = fields.String(validate=validate.Length(equal=6))
    
    ai_api_key = fields.String()
    ai_api_url = fields.String()
    ai_model = fields.String()
    ocr_api_key = fields.String()
    ocr_api_url = fields.String()
    ocr_model = fields.String()
