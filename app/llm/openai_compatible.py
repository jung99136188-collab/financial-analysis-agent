"""
OpenAI 兼容适配器

支持所有 OpenAI-compatible API:
    - DeepSeek (官方 / 火山引擎 / 代理)
    - OpenAI (GPT-4, GPT-4o, etc.)
    - 任何兼容 /v1/chat/completions 的服务
"""

import requests
from . import LLMClient


class OpenAICompatibleClient(LLMClient):
    """OpenAI 兼容 API 客户端"""

    def __init__(self, config: dict):
        self.base_url = config.get("base_url", "").rstrip("/")
        self.api_key = config.get("api_key", "")
        self._model = config.get("model", "")
        self._timeout = config.get("timeout", 120)

    @property
    def model_name(self):
        return self._model

    def chat(self, messages, tools=None, temperature=0.3, max_tokens=4096):
        """调用 OpenAI 兼容 API"""
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=self._timeout)

            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]

            # 错误处理
            error_msg = f"API error {response.status_code}"
            try:
                error_detail = response.json()
                error_msg += f": {error_detail}"
            except Exception:
                error_msg += f": {response.text[:300]}"
            print(f"  [LLM:OpenAI] {error_msg}")
            return {"role": "assistant", "content": f"模型调用失败: {error_msg}"}

        except requests.exceptions.Timeout:
            print(f"  [LLM:OpenAI] 请求超时 ({self._timeout}s)")
            return {"role": "assistant", "content": "模型调用超时，请稍后重试。"}

        except Exception as e:
            print(f"  [LLM:OpenAI] 请求异常: {str(e)}")
            return {"role": "assistant", "content": f"模型调用异常: {str(e)}"}
