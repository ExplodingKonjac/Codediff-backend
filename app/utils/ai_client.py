from openai import OpenAI
from base64 import b64encode
from flask import current_app
from app.exceptions import APIError
from PIL import Image
import logging
import base64
import io

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
    - **Parameters Affecting Complexity (e.g., $N, M, K$):** Assume these are small (e.g., $N \le 20$) and will not cause a Time Limit Exceeded error, even for exponential solutions (e.g., $O(2^N)$ or $O(N!)$). In other words, if you find out that a brute-force solution seems impossible under the given data range, just ignore the data range and assume it is acceptable.
    - Implement the most direct, mathematically obvious solution. **Do not optimize.** Use methods like: complete enumeration, DFS/BFS for state-space search, or direct simulation.

2.  **Value Range Safety (The "Correctness" Rule):**
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

    def __init__(self, api_key, base_url, ai_model):
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._ai_model = ai_model
    
    def _construct_completion(self, system_prompt, user_question, stream: bool = False):
        return self._client.chat.completions.create(
            model=self._ai_model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_question}
            ],
            stream=stream,
            timeout=current_app.config['AI_TIMEOUT']
        )

    def _stream_completion(self, system_prompt, user_question):
        stream = self._construct_completion(
            system_prompt,
            user_question,
            stream=True
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if (content := getattr(delta, 'content', None)) is not None:
                yield content

    def generate_generator(self, context):
        if 'description' not in context:
            raise APIError('You must provided problem description')

        return self._construct_completion(
            self.GENERATOR_SYSTEM_PROMPT,
            self.GENERATOR_USER_PROMPT.format(context['description'])
        )

    def generate_standard(self, context):
        if 'description' not in context:
            raise APIError('You must provided problem description')

        return self._construct_completion(
            self.STANDARD_SYSTEM_PROMPT,
            self.STANDARD_USER_PROMPT.format(context['description'])
        )

    def generate_generator_stream(self, context):
        if 'description' not in context:
            raise APIError('You must provided problem description')

        return self._stream_completion(
            self.GENERATOR_SYSTEM_PROMPT,
            self.GENERATOR_USER_PROMPT.format(context['description'])
        )

    def generate_standard_stream(self, context):
        if 'description' not in context:
            raise APIError('You must provided problem description')

        return self._stream_completion(
            self.STANDARD_SYSTEM_PROMPT,
            self.STANDARD_USER_PROMPT.format(context['description'])
        )


class OCRClient:
    SYSTEM_PROMPT = """
Extract the original programming problem description from the provided image, which may be in Chinese or English. Output the content strictly in markdown format, preserving all expressions and the original language. If no programming problem description is found in the image, respond with 'Problem description not found' only.
"""
    def __init__(self, api_key, base_url, ai_model) -> None:
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._ai_model = ai_model
    
    @classmethod
    def _get_data_url(cls, image: Image):
        buffer = io.BytesIO()
        image.convert('RGB').save(buffer, format='JPEG')
        return 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    def _construct_completion(self, image: Image, stream: bool = False):
        messages = [
            {'role': 'system', 'content': self.SYSTEM_PROMPT},
            {'role': 'user', 'content': [
                {
                    'type': 'image_url',
                    'image_url': {'url': self._get_data_url(image)}
                }
            ]}
        ]
        return self._client.chat.completions.create(
            model=self._ai_model,
            messages=messages,
            stream=stream,
            timeout=current_app.config['AI_TIMEOUT']
        )
    
    def perform_ocr(self, image: Image):
        completion = self._construct_completion(image)
        return completion.choices[0].message.content

    def perform_ocr_stream(self, image: Image):
        stream = self._construct_completion(image, stream=True)
        for chunk in stream:
            delta = chunk.choices[0].delta
            if (content := getattr(delta, 'content', None)) is not None:
                yield content
