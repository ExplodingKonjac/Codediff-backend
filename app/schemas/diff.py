from marshmallow import Schema, fields, validate

class StartDiffQuerySchema(Schema):
    max_tests = fields.Integer(load_default=100, validate=validate.Range(min=1, max=1000))
    checker = fields.String(load_default='wcmp')

class RerunDiffQuerySchema(Schema):
    checker = fields.String(load_default='wcmp')
