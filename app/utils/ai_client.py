from openai import OpenAI
from anthropic import Anthropic
from base64 import b64encode
from app.config import config as app_config
from app.exceptions import APIError
import logging
import os

logger = logging.getLogger(__name__)

class CodeGenerationClient:
    GENERATOR_SYSTEM_PROMPT = """
## Task: Competitive Programming Data Generator

You are a specialized AI assistant whose sole task is to generate **C++ test data generators** for competitive programming problems.

Your output must be **raw, executable C++ code** using the `testlib.h` library.

## User Input Specification

The user will provide the problem details in two distinct, mandatory sections:

1.  **PROBLEM DESCRIPTION:** The full text of the problem statement, outlining the task and logic.
2.  **CONSTRAINTS:** A list of all numerical and logical constraints (e.g., $N \le 10^5$, $1 \le A[i] \le 10^9$, Graph must be connected).

## Generation Requirements and Rules

1. Technical Specification
    - **Language & Library:** Use **C++17** and the competitive programming header **`testlib.h`**.
    - **Setup:** The code must include the necessary headers (`<iostream>`, `testlib.h`) and a `main` function with a call to `registerGen(argc, argv, 1);`.
    - **Output:** All generated data must be written to standard output (using `cout` or $testlib$'s `printf`/`printL` functions).
    - **Argument Control:** **DO NOT** use command line arguments for configuration. Use **`constexpr`** variables to set and adjust all numerical parameters (e.g., maximum size, value ranges).

2. Data Quality & Constraints
    - **Format:** The generated data must strictly adhere to the exact input format described in the Problem Description.
    - **Validity:** The data must satisfy **ALL** specified constraints.
    - **Debugging Size:** To ensure easy debugging, the total generated output size (e.g., number of elements $N$, or total lines of input) should be kept relatively small, typically **between 5 and 50** lines/elements.

3. Edge Case Coverage (Critical)
    - The generator must intelligently cover critical edge cases related to the problem logic and constraints. Prioritize:
    - **Boundary Cases:** Minimum constraint values (e.g., $N=1$) and maximum constraint values (e.g., $N=50$ or whatever is set by the `constexpr` maximum).
    - **Uniformity:** Cases where all elements are identical (e.g., $A[i] = 1$ for all $i$).
    - **Diversity:** Cases where all elements are maximally diverse (distinct, or covering the full range of $1$ to $10^9$).
    - **Ordering:** Strictly sorted or strictly reverse-sorted inputs (if order matters).
    - **Problem-Specific Edges:** Zeroes, negative numbers (if allowed), large prime numbers, or structures like linear chains/stars in graphs.

## Final Output

**Produce raw C++ code only.** Do not include any extra explanatory text, comments outside of the code block, or Markdown notations (e.g., **DO NOT** use ```cpp ... ```).
"""
    GENERATOR_USER_PROMPT = """
Write the data generator for the following problem:

{}
"""
    STANDARD_SYSTEM_PROMPT = """
**Role:** You are a C++17 Reference Implementation Generator. Your purpose is to generate logically perfect, naive brute-force solutions for competitive programming problems. These solutions are used as "Reference Code" for stress testing (checking against optimized solutions).

**Input:** A competitive programming problem description.
**Output:** Raw C++17 source code.

---

### **Critical Rules**

1.  **Complexity Assumption (The "Naive" Rule):**
    - **Parameters Affecting Complexity (e.g., $N, M, K$):** Assume these are small (e.g., $N \le 20$) and will not cause a Time Limit Exceeded error, even for exponential solutions (e.g., $O(2^N)$ or $O(N!)$).
    - Implement the most direct, mathematically obvious solution. **Do not optimize.** Use methods like: complete enumeration, DFS/BFS for state-space search, or direct simulation.

2.  **Value Range Safety (The "Correctness" Rule):**
    - **Parameters Affecting Value (e.g., $A_i, V$):** Treat the magnitude and range of these parameters **very seriously**. Do not assume they are small.
    - **Data Types:** Use `long long` (`int64_t`) by default for *all* integer arithmetic (inputs, variables, intermediate results, and outputs) to prevent overflow, unless the problem guarantees all values fit in a 32-bit `int`. Use `double` or `long double` for floating-point values as appropriate.
    - **Logical Correctness is paramount.** The code must produce the exact right answer for valid inputs, handling large values and negative values correctly.
    - Handle all edge cases (e.g., $N=0$, empty arrays) as defined by the problem.

3.  **Formatting & IO:**
    - Use standard C++ I/O (`std::cin`, `std::cout`).
    - **NO Markdown:** Do not use code blocks (like ```cpp ... ```). Do not write introductory or concluding text.
    - **Output ONLY the code.** The output must start with the first preprocessor directive (`#include`, `using namespace`, etc.) and end with the closing brace `}` of the `main` function.
"""
    STANDARD_USER_PROMPT = """
Generate the brute-force C++17 solution for the following problem:

{}
"""

    def __init__(self):
        self.config = app_config[os.getenv('FLASK_ENV', 'default')]

    def _get_ai_config(self, user_config):
        """获取 AI 配置，优先使用用户配置"""
        api_key = user_config.get('api_key')
        api_url = user_config.get('api_url')

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
        if 'description' not in context:
            raise APIError('You must provided problem description')

        return self.get_completion(
            api_key, api_url, ai_model,
            self.GENERATOR_SYSTEM_PROMPT,
            self.GENERATOR_USER_PROMPT.format(context['description'])
        )

    def generate_standard(self, context, api_key, api_url, ai_model):
        if 'description' not in context:
            raise APIError('You must provided problem description')

        return self.get_completion(
            api_key, api_url, ai_model,
            self.STANDARD_SYSTEM_PROMPT,
            self.STANDARD_USER_PROMPT.format(context['description']),
        )

    def generate_generator_stream(self, context, api_key, api_url, ai_model):
        if 'description' not in context:
            raise APIError('You must provided problem description')

        return self.stream_completion(
            api_key, api_url, ai_model,
            self.GENERATOR_SYSTEM_PROMPT,
            self.GENERATOR_USER_PROMPT.format(context['description']),
        )

    def generate_standard_stream(self, context, api_key, api_url, ai_model):
        if 'description' not in context:
            raise APIError('You must provided problem description')

        return self.stream_completion(
            api_key, api_url, ai_model,
            self.STANDARD_SYSTEM_PROMPT,
            self.STANDARD_USER_PROMPT.format(context['description'])
        )

class OCRClient:
    PROMPT = """
The image given to you contains description of a programming problem, in Chinese or English. You should output the ORIGINAL content in markdown format. DON'T change the expressions. DON'T change the language. Ouput markdown format text ONLY.
"""
    def __init__(self) -> None:
        self._client = Anthropic()
    
    def perform_ocr(self, image_path: str | os.PathLike):
        with open(image_path, 'rb') as f:
            image_base64 = b64encode(f.read()).decode('ascii')

        user_content = [
            {
                'type': 'image',
                'source': {
                    'type': 'base64',
                    'media_type': 'image/jpeg',
                    'data': image_base64
                }
            },
            {'type': 'text', 'text': self.PROMPT}
        ]
        message = self._client.messages.create(
            max_tokens=2048,
            messages=[{'role': 'user', 'content': user_content}],
            model='claude-haiku-4-5',
        )
        return '\n'.join(i.text for i in message.content if i.type == 'text')
