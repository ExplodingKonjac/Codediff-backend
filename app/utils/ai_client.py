import requests
import json
import logging
import time
import os
from openai import OpenAI

from app.config import config as app_config

logger = logging.getLogger(__name__)

class AIClient:
    GENERATOR_SYSTEM_PROMPT = """
任务描述：作为专业的程序设计竞赛助手，你的职责是为用户编写一个测试数据生成器。请遵循以下要求来完成此任务：

- 使用的语言和库：C++17 和 testlib.h。
- 数据输入格式：首先尝试从题目描述中获取数据输入的具体格式。如果题目描述未提供足够的信息，则需根据用户的代码逻辑推断出合适的输入格式。
- 数据格式**严格遵守**题目描述，不要自己更改格式。
- 生成的数据必须严格遵守题目的所有约束条件。
- 尽量控制生成的数据规模，使其适合于用户进行轻松调试；同时尽可能覆盖各种边界情况以确保全面性。
- 不允许使用命令行参数传递任何配置选项。对于需要调整的参数，请直接在代码内部定义，并推荐使用 `constexpr` 类型变量以便于用户后续修改。

最终输出仅限于完整的生成器代码本身，不应包含任何形式的额外内容（如代码解释、Markdown标记等）。

**重要：使用 C++17 标准。不要生成任何 Markdown 代码标记（```cpp ... ```）。**
"""
    GENERATOR_USER_PROMPT = """
## 题目描述如下：

{}

## 用户代码如下：

{}
"""
    STANDARD_SYSTEM_PROMPT = """
请作为一个专业的程序设计竞赛助手，根据用户需求生成一段 C++17 代码。这段代码主要用于在数据规模较小时提供正确的解题方案（即，暴力解法）而不必考虑其在大规模数据集上的效率问题。**但是代码的正确性必须保证。**同时，请确保代码能够妥善处理各种边界情况，如数组越界、整型溢出以及避免陷入死循环等。

- 你需要从题目描述中提取输入输出的具体格式要求；如果题目描述中未明确指出，则应尝试从用户提供的现有代码样例中推断。
- 严格遵循题目的输入输出规范进行编码，确保不产生任何额外的输出信息（例如提示性文字）。
- 最终只需提交生成的代码本身，无需附加其他任何形式的内容或说明，也不要输出 Markdown 标记。

请基于上述指导原则编写满足条件的代码。

**重要：使用 C++17 标准。不要生成任何 Markdown 代码标记（```cpp ... ```）。必须使用最朴素的暴力解法（如搜索、穷举等等），正确性是第一要务。**
"""
    STANDARD_USER_PROMPT = """
## 题目描述如下:

{}

## 用户代码如下:

{}
"""

    def __init__(self):
        self.config = app_config[os.getenv('FLASK_ENV', 'default')]

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
            timeout=self.config.AI_TIMEOUT
        )
        content = completion.choices[0].message.content
        return '\n'.join(filter(lambda line: line.find('```') == -1, content.split('\n')))

    def stream_completion(self, api_key, api_url, ai_model, system_prompt, user_question):
        """流式获取AI完成响应"""
        try:
            client = OpenAI(api_key=api_key, base_url=api_url)
            stream = client.chat.completions.create(
                model=ai_model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_question}
                ],
                stream=True,
                timeout=self.config.AI_TIMEOUT
            )

            for chunk in stream:
                delta = chunk.choices[0].delta
                if (content := getattr(delta, 'content', None)) is not None:
                    yield 'code_chunk', content
            yield 'finish', None

        except Exception as e:
            logger.error(f'Streaming completion failed: {str(e)}')
            yield 'error', str(e)

    def generate_generator(self, context, api_key, api_url, ai_model):
        return self.get_completion(
            api_key, api_url, ai_model,
            self.GENERATOR_SYSTEM_PROMPT,
            self.GENERATOR_USER_PROMPT.format(
                context.get('description', 'No description provided'),
                context.get('user_code', 'No user code provided')
            )
        )

    def generate_standard(self, context, api_key, api_url, ai_model):
        return self.get_completion(
            api_key, api_url, ai_model,
            self.STANDARD_SYSTEM_PROMPT,
            self.STANDARD_USER_PROMPT.format(
                context.get('description', 'No description provided'),
                context.get('user_code', 'No user code provided')
            )
        )

    def generate_generator_stream(self, context, api_key, api_url, ai_model):
        return self.stream_completion(
            api_key, api_url, ai_model,
            self.GENERATOR_SYSTEM_PROMPT,
            self.GENERATOR_USER_PROMPT.format(
                context.get('description', 'No description provided'),
                context.get('user_code', 'No user code provided')
            )
        )

    def generate_standard_stream(self, context, api_key, api_url, ai_model):
        return self.stream_completion(
            api_key, api_url, ai_model,
            self.STANDARD_SYSTEM_PROMPT,
            self.STANDARD_USER_PROMPT.format(
                context.get('description', 'No description provided'),
                context.get('user_code', 'No user code provided')
            )
        )
