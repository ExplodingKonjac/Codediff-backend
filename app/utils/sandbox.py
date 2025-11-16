import subprocess
import tempfile
import os
import json
import signal
from pathlib import Path
from app.config import config as app_config

class FirejailSandbox:
    """使用 Firejail 实现轻量级安全沙箱"""
    
    def __init__(self):
        self.sandbox_exec = app_config[os.getenv('FLASK_ENV', 'default')].SANDBOX_EXECUTABLE
        self.profile_dir = app_config[os.getenv('FLASK_ENV', 'default')].SANDBOX_PROFILE_DIR
        self.max_time = app_config[os.getenv('FLASK_ENV', 'default')].MAX_EXEC_TIME
        self.max_memory = app_config[os.getenv('FLASK_ENV', 'default')].MAX_MEMORY_MB
    
    def _get_profile_path(self, profile_type):
        """获取 Firejail 配置文件路径"""
        profile_map = {
            'code-exec': 'code-exec.profile',
            'generator': 'generator.profile'
        }
        profile_file = profile_map.get(profile_type, 'code-exec.profile')
        return os.path.join(self.profile_dir, profile_file)
    
    def _prepare_code(self, code_info, input_data=None):
        """准备代码执行环境"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 写入代码文件
            ext_map = {
                'c': 'c',
                'cpp': 'cpp',
                'c11': 'c',
                'c17': 'c',
                'c++11': 'cpp',
                'c++17': 'cpp',
                'c++20': 'cpp'
            }
            lang = code_info['lang'].lower()
            ext = ext_map.get(lang, 'cpp')
            code_path = os.path.join(tmpdir, f'code.{ext}')
            
            with open(code_path, 'w') as f:
                f.write(code_info['content'])
            
            # 写入输入文件
            if input_data:
                input_path = os.path.join(tmpdir, 'input.txt')
                with open(input_path, 'w') as f:
                    f.write(input_data)
            
            return tmpdir
    
    def execute_code(self, code_info, input_data=None, profile_type='code-exec'):
        """
        在沙箱中执行代码
        
        Args:
            code_info: {'lang': 'cpp', 'std': 'c++17', 'content': '...'}
            input_data: 输入数据字符串
            profile_type: 'code-exec' 或 'generator'
        
        Returns:
            {
                'stdout': str,
                'stderr': str,
                'returncode': int,
                'time_cost': float,  # ms
                'memory_cost': float  # MB
            }
        """
        # 准备执行环境
        tmpdir = self._prepare_code(code_info, input_data)
        
        # 构建编译命令
        lang = code_info['lang'].lower()
        std = code_info.get('std', '').lower()
        compile_cmd = self._build_compile_command(lang, std, tmpdir)
        
        # 构建运行命令
        run_cmd = self._build_run_command(lang, tmpdir, input_data)
        
        # 构建 Firejail 命令
        firejail_cmd = self._build_firejail_command(profile_type, tmpdir)
        
        try:
            # 执行编译
            compile_result = self._run_command(firejail_cmd + compile_cmd, tmpdir)
            if compile_result['returncode'] != 0:
                return {
                    'stdout': '',
                    'stderr': compile_result['stderr'],
                    'returncode': compile_result['returncode'],
                    'time_cost': compile_result['time_cost'],
                    'memory_cost': compile_result['memory_cost'],
                    'error': 'COMPILATION_FAILED'
                }
            
            # 执行程序
            run_result = self._run_command(firejail_cmd + run_cmd, tmpdir)
            return run_result
            
        finally:
            # 清理临时目录
            try:
                Path(tmpdir).rmdir()
            except:
                pass
    
    def _build_compile_command(self, lang, std, tmpdir):
        """构建编译命令"""
        if lang in ['c', 'c11', 'c17']:
            cmd = ['gcc']
            if std:
                cmd.append(f'-std={std}')
            cmd.extend(['-o', os.path.join(tmpdir, 'a.out'), os.path.join(tmpdir, 'code.c')])
        elif lang in ['cpp', 'c++11', 'c++17', 'c++20']:
            cmd = ['g++']
            if std:
                cmd.append(f'-std={std}')
            cmd.extend(['-o', os.path.join(tmpdir, 'a.out'), os.path.join(tmpdir, 'code.cpp')])
        else:
            raise ValueError(f'Unsupported language: {lang}')
        
        return cmd
    
    def _build_run_command(self, lang, tmpdir, input_data):
        """构建运行命令"""
        cmd = [os.path.join(tmpdir, 'a.out')]
        if input_data:
            cmd = ['timeout', str(self.max_time), os.path.join(tmpdir, 'a.out')]
        return cmd
    
    def _build_firejail_command(self, profile_type, tmpdir):
        """构建 Firejail 命令"""
        profile_path = self._get_profile_path(profile_type)
        
        cmd = [
            self.sandbox_exec,
            f'--profile={profile_path}',
            f'--timeout={self.max_time}',
            f'--rlimit-as={self.max_memory}M',
            f'--private={tmpdir}',
            '--private-tmp',
            '--noprofile',
            '--quiet'
        ]
        
        # 根据配置添加额外限制
        if app_config[os.getenv('FLASK_ENV', 'default')].DEBUG:
            cmd.append('--debug')
        
        return cmd
    
    def _run_command(self, command, working_dir):
        """执行命令并返回结果"""
        start_time = os.times()
        
        try:
            result = subprocess.run(
                command,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=self.max_time + 1,
                check=False
            )
            end_time = os.times()
            
            # 计算时间和内存
            time_cost = (end_time.elapsed - start_time.elapsed) * 1000  # ms
            memory_cost = self._estimate_memory(result)
            
            return {
                'stdout': result.stdout.strip(),
                'stderr': result.stderr.strip(),
                'returncode': result.returncode,
                'time_cost': min(time_cost, self.max_time * 1000),
                'memory_cost': min(memory_cost, self.max_memory)
            }
        except subprocess.TimeoutExpired:
            return {
                'stdout': '',
                'stderr': f'Execution timed out after {self.max_time} seconds',
                'returncode': -signal.SIGKILL,
                'time_cost': self.max_time * 1000,
                'memory_cost': 0,
                'error': 'TIMEOUT'
            }
        except Exception as e:
            return {
                'stdout': '',
                'stderr': str(e),
                'returncode': -1,
                'time_cost': 0,
                'memory_cost': 0,
                'error': 'EXECUTION_ERROR'
            }
    
    def _estimate_memory(self, result):
        """估算内存使用（简化版）"""
        # 实际生产环境应使用 cgroups 或 firejail --mem
        return len(result.stdout) / 1024 + len(result.stderr) / 1024 
