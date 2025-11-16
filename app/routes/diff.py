from flask import request, Response, stream_with_context
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.config import config as app_config
from app.models import Session, TestCase
from app.utils.sandbox import FirejailSandbox
from app.utils.sse import sse_response
import os
import time

sandbox = FirejailSandbox()

class StartDiff(Resource):
    @jwt_required()
    def post(self, session_id):
        """开始持续对拍 (SSE 流)"""
        current_user = get_jwt_identity()
        session = Session.query.get_or_404(session_id)
        
        # 验证权限
        if session.user_id != current_user['id']:
            return {'error': 'forbidden', 'message': 'Not your session'}, 403
        
        # 获取参数
        data = request.get_json()
        max_tests = data.get('max_tests', 100)
        stop_on_fail = data.get('stop_on_fail', True)
        
        # 保存原始代码
        user_code = session.user_code.copy()
        std_code = session.std_code.copy()
        gen_code = session.gen_code.copy() if session.gen_code else None
        
        def generate_events():
            """生成 SSE 事件流"""
            for test_num in range(1, max_tests + 1):
                try:
                    # 1. 生成输入数据
                    if gen_code and gen_code.get('content'):
                        gen_result = sandbox.execute_code(
                            gen_code,
                            profile_type='generator'
                        )
                        input_data = gen_result['stdout']
                        if gen_result['returncode'] != 0:
                            yield sse_response('error', {
                                'message': 'Generator failed',
                                'details': gen_result['stderr'],
                                'test_num': test_num
                            })
                            return
                    else:
                        # 默认生成器
                        a = int(time.time() * 1000) % 100 + 1
                        b = int(time.time() * 10000) % 100 + 1
                        input_data = f"{a} {b}"
                    
                    # 2. 执行标准代码
                    std_result = sandbox.execute_code(std_code, input_data)
                    if std_result['returncode'] != 0:
                        yield sse_response('error', {
                            'message': 'Standard code failed',
                            'details': std_result['stderr'],
                            'test_num': test_num
                        })
                        return
                    
                    # 3. 执行用户代码
                    user_result = sandbox.execute_code(user_code, input_data)
                    
                    # 4. 确定状态
                    status = 'AC'
                    if user_result['returncode'] != 0:
                        status = 'RE'
                    elif user_result.get('error') == 'TIMEOUT':
                        status = 'TLE'
                    elif user_result['memory_cost'] > app_config[os.getenv('FLASK_ENV', 'default')].MAX_MEMORY_MB:
                        status = 'MLE'
                    elif user_result['stdout'].strip() != std_result['stdout'].strip():
                        status = 'WA'
                    
                    # 5. 保存测试用例
                    test_case = TestCase(
                        session_id=session_id,
                        status=status,
                        input_data=input_data,
                        user_output=user_result['stdout'],
                        std_output=std_result['stdout'],
                        time_cost=user_result['time_cost'],
                        memory_cost=user_result['memory_cost']
                    )
                    db.session.add(test_case)
                    db.session.commit()
                    
                    # 6. 发送事件
                    yield sse_response('test_result', {
                        'test_num': test_num,
                        'test_case': test_case.to_dict(),
                        'status': 'running'
                    })
                    
                    # 7. 检查停止条件
                    if status != 'AC' and stop_on_fail:
                        yield sse_response('completed', {
                            'total_tests': test_num,
                            'success_count': test_num - 1,
                            'fail_count': 1,
                            'success_rate': ((test_num - 1) / test_num) * 100,
                            'reason': 'first_failure'
                        })
                        return
                
                except Exception as e:
                    yield sse_response('error', {
                        'message': 'Execution error',
                        'details': str(e),
                        'test_num': test_num
                    })
                    return
            
            # 所有测试完成
            yield sse_response('completed', {
                'total_tests': max_tests,
                'success_count': max_tests,
                'fail_count': 0,
                'success_rate': 100.0,
                'reason': 'max_tests_reached'
            })
        
        return Response(
            stream_with_context(generate_events()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'  # 禁用 Nginx 缓冲
            }
        )

class StopDiff(Resource):
    @jwt_required()
    def post(self, session_id):
        """停止当前对拍"""
        # 实际实现需要维护执行进程映射
        # 简化版：标记会话为停止状态
        return {'stopped': True, 'session_id': session_id}, 200

class RerunDiff(Resource):
    @jwt_required()
    def post(self, session_id):
        """重新测试现有数据 (SSE 流)"""
        current_user = get_jwt_identity()
        session = Session.query.get_or_404(session_id)
        
        if session.user_id != current_user['id']:
            return {'error': 'forbidden', 'message': 'Not your session'}, 403
        
        # 获取要重测的测试用例
        data = request.get_json()
        case_ids = data.get('case_ids', [])
        
        if not case_ids:
            test_cases = session.test_cases
        else:
            test_cases = TestCase.query.filter(
                TestCase.id.in_(case_ids),
                TestCase.session_id == session_id
            ).all()
        
        # 保存原始代码
        user_code = session.user_code.copy()
        std_code = session.std_code.copy()
        
        def generate_events():
            """生成 SSE 事件流"""
            for idx, test_case in enumerate(test_cases):
                try:
                    # 1. 执行标准代码
                    std_result = sandbox.execute_code(std_code, test_case.input_data)
                    
                    # 2. 执行用户代码
                    user_result = sandbox.execute_code(user_code, test_case.input_data)
                    
                    # 3. 确定状态
                    status = 'AC'
                    if user_result['returncode'] != 0:
                        status = 'RE'
                    elif user_result.get('error') == 'TIMEOUT':
                        status = 'TLE'
                    elif user_result['memory_cost'] > app_config[os.getenv('FLASK_ENV', 'default')].MAX_MEMORY_MB:
                        status = 'MLE'
                    elif user_result['stdout'].strip() != std_result['stdout'].strip():
                        status = 'WA'
                    
                    # 4. 更新测试用例
                    test_case.status = status
                    test_case.user_output = user_result['stdout']
                    test_case.std_output = std_result['stdout']
                    test_case.time_cost = user_result['time_cost']
                    test_case.memory_cost = user_result['memory_cost']
                    
                    db.session.commit()
                    
                    # 5. 发送更新事件
                    yield sse_response('test_update', {
                        'test_case': test_case.to_dict(),
                        'progress': {
                            'current': idx + 1,
                            'total': len(test_cases)
                        }
                    })
                
                except Exception as e:
                    yield sse_response('error', {
                        'message': 'Rerun error',
                        'details': str(e),
                        'case_id': test_case.id
                    })
            
            # 完成事件
            yield sse_response('completed', {
                'total_cases': len(test_cases),
                'updated_cases': len(test_cases)
            })
        
        return Response(
            stream_with_context(generate_events()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )

from flask import Blueprint
diff_bp = Blueprint('diff', __name__)
diff_bp.add_url_rule('/<int:session_id>/start', view_func=StartDiff.as_view('session_list'))
diff_bp.add_url_rule('/<int:session_id>/stop', view_func=StopDiff.as_view('session_detail'))
diff_bp.add_url_rule('/<int:session_id>/rerun', view_func=RerunDiff.as_view('session_detail'))
