from flask import request, Response, stream_with_context
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from app.extensions import db
from app.config import config as app_config
from app.models import Session, TestCase
from app.utils.sandbox import run_compiler, run_program
from app.utils.sse import sse_response
from tempfile import TemporaryDirectory
from pathlib import Path
import string
import random
import logging

logger = logging.getLogger(__name__)
request_stop_set = set()

class StartDiff(Resource):
    @jwt_required()
    def get(self, session_id):
        try:
            # 获取当前用户
            current_user = get_jwt_identity()
            if not current_user or not isinstance(current_user, str):
                logger.warning("Invalid JWT identity")
                return {'error': 'Invalid token'}, 401
            
            user_id = int(current_user)
            if not user_id:
                logger.warning("Missing user ID in token")
                return {'error': 'Invalid token'}, 401
            
            # 获取会话
            session = Session.query.get_or_404(session_id)
            
            # 验证权限
            if session.user_id != user_id:
                logger.warning(f"User {user_id} attempted to access session {session_id} owned by {session.user_id}")
                return {'error': 'forbidden', 'message': 'Not your session'}, 403

            # 获取参数
            max_tests = int(request.args.get('max_tests', 100))
            stop_on_fail = request.args.get('stop_on_fail', True)
            
            # 验证参数
            if max_tests < 1 or max_tests > 1000:
                max_tests = 1000
            
            logger.info(f"Starting continuous diff for session {session_id} with max_tests={max_tests}, stop_on_fail={stop_on_fail}")
            
            # 保存原始代码
            user_code = session.user_code.copy() if session.user_code else {}
            std_code = session.std_code.copy() if session.std_code else {}
            gen_code = session.gen_code.copy() if session.gen_code else None
            
            # 生成 SSE 响应
            return Response(
                stream_with_context(self.diff(
                    session_id, user_code, std_code, gen_code, max_tests, stop_on_fail
                )),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'X-Accel-Buffering': 'no',  # 禁用 Nginx 缓冲
                    'Access-Control-Allow-Origin': request.headers.get('Origin', '*'),
                    'Access-Control-Allow-Credentials': 'true'
                }
            )
        
        except Exception as e:
            logger.exception(f"Error in StartDiff: {str(e)}")
            return {'error': 'Internal server error', 'message': str(e)}, 500
    
    def diff(self, session_id, user_code, std_code, gen_code, max_tests, stop_on_fail):
        request_stop_set.discard(session_id)

        # delete old data
        TestCase.query.filter_by(session_id=session_id).delete()
        db.session.commit()

        with TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)

            for s, code in (('user', user_code), ('std', std_code), ('gen', gen_code)):
                yield sse_response('status', {'status': f"Compiling {s} code"})

                code_file = temp_dir / f'{s}_code'
                exe_file = temp_dir / f'{s}_exe'
                Path.write_text(code_file, code['content'])
                Path.touch(exe_file)
                type, data = run_compiler(code_file, exe_file, code['lang'], code['std'])
                data['message'] = f"{s} code: {data['message']}"

                yield sse_response(type, data)
                if type == 'failed':
                    return

            current_testcase = None
            for i in range(max_tests):
                if current_testcase:
                    yield sse_response('test_result', {
                        'test_num': i,
                        'test_case': current_testcase.to_dict()
                    })

                yield sse_response('status', {"status": f"Running test {i + 1}/{max_tests}"})
                current_testcase = TestCase(
                    session_id=session_id,
                    status='',
                    input_data='',
                    user_output='',
                    std_output='',
                )

                gen_exe_file = temp_dir / 'gen_exe'
                user_exe_file = temp_dir / 'user_exe'
                std_exe_file = temp_dir / 'std_exe'
                
                random_token = ''.join(random.choice(string.ascii_letters) for _ in range(16))
                gen_result, input_data, _, _ = run_program(gen_exe_file, [random_token])

                current_testcase.input_data = input_data
                if gen_result['type'] != 'OK':
                    current_testcase.status = f"Generator {gen_result['type']}"
                    db.session.add(current_testcase)
                    db.session.commit()
                    break

                user_result, user_output, time_used, memory_used = run_program(user_exe_file, input_data=input_data)
                current_testcase.user_output = user_output
                current_testcase.time_used = time_used
                current_testcase.memory_used = memory_used
                if user_result['type'] != 'OK':
                    current_testcase.status = f"User {user_result['type']}"
                    db.session.add(current_testcase)
                    db.session.commit()
                    break

                std_result, std_output, _, _ = run_program(std_exe_file, input_data=input_data)
                current_testcase.std_output = std_output
                if std_result['type'] != 'OK':
                    current_testcase.status = f"Std {std_result['type']}"
                    db.session.add(current_testcase)
                    db.session.commit()
                    break

                normalized_user_output = '\n'.join([s.rstrip() for s in user_output.split('\n')]).rstrip()
                normalized_std_output = '\n'.join([s.rstrip() for s in std_output.split('\n')]).rstrip()
                if normalized_user_output != normalized_std_output:
                    current_testcase.status = 'WA'
                    db.session.add(current_testcase)
                    db.session.commit()
                    break
                
                current_testcase.status = 'OK'
                db.session.add(current_testcase)
                db.session.commit()

                if session_id in request_stop_set:
                    yield sse_response('finish', {})
                    return

            if current_testcase:
                yield sse_response('test_result', {
                    'test_num': max_tests,
                    'test_case': current_testcase.to_dict()
                })
            yield sse_response('finish', {})


class StopDiff(Resource):
    @jwt_required()
    def post(self, session_id):
        """停止当前对拍"""
        # 实际实现需要维护执行进程映射
        # 简化版：标记会话为停止状态
        request_stop_set.add(session_id)
        return {'stopped': True, 'session_id': session_id}, 200


class RerunDiff(Resource):
    @jwt_required()
    def get(self, session_id):
        """重新测试现有数据 (SSE 流)"""
        current_user = int(get_jwt_identity())
        session = Session.query.get_or_404(session_id)
        
        if session.user_id != int(current_user):
            return {'error': 'forbidden', 'message': 'Not your session'}, 403
        
        # 保存原始代码
        user_code = session.user_code.copy()
        std_code = session.std_code.copy()
        
        return Response(
            stream_with_context(self.rerun(session_id, user_code, std_code)),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )
    
    def rerun(self, session_id, user_code, std_code):
        request_stop_set.discard(session_id)

        session = Session.query.get_or_404(session_id)
        test_cases = session.test_cases

        with TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)

            for s, code in (('user', user_code), ('std', std_code)):
                yield sse_response('status', {'status': f"Compiling {s} code"})

                code_file = temp_dir / f'{s}_code'
                exe_file = temp_dir / f'{s}_exe'
                Path.write_text(code_file, code['content'])
                Path.touch(exe_file)
                type, data = run_compiler(code_file, exe_file, code['lang'], code['std'])
                data['message'] = f"{s} code: {data['message']}"

                yield sse_response(type, data)
                if type == 'failed':
                    return

            current_testcase = None
            for i, current_testcase in enumerate(test_cases):
                yield sse_response('status', {"status": f"Running test {i + 1}/{len(test_cases)}"})
                user_exe_file = temp_dir / 'user_exe'
                std_exe_file = temp_dir / 'std_exe'

                input_data = current_testcase.input_data

                user_result, user_output, time_used, memory_used = run_program(user_exe_file, input_data=input_data)
                current_testcase.user_output = user_output
                current_testcase.status = f"User {user_result['type']}"
                current_testcase.time_used = time_used
                current_testcase.memory_used = memory_used

                std_result, std_output, _, _ = run_program(std_exe_file, input_data=current_testcase.input_data)
                current_testcase.std_output = std_output
                current_testcase.status = f"Std {std_result['type']}"

                normalized_user_output = '\n'.join([s.rstrip() for s in user_output.split('\n')]).rstrip()
                normalized_std_output = '\n'.join([s.rstrip() for s in std_output.split('\n')]).rstrip()
                if normalized_user_output != normalized_std_output:
                    current_testcase.status = 'WA'
                else:
                    current_testcase.status = 'OK'

                db.session.commit()
                yield sse_response('test_result', {
                    'test_num': i,
                    'test_case': current_testcase.to_dict()
                })

                if session_id in request_stop_set:
                    yield sse_response('finish', {})
                    return

            yield sse_response('finish', {})


from flask import Blueprint
diff_bp = Blueprint('diff', __name__)
diff_bp.add_url_rule('/<int:session_id>/start', view_func=StartDiff.as_view('start_diff'))
diff_bp.add_url_rule('/<int:session_id>/stop', view_func=StopDiff.as_view('stop_diff'))
diff_bp.add_url_rule('/<int:session_id>/rerun', view_func=RerunDiff.as_view('rerun_diff'))
