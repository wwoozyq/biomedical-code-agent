"""
LLM 客户端 - 通过 OpenAI 兼容接口调用 LLM（支持通义千问、DeepSeek 等）
"""

import os
import time
from typing import List, Dict, Any, Optional
from openai import OpenAI


class LLMClient:
    """通用 LLM 客户端（OpenAI 兼容接口）"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        model: str = "qwen-plus",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ):
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "需要提供 API Key，可通过参数传入或设置环境变量 DASHSCOPE_API_KEY"
            )
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.client = OpenAI(api_key=self.api_key, base_url=base_url)

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """发送对话请求，返回助手回复文本（带重试）"""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature if temperature is not None else self.temperature,
                    max_tokens=max_tokens or self.max_tokens,
                )
                content = resp.choices[0].message.content
                if content is None:
                    content = ""
                return content
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait = self.retry_delay * (attempt + 1)
                    print(f"⚠️ LLM 调用失败 (尝试 {attempt+1}/{self.max_retries}): {e}")
                    print(f"   {wait}s 后重试...")
                    time.sleep(wait)
        raise RuntimeError(f"LLM 调用失败，已重试 {self.max_retries} 次: {last_error}")
