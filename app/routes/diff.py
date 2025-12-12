from flask import request, Response, stream_with_context
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from app.extensions import db
from app.exceptions import AuthenticationError, AuthorizationError
from flask import current_app
from app.models import Session, TestCase
from app.utils.sandbox import run_compiler, run_program, run_checker
from app.utils.sse import sse_response
from tempfile import TemporaryDirectory, NamedTemporaryFile
from pathlib import Path
from datetime import datetime, timezone
from signal import Signals
import string
import random
import logging
import os

logger = logging.getLogger(__name__)
request_stop_set = set()

def judge(testcase: TestCase,
          gen_exe_file: os.PathLike | None,
          user_exe_file: os.PathLike,
          std_exe_file: os.PathLike,
          chk_exe_file: os.PathLike):
    # run generator if exists
    if gen_exe_file is not None:
        random_token = ''.join(random.choice(string.ascii_letters) for _ in range(16))
        gen_result, input_data, _, _, _ = run_program(gen_exe_file, [random_token])

        testcase.input_data = input_data
        if gen_result['type'] != 'OK':
            testcase.status = f"Generator {gen_result['type']}"
            testcase.detail = f"Generator {gen_result['type']}"
            if gen_result['type'] == 'RE':
                testcase.detail += f" ({Signals(gen_result['code']).name})"
            return False
    else:
        input_data = testcase.input_data

    # run user code
    user_result, user_output, _, time_used, memory_used = run_program(user_exe_file, input_data=input_data)
    testcase.user_output = user_output
    testcase.time_used = time_used
    testcase.memory_used = memory_used
    if user_result['type'] != 'OK':
        testcase.status = f"User {user_result['type']}"
        testcase.detail = f"User {user_result['type']}"
        if user_result['type'] == 'RE':
            testcase.detail += f" ({Signals(user_result['code']).name})"
        return False

    # run std code
    std_result, std_output, _, _, _ = run_program(std_exe_file, input_data=input_data)
    testcase.std_output = std_output
    if std_result['type'] != 'OK':
        testcase.status = f"Std {std_result['type']}"
        testcase.detail = f"Std {std_result['type']}"
        if std_result['type'] == 'RE':
            testcase.detail += f" ({Signals(std_result['code']).name})"
        return False

    # run checker
    with (
        NamedTemporaryFile('w+', delete=True) as input_file,
        NamedTemporaryFile('w+', delete=True) as output_file,
        NamedTemporaryFile('w+', delete=True) as answer_file
    ):
        input_file.write(input_data)
        output_file.write(user_output)
        answer_file.write(std_output)

        input_file.flush()
        output_file.flush()
        answer_file.flush()

        result = run_checker(chk_exe_file, input_file.name, output_file.name, answer_file.name)
        testcase.status = result['status']
        testcase.detail = result['detail']
        if testcase.status != 'OK':
            return False

    testcase.status = 'OK'
    return True


class StartDiff(Resource):
    @jwt_required()
    def get(self, session_id):
        def generator():
            try:
                # 获取当前用户
                current_user = get_jwt_identity()
                if not current_user or not isinstance(current_user, str):
                    raise AuthenticationError("Invalid JWT identity")
                
                user_id = int(current_user)
                if not user_id:
                    raise AuthenticationError("Missing user ID in token")
                
                # 获取会话
                session = Session.query.get_or_404(session_id)
                
                # 验证权限
                if session.user_id != user_id:
                    raise AuthorizationError("Not your session")

                # 获取参数
                max_tests = int(request.args.get('max_tests', 100))
                checker = str(request.args.get('checker', 'wcmp'))
                max_tests = max(min(max_tests, 1000), 1)
                
                # 保存原始代码
                user_code = session.user_code.copy() if session.user_code else {}
                std_code = session.std_code.copy() if session.std_code else {}
                gen_code = session.gen_code.copy() if session.gen_code else None
                
                yield from self.diff(session_id, user_code, std_code, gen_code, max_tests, checker)
            
            except Exception as e:
                yield sse_response('error', {'message': str(e)})

        # 生成 SSE 响应
        return Response(
            stream_with_context(generator()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',  # 禁用 Nginx 缓冲
                'Access-Control-Allow-Origin': request.headers.get('Origin', '*'),
                'Access-Control-Allow-Credentials': 'true'
            }
        )

    def diff(self, session_id, user_code, std_code, gen_code, max_tests, checker):
        request_stop_set.discard(session_id)

        # delete old data
        TestCase.query.filter_by(session_id=session_id).delete()
        db.session.commit()

        checker_exe_file = Path(current_app.config['CHECKER_EXECUTABLE_PREFIX']) / checker

        with TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)

            # compile codes
            for s, code in (('user', user_code), ('std', std_code), ('gen', gen_code)):
                yield sse_response('status', {'status': f"Compiling {s} code"})

                code_file = temp_dir / f'{s}_code'
                exe_file = temp_dir / f'{s}_exe'
                code_file.write_text(code['content'])
                exe_file.touch()
                type, data = run_compiler(code_file, exe_file, code['lang'], code['std'])
                data['message'] = f"{s} code: {data['message']}"

                yield sse_response(type, data)
                if type == 'failed':
                    return

            try:
                for i in range(max_tests):
                    yield sse_response('status', {"status": f"Running test {i + 1}/{max_tests}"})
                    testcase = TestCase(
                        session_id=session_id,
                        created_at=datetime.now(timezone.utc)
                    )

                    gen_exe_file = temp_dir / 'gen_exe'
                    user_exe_file = temp_dir / 'user_exe'
                    std_exe_file = temp_dir / 'std_exe'
                    ret = judge(testcase, gen_exe_file, user_exe_file, std_exe_file, checker_exe_file)

                    db.session.add(testcase)
                    yield sse_response('test_result', {
                        'test_num': i,
                        'test_case': testcase.to_dict()
                    })
                    if not ret or session_id in request_stop_set:
                        break
            finally:
                db.session.commit()

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
        def generator():
            try:
                current_user = int(get_jwt_identity())
                session = Session.query.get_or_404(session_id)
                
                if session.user_id != int(current_user):
                    raise AuthorizationError("Not your session")
                
                checker = str(request.args.get('checker', 'wcmp'))

                # 保存原始代码
                user_code = session.user_code.copy()
                std_code = session.std_code.copy()

                yield from self.rerun(session_id, user_code, std_code, checker)
            
            except Exception as e:
                yield sse_response('error', {'message': str(e)})

        return Response(
            stream_with_context(generator()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )
    
    def rerun(self, session_id, user_code, std_code, checker):
        request_stop_set.discard(session_id)

        session = Session.query.get_or_404(session_id)
        test_cases = session.test_cases

        checker_exe_file = Path(current_app.config['CHECKER_EXECUTABLE_PREFIX']) / checker

        with TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)

            for s, code in (('user', user_code), ('std', std_code)):
                yield sse_response('status', {'status': f"Compiling {s} code"})

                code_file = temp_dir / f'{s}_code'
                exe_file = temp_dir / f'{s}_exe'
                code_file.write_text(code['content'])
                exe_file.touch()
                type, data = run_compiler(code_file, exe_file, code['lang'], code['std'])
                data['message'] = f"{s} code: {data['message']}"

                yield sse_response(type, data)
                if type == 'failed':
                    return

            try:
                for i, testcase in enumerate(test_cases):
                    yield sse_response('status', {"status": f"Running test {i + 1}/{len(test_cases)}"})
                    
                    user_exe_file = temp_dir / 'user_exe'
                    std_exe_file = temp_dir / 'std_exe'
                    ret = judge(testcase, None, user_exe_file, std_exe_file, checker_exe_file)

                    yield sse_response('test_result', {
                        'test_num': i,
                        'test_case': testcase.to_dict()
                    })
                    if not ret or session_id in request_stop_set:
                        break
            finally:
                db.session.commit()

            yield sse_response('finish', {})


from flask import Blueprint
diff_bp = Blueprint('diff', __name__)
diff_bp.add_url_rule('/<int:session_id>/start', view_func=StartDiff.as_view('start_diff'))
diff_bp.add_url_rule('/<int:session_id>/stop', view_func=StopDiff.as_view('stop_diff'))
diff_bp.add_url_rule('/<int:session_id>/rerun', view_func=RerunDiff.as_view('rerun_diff'))
