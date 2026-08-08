"""
LLM 适配层 — 统一接口 + 工厂函数

所有 Agent 通过此层的统一接口调用 LLM，不关心底层是 DeepSeek 还是 Gemini。
"""


class LLMClient:
    """LLM 统一接口

    所有适配器都实现此接口。输入/输出统一使用 OpenAI 兼容格式，
    非 OpenAI 格式的 API（如 Gemini）在适配器内部做转换。
    """

    def chat(self, messages, tools=None, temperature=0.3, max_tokens=4096):
        """
        发送消息并获取回复。

        Args:
            messages: list of dict, OpenAI 格式
                [{"role": "system", "content": "..."},
                 {"role": "user", "content": "..."},
                 {"role": "assistant", "content": "...", "tool_calls": [...]},
                 {"role": "tool", "tool_call_id": "...", "content": "..."}]
            tools: list of dict, OpenAI function calling 格式
            temperature: float
            max_tokens: int

        Returns:
            dict: OpenAI 格式的 message 对象
                {"role": "assistant", "content": "...", "tool_calls": [...]}
                其中 tool_calls 格式:
                [{"id": "call_xxx", "type": "function",
                  "function": {"name": "...", "arguments": "{...}"}}]
        """
        raise NotImplementedError

    @property
    def model_name(self):
        """返回当前使用的模型名称"""
        raise NotImplementedError


def create_llm_client(provider_config: dict) -> LLMClient:
    """工厂函数 — 根据配置创建对应的 LLM 客户端

    Args:
        provider_config: dict, 包含:
            - provider: "openai_compatible" 或 "gemini"
            - api_key: str
            - base_url: str (openai_compatible 需要)
            - model: str

    Returns:
        LLMClient 实例
    """
    provider = provider_config.get("provider", "").lower()

    if provider == "openai_compatible":
        from .openai_compatible import OpenAICompatibleClient
        return OpenAICompatibleClient(provider_config)
    elif provider == "gemini":
        from .gemini import GeminiClient
        return GeminiClient(provider_config)
    else:
        raise ValueError(
            f"Unknown provider: '{provider}'. "
            f"Supported: 'openai_compatible', 'gemini'"
        )
