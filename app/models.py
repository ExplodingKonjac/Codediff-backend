from datetime import datetime, timezone
from app.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
import logging

def _now_fn():
    return datetime.now(timezone.utc)

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    ai_api_key = db.Column(db.String(128))
    ai_api_url = db.Column(db.String(255))
    ai_model = db.Column(db.String(32))
    created_at = db.Column(db.DateTime, default=_now_fn)
    updated_at = db.Column(db.DateTime, default=_now_fn, onupdate=_now_fn)
    
    sessions = db.relationship('Session', backref='user', lazy=True, cascade="all, delete-orphan")
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'ai_api_key': self.ai_api_key,
            'ai_api_url': self.ai_api_url,
            'ai_model': self.ai_model,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Session(db.Model):
    __tablename__ = 'sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now_fn)
    updated_at = db.Column(db.DateTime, default=_now_fn, onupdate=_now_fn)
    
    # 代码内容 (存储为 JSON)
    user_code = db.Column(db.JSON, nullable=False, default=lambda: {'lang': 'cpp', 'std': 'c++17', 'content': ''})
    gen_code = db.Column(db.JSON, nullable=False, default=lambda: {'lang': 'cpp', 'std': 'c++17', 'content': ''})
    std_code = db.Column(db.JSON, nullable=False, default=lambda: {'lang': 'cpp', 'std': 'c++17', 'content': ''})
    
    test_cases = db.relationship('TestCase', backref='session', lazy=True, cascade="all, delete-orphan")
    
    def to_dict(self, include_cases=False):
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'user_code': self.user_code,
            'gen_code': self.gen_code,
            'std_code': self.std_code,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'test_case_count': len(self.test_cases)
        }
        if include_cases:
            data['test_cases'] = [tc.to_dict() for tc in self.test_cases]
        return data

class TestCase(db.Model):
    __tablename__ = 'test_cases'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'), nullable=False)
    status = db.Column(db.String(32), default='PENDING')  # AC, WA, TLE, MLE, RE
    input_data = db.Column(db.Text, nullable=False)
    user_output = db.Column(db.Text)
    std_output = db.Column(db.Text)
    time_used = db.Column(db.Float, nullable=True, default=None)
    memory_used = db.Column(db.Float, nullable=True, default=None)
    created_at = db.Column(db.DateTime, default=_now_fn)
    
    def to_dict(self):
        return {
            'id': self.id,
            'status': self.status,
            'input': self.input_data,
            'output': self.user_output,
            'answer': self.std_output,
            'time_used': self.time_used,
            'memory_used': self.memory_used,
            'created_at': self.created_at.isoformat()
        }
