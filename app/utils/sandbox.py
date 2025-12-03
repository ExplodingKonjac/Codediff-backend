from app.exceptions import SandboxError
import os
import signal
import ctypes
from pathlib import Path
from app.config import config as app_config
from subprocess import Popen, PIPE
from multiprocessing import Pipe

class ChildData(ctypes.Structure):
    _fields_ = [
        ('exit_status', ctypes.c_int),
        ('user_time_us', ctypes.c_uint64),
        ('system_time_us', ctypes.c_uint64),
        ('memory_kb', ctypes.c_uint64),
    ]

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

def launch_sandbox(cmd, rlim_cpu, rlim_as, rlim_fsz, extra_args=[], input_data = None):
    config = app_config[os.getenv('FLASK_ENV', 'default')]

    pipe_rd_fd, pipe_wr_fd = os.pipe()
    with os.fdopen(pipe_wr_fd, 'wb') as pipe_wr, os.fdopen(pipe_rd_fd, 'rb') as pipe_rd:
        child = Popen(
            [
                config.SANDBOX_EXECUTABLE,
                '--ro-bind', config.RLIMIT_WRAPPER_EXECUTABLE, '/wrapper',
                '--ro-bind', '/usr', '/usr',
                '--symlink', 'usr/lib', '/lib',
                '--symlink', 'usr/lib64', '/lib64',
                '--proc', '/proc',
                '--dev', '/dev',
                '--dir', '/home',
                '--chdir', '/home',
                '--unshare-all',
                '--as-pid-1',
                '--sync-fd', str(pipe_wr.fileno()),
                *extra_args,
                '--', '/wrapper', str(rlim_cpu), str(rlim_as), str(rlim_fsz), str(pipe_wr.fileno()),
                *cmd
            ],
            pass_fds=[pipe_wr.fileno()],
            stdout=PIPE,
            stderr=PIPE,
            stdin=PIPE,
        )
        pipe_wr.close()

        stdout, stderr = child.communicate(None if input_data is None else input_data.encode())
        if isinstance(stderr, bytes):
            stderr = stderr.decode()
        if isinstance(stdout, bytes):
            stdout = stdout.decode()

        data_buf = pipe_rd.read(ctypes.sizeof(ChildData))
        data = ChildData.from_buffer_copy(data_buf)

    return data, stdout, stderr

def run_compiler(code, out, lang, std):
    config = app_config[os.getenv('FLASK_ENV', 'default')]
    time_limit = 10
    memory_limit = config.COMPILER_MEMORY_LIMIT * 1024 * 1024
    output_limit = config.COMPILER_OUTPUT_LIMIT * 1024

    if lang.lower() == 'c':
        cmd = ['gcc', '-x', 'c', f'-std={std}', '-O2', 'code', '-o', 'out']
    elif lang.lower() == 'cpp':
        cmd = ['g++', '-x', 'c++', f'-std={std}', '-O2', 'code', '-o', 'out']
    else:
        raise SandboxError("Unknown language")

    data, stdout, stderr = launch_sandbox(
        cmd,
        time_limit,
        memory_limit,
        output_limit,
        extra_args=[
            '--ro-bind', code, '/home/code',
            '--bind', out, '/home/out',
            '--bind', app_config[os.getenv('FLASK_ENV', 'default')].TESTLIB_PATH, '/home/testlib.h' 
        ]
    )

    res = get_result_from_exit_status(data.exit_status)
    if res['type'] == 'RE':
        if res['code'] == 1:
            return 'failed', {'message': "Compile Error", 'detail': stderr[:1024]}
        else:
            return 'failed', {'message': f"Compiler {res['type']}", 'detail': ""}
    else:
        return 'status', {'message': "Success", 'detail': stderr[:1024]}

def run_program(filename, args = [], input_data = None):
    config = app_config[os.getenv('FLASK_ENV', 'default')]
    time_limit = config.PROG_TIME_LIMIT
    memory_limit = config.PROG_MEMORY_LIMIT * 1024 * 1024
    output_limit = config.PROG_OUTPUT_LIMIT * 1024

    data, stdout, stderr = launch_sandbox(
        ['/exe', *args],
        time_limit,
        memory_limit,
        output_limit,
        extra_args=['--ro-bind', filename, '/exe'],
        input_data=input_data
    )

    time_ms = data.user_time_us / 1000
    memory_mb = data.memory_kb / 1024
    print(memory_mb)
    result = get_result_from_exit_status(data.exit_status)

    return result, stdout, time_ms, memory_mb
