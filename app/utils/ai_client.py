import requests
import json
import logging
import time
import os
from openai import OpenAI

from app.config import config as app_config

logger = logging.getLogger(__name__)

class AIClient:
    """AI 代码生成客户端"""
    
    def __init__(self):
        self.config = app_config[os.getenv('FLASK_ENV', 'default')]
        self.timeout = self.config.AI_TIMEOUT
    
    def _get_ai_config(self, user_config):
        """获取 AI 配置，优先使用用户配置"""
        api_key = user_config.get('api_key') or self.config.get('AI_API_KEY')
        api_url = user_config.get('api_url') or self.config.get('AI_API_URL')
        
        if not api_key or not api_url:
            raise ValueError('AI API configuration is missing')
        
        return {
            'api_key': api_key,
            'api_url': api_url,
            'model': user_config.get('model', '')
        }
    
    def get_completion(self, api_key, api_url, ai_model, system_prompt, user_question):
        client = OpenAI(api_key=api_key, base_url=api_url)
        completion = client.chat.completions.create(
            model=ai_model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_question}
            ],
            timeout=self.timeout
        )
        content = completion.choices[0].message.content
        return '\n'.join(filter(lambda line: line.find('```') == -1, content.split('\n')))
    
    def generate_generator(self, context, api_key, api_url, ai_model):
        system_prompt = """
你是一个专业的程序设计竞赛助手，专门为用户编写测试数据生成器。你需要使用 C++20 和 testlib.h 来写数据生成器。你需要从题目描述中获取数据输入的格式，如果题目描述没有给出，你需要根据用户的代码来推断。你的生成器生成的数据必须严格满足题目的约束条件，并且要把数据大小控制在用户可以比较轻松地调试的范围。在此基础上，可以尽量覆盖边界情况。注意，**不要**使用任何命令行参数来传递参数，如果你有可调整的参数，请直接写在代码里，最好使用 constexpr 变量来方便用户调整。回答时只需要给出生成器代码，不要输出任何多余的东西，重复一遍：**只需要给出生成器代码，不要输出任何多余的东西**。
"""
        user_question = f"""
题目描述如下：

{context.get('description', 'No description provided')}

用户代码如下：

{context.get('user_code', 'No user code provided')}
"""
        return self.get_completion(api_key, api_url, ai_model, system_prompt, user_question)
    
    def generate_standard(self, context, api_key, api_url, ai_model):
        system_prompt = """
你是一个专业的程序设计竞赛助手，专门为用户生成可供对拍的正确代码。你需要使用 C++20 编写一个在数据范围比较小的时候能够通过的代码。你编写的代码**不需要**拥有足够通过题目数据范围内的所有数据的效率，但是必须保证能够在比较小的数据下运行并且能够输出正确的答案。注意考虑各种边界情况地处理，比如数组越界、整型溢出、死循环等等。你需要从题目描述中获得输入输出的格式，如果题目描述没有给出，你需要从用户的代码推断。严格遵守题目的输入输出规范，**不要**输出任何多余信息（包括输入提示等等）。回答时只需要给出生成器代码，不要输出任何多余的东西，重复一遍：**只需要给出生成器代码，不要输出任何多余的东西**。
"""
        user_question = f"""
题目描述如下：

{context.get('description', 'No description provided')}

用户代码如下：

{context.get('user_code', 'No user code provided')}
"""
        return self.get_completion(api_key, api_url, ai_model, system_prompt, user_question)
