"""
Agent 基类 — ReAct 循环引擎（token 优化版）

实现 Think → Act → Observe → Think 循环，
通过注入的 LLMClient 驱动工具调用，不绑定具体模型。

优化点:
    - 工具结果按类型动态截断 (TOOL_RESULT_LIMITS)
    - 对话历史压缩为摘要
    - System Prompt 放首位享受缓存
    - 各 Agent 独立 MAX_ITERATIONS
"""

import json
from config.agent_config import (
    MAX_ITERATIONS,
    MAX_ITERATIONS_MAP,
    TOOL_RESULT_LIMITS,
)


class BaseAgent:
    """ReAct Agent 基类"""

    def __init__(self, name, system_prompt, tools, llm_client, tool_handlers=None,
                 extended_prompt=None):
        self.name = name
        self.system_prompt = system_prompt
        self.extended_prompt = extended_prompt        # 按需拼接的扩展 Prompt
        self.tools = tools if tools else []
        self.llm = llm_client
        self.model = llm_client.model_name
        self.tool_handlers = tool_handlers or {}
        self.max_iterations = MAX_ITERATIONS_MAP.get(name, MAX_ITERATIONS)
        self.conversation_history = []
        self._token_count = 0                          # 累计 token 估算

    # ================================================================
    # ReAct 循环
    # ================================================================

    def run(self, task: str, deep_mode: bool = False) -> str:
        """执行 ReAct 循环。

        Args:
            task: 当前任务描述
            deep_mode: 是否启用扩展 Prompt（深度分析时用）
        """
        messages = self._build_initial_messages(task, deep_mode=deep_mode)

        for iteration in range(self.max_iterations):
            print(f"  [{self.name}] 轮次 {iteration + 1}/{self.max_iterations} "
                  f"(est. tokens: ~{self._token_count})")

            response = self._call_llm(messages)

            if response is None:
                return f"[{self.name}] LLM 调用失败。"

            tool_calls = self._extract_tool_calls(response)

            if tool_calls:
                print(f"  [{self.name}] → {len(tool_calls)} 个工具调用")
                messages.append(response)

                for tc in tool_calls:
                    tool_name = tc.get("function", {}).get("name", "unknown")
                    tool_args = self._parse_tool_args(tc)

                    print(f"  [{self.name}] 执行: {tool_name}")
                    tool_result = self._execute_tool(tool_name, tool_args)

                    # 动态截断
                    limit = TOOL_RESULT_LIMITS.get(tool_name, TOOL_RESULT_LIMITS.get("default", 2500))
                    if len(tool_result) > limit:
                        tool_result = tool_result[:limit] + "\n...(已截断)"

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", f"call_{iteration}"),
                        "name": tool_name,    # Gemini 适配器需要此字段
                        "content": tool_result,
                    })
            else:
                content = response.get("content", "")
                self._update_token_estimate(response)
                print(f"  [{self.name}] 完成 ({len(content)} 字符)")
                return content

        return f"[{self.name}] 达到最大轮次 ({self.max_iterations})，任务未完成。"

    # ================================================================
    # 消息构建（缓存优化）
    # ================================================================

    def _build_initial_messages(self, task, deep_mode=False):
        """构建初始消息列表 — System Prompt 放第一享受缓存"""
        # 核心 System Prompt（放第一，DeepSeek 自动缓存）
        full_prompt = self.system_prompt
        if deep_mode and self.extended_prompt:
            full_prompt += self.extended_prompt

        messages = [
            {"role": "system", "content": full_prompt},
        ]

        # 对话历史压缩为 1 条摘要
        if self.conversation_history:
            summary = self._summarize_history()
            if summary:
                messages.append({"role": "user", "content": summary})
                messages.append({"role": "assistant", "content": "了解。"})

        messages.append({"role": "user", "content": task})

        # 粗估 token（4 字符 ≈ 1 token 的简单估算）
        raw = json.dumps(messages, ensure_ascii=False)
        self._token_count = len(raw) // 4
        return messages

    def _summarize_history(self):
        """压缩最近对话历史为 1 条简短摘要"""
        recent = self.conversation_history[-3:]
        if not recent:
            return ""
        lines = []
        for h in recent:
            q = h.get("q", "")[:80]
            a = h.get("a", "")[:120]
            lines.append(f"Q: {q}\nA: {a}")
        return "【对话历史】\n" + "\n---\n".join(lines)

    def _update_token_estimate(self, response):
        """从 API 响应更新 token 估算"""
        usage = response.get("usage", {})
        if usage:
            self._token_count = usage.get("total_tokens", self._token_count)

    # ================================================================
    # LLM 调用
    # ================================================================

    def _call_llm(self, messages):
        """通过 LLMClient 统一接口调用"""
        response = self.llm.chat(
            messages=messages,
            tools=self.tools if self.tools else None,
        )
        # 错误检测：适配器返回的 content 以特定错误前缀开头
        content = response.get("content", "") or ""
        error_prefixes = ("模型调用失败", "模型调用超时", "模型调用异常",
                          "Gemini 响应解析失败", "API error")
        if any(content.startswith(p) for p in error_prefixes):
            print(f"  [{self.name}] {content}")
            return None
        return response

    # ================================================================
    # 工具调度
    # ================================================================

    def _extract_tool_calls(self, message):
        if message is None:
            return []
        tc = message.get("tool_calls")
        return tc if tc else []

    def _parse_tool_args(self, tool_call):
        raw_args = tool_call.get("function", {}).get("arguments", "{}")
        if isinstance(raw_args, str):
            try:
                return json.loads(raw_args)
            except json.JSONDecodeError:
                print(f"  [{self.name}] 参数解析失败: {raw_args[:100]}")
                return {}
        return raw_args

    def _execute_tool(self, tool_name, tool_args):
        handler = self.tool_handlers.get(tool_name)
        if handler:
            try:
                return str(handler(tool_args))
            except Exception as e:
                return f"工具错误: {str(e)}"
        return f"未知工具: {tool_name}"

    def add_to_history(self, question, answer):
        self.conversation_history.append({"q": question, "a": answer})
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]
