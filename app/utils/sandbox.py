from app.exceptions import SandboxError
import os
import signal
from pathlib import Path
from app.config import config as app_config
from subprocess import Popen, PIPE

def get_result_from_exit_status(exit_status):
    if os.WIFEXITED(exit_status):
        return {'type': 'OK', 'code': os.WEXITSTATUS(exit_status)}
    elif os.WIFSIGNALED(exit_status):
        sig = os.WTERMSIG(exit_status)
        if sig == signal.SIGKILL:
            return {'type': 'TLE_or_MLE', 'code': sig}
        elif sig == signal.SIGXFSZ:
            return {'type': 'OLE', 'code': sig}
        else:
            return {'type': 'RE', 'code': sig}
    else:
        return {'type': 'UKE', 'code': exit_status}

def launch_sandbox(cmd, rlim_cpu, rlim_as, rlim_fsz, extra_args=[], *args, **kwargs):
    config = app_config[os.getenv('FLASK_ENV', 'default')]
    return Popen([
        config.SANDBOX_EXECUTABLE,
        '--ro-bind', config.RLIMIT_WRAPPER_EXECUTABLE, '/wrapper',
        '--ro-bind', '/usr', '/usr',
        '--symlink', 'usr/lib', '/lib',
        '--symlink', 'usr/lib64', '/lib64',
        '--proc', '/proc',
        '--dev', '/dev',
        '--dir', '/home',
        '--chdir', '/home',
        *extra_args,
        '--', '/wrapper', str(rlim_cpu), str(rlim_as), str(rlim_fsz), *cmd
    ], *args, **kwargs)

def run_compiler(code, out, lang, std):
    if lang.lower() == 'c':
        cmd = ['gcc', '-x', 'c', f'-std={std}', '-O2', 'code', '-o', 'out']
    elif lang.lower() == 'cpp':
        cmd = ['g++', '-x', 'c++', f'-std={std}', '-O2', 'code', '-o', 'out']
    else:
        raise SandboxError("Unknown language")
    
    child = launch_sandbox(cmd, 10, 512 * 1024 * 1024, 16 * 1024 * 1024, extra_args=[
        '--ro-bind', code, '/home/code',
        '--bind', out, '/home/out',
        '--bind', app_config[os.getenv('FLASK_ENV', 'default')].TESTLIB_PATH, '/home/testlib.h' 
    ], stdout=PIPE, stderr=PIPE)
    
    _, stderr = child.communicate()
    if isinstance(stderr, bytes):
        stderr = stderr.decode()

    res = get_result_from_exit_status(child.returncode)
    if res['type'] == 'RE':
        if res['code'] == 1:
            return 'failed', {'message': "Compile Error", 'detail': stderr[:1024]}
        else:
            return 'failed', {'message': f"Compiler {res['type']}", 'detail': ""}
    else:
        return 'status', {'message': "Success", 'detail': stderr[:1024]}

def run_program(filename, args = [], input_data = None):
    child = launch_sandbox(['/exe', *args], 5, 256 * 1024 * 1024, 1024 * 1024, extra_args=[
        '--ro-bind', filename, '/exe'
    ], stdout=PIPE, stderr=PIPE, stdin=PIPE)

    data, stderr = child.communicate(None if input_data is None else input_data.encode())
    if isinstance(stderr, bytes):
        stderr = stderr.decode()
    if isinstance(data, bytes):
        data = data.decode()

    time_ms = 0
    memory_mb = 0
    result = get_result_from_exit_status(child.returncode)

    return result, data, time_ms, memory_mb
