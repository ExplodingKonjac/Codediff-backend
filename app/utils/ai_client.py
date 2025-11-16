import requests
import json
import logging
import time
import os

from app.config import config as app_config

logger = logging.getLogger(__name__)

class AIClient:
    """AI 代码生成客户端"""
    
    def __init__(self):
        self.config = app_config[os.getenv('FLASK_ENV', 'default')]
        self.timeout = self.config.AI_TIMEOUT
        self.default_model = self.config.DEFAULT_AI_MODEL
    
    def _get_ai_config(self, user_config):
        """获取 AI 配置，优先使用用户配置"""
        api_key = user_config.get('api_key') or self.config.get('AI_API_KEY')
        api_url = user_config.get('api_url') or self.config.get('AI_API_URL')
        
        if not api_key or not api_url:
            raise ValueError('AI API configuration is missing')
        
        return {
            'api_key': api_key,
            'api_url': api_url,
            'model': user_config.get('model', self.default_model)
        }
    
    def _make_request(self, config, payload):
        """发送 AI 请求"""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {config["api_key"]}'
        }
        
        try:
            start_time = time.time()
            response = requests.post(
                config['api_url'],
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            elapsed = time.time() - start_time
            
            logger.info(f'AI request completed in {elapsed:.2f}s, status: {response.status_code}')
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f'AI request failed: {str(e)}')
            if e.response is not None:
                logger.error(f'Response content: {e.response.text}')
            raise
    
    def generate_generator(self, api_key: str, api_url: str, context: dict[str, str]):
        """生成数据生成器代码"""
        # 构建提示
        prompt = f"""
        你是一个专业的编程助手，专门为程序设计竞赛生成测试数据。
        
        题目: {context.get('title', 'Unknown Problem')}
        描述: {context.get('description', 'No description provided')}
        
        要求:
        1. 使用 C++ 和 testlib.h 库生成随机测试数据
        2. 生成的代码必须是完整的、可编译的程序
        3. 包含适当的随机数生成和边界条件处理
        4. 输出格式必须符合题目要求
        5. 代码必须高效且无内存泄漏
        
        仅返回代码，不要包含任何解释或额外文本。
        """
        
        return self._generate_code(
            api_key=api_key,
            api_url=api_url,
            prompt=prompt,
            language='cpp',
            code_type='generator'
        )
    
    def generate_standard(self, api_key: str, api_url: str, context: dict[str, str]):
        """生成标准答案代码"""
        # 构建提示
        prompt = f"""
        你是一个专业的编程助手，专门为程序设计竞赛生成标准答案。
        
        题目: {context.get('title', 'Unknown Problem')}
        描述: {context.get('description', 'No description provided')}
        用户代码: {context.get('user_code', 'No user code provided')[:200]}...
        
        要求:
        1. 生成一个正确、高效的 C++ 程序
        2. 程序必须通过所有可能的测试用例
        3. 代码必须符合题目中的时间/空间限制
        4. 使用适当的算法和数据结构
        5. 代码必须是完整的、可编译的程序
        6. 优先使用标准库和现代 C++ 特性
        
        仅返回代码，不要包含任何解释或额外文本。
        """
        
        return self._generate_code(
            api_key=api_key,
            api_url=api_url,
            prompt=prompt,
            language='cpp',
            code_type='standard'
        )
    
    def _generate_code(self, api_key, api_url, prompt, language, code_type):
        """通用代码生成方法"""
        # 模拟开发环境 (无真实 AI 服务)
        if self.config.DEBUG:
            return self._mock_generation(code_type, language)
        
        # 获取配置
        ai_config = self._get_ai_config({
            'api_key': api_key,
            'api_url': api_url
        })
        
        # 构建请求
        payload = {
            'model': ai_config['model'],
            'messages': [
                {'role': 'system', 'content': 'You are a code generation assistant that only outputs code without any explanations.'},
                {'role': 'user', 'content': prompt}
            ],
            'max_tokens': 1000,
            'temperature': 0.3,
            'top_p': 0.9
        }
        
        # 发送请求
        response = self._make_request(ai_config, payload)
        
        # 解析响应
        try:
            code = self._extract_code(response)
            return {
                'code': code,
                'language': language,
                'confidence': 0.95
            }
        except Exception as e:
            logger.error(f'Failed to parse AI response: {str(e)}')
            logger.error(f'Response: {response}')
            raise ValueError('Invalid AI response format')
    
    def _extract_code(self, response):
        """从 AI 响应中提取代码"""
        # 支持多种响应格式
        if 'choices' in response and len(response['choices']) > 0:
            message = response['choices'][0].get('message', {})
            content = message.get('content', '')
        elif 'content' in response:
            content = response['content']
        elif 'text' in response:
            content = response['text']
        else:
            raise ValueError('Unsupported AI response format')
        
        # 清理代码 (移除 Markdown 代码块标记)
        if content.startswith('```'):
            lines = content.split('\n')
            if lines[0].startswith('```'):
                lang = lines[0][3:].strip()
                code_lines = lines[1:-1] if lines[-1].startswith('```') else lines[1:]
            else:
                code_lines = lines
            code = '\n'.join(code_lines)
        else:
            code = content
        
        # 确保代码包含必要的头文件
        if '#include' not in code[:100] and 'c++' in self.default_model.lower():
            code = '#include <iostream>\n#include <vector>\n#include <algorithm>\nusing namespace std;\n\n' + code
        
        return code.strip()
    
    def _mock_generation(self, code_type, language):
        """开发环境下的模拟生成"""
        logger.info(f'Mocking AI generation for {code_type} in {language}')
        
        if code_type == 'generator':
            return {
                'code': '''#include "testlib.h"
#include <iostream>
using namespace std;

int main() {
    registerGen();
    int n = rnd.next(1, 100);
    cout << n << endl;
    for (int i = 0; i < n; i++) {
        cout << rnd.next(1, 1000) << " ";
    }
    return 0;
}''',
                'language': 'cpp',
                'confidence': 0.85
            }
        else:
            return {
                'code': '''#include <iostream>
#include <vector>
#include <algorithm>
using namespace std;

int main() {
    int n;
    cin >> n;
    vector<int> arr(n);
    for (int i = 0; i < n; i++) {
        cin >> arr[i];
    }
    sort(arr.begin(), arr.end());
    for (int i = 0; i < n; i++) {
        cout << arr[i] << " ";
    }
    return 0;
}''',
                'language': 'cpp',
                'confidence': 0.92
            }
