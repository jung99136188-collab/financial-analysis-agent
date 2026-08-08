"""
Agent 基类 — ReAct 循环引擎

实现 Think → Act → Observe → Think 循环，
通过注入的 LLMClient 驱动工具调用，不绑定具体模型。
"""

import json
from config.agent_config import MAX_ITERATIONS


class BaseAgent:
    """
    ReAct Agent 基类。

    子类只需提供:
        - name: Agent 名称
        - system_prompt: 系统提示词
        - tools: 工具列表 (OpenAI function calling 格式)
        - llm_client: LLMClient 实例（依赖注入）
        - tool_handlers: {tool_name: callable} 工具执行函数映射
    """

    def __init__(self, name, system_prompt, tools, llm_client, tool_handlers=None):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools
        self.llm = llm_client                # LLMClient 实例（统一接口）
        self.model = llm_client.model_name    # 兼容旧代码
        self.tool_handlers = tool_handlers or {}
        self.max_iterations = MAX_ITERATIONS
        self.conversation_history = []  # 跨轮次记忆（Coordinator 用）

    def run(self, task: str, context: dict = None) -> str:
        """
        执行 ReAct 循环。

        Args:
            task: 当前任务描述
            context: 可选的上下文字典（如历史对话）

        Returns:
            Agent 的最终文本回复
        """
        messages = self._build_initial_messages(task)

        for iteration in range(self.max_iterations):
            print(f"  [{self.name}] 推理轮次 {iteration + 1}/{self.max_iterations}")

            response = self._call_llm(messages)

            if response is None:
                return f"[{self.name}] LLM 调用失败，请稍后重试。"

            # 检查是否有 tool_calls
            tool_calls = self._extract_tool_calls(response)

            if tool_calls:
                print(f"  [{self.name}] 决定调用 {len(tool_calls)} 个工具")

                # 将 assistant 消息加入历史
                messages.append(response)

                for tc in tool_calls:
                    tool_name = tc.get("function", {}).get("name", "unknown")
                    tool_args = self._parse_tool_args(tc)

                    print(f"  [{self.name}] → 执行工具: {tool_name}")

                    # 执行工具
                    tool_result = self._execute_tool(tool_name, tool_args)

                    # 截断过长结果，避免超出 token 限制
                    if len(tool_result) > 8000:
                        tool_result = tool_result[:8000] + "\n...(内容过长已截断)"

                    # 将工具结果加入消息历史
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", f"call_{iteration}"),
                        "content": tool_result,
                    })
            else:
                # 没有 tool_calls，返回最终文本
                content = response.get("content", "")
                print(f"  [{self.name}] 完成推理，返回 {len(content)} 字符")
                return content

        return f"[{self.name}] 达到最大推理轮次 ({self.max_iterations})，任务未完成。请尝试简化问题。"

    def _build_initial_messages(self, task):
        """构建初始消息列表"""
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]
        # 如果有历史对话上下文，加入
        if self.conversation_history:
            for entry in self.conversation_history[-6:]:  # 最近3轮对话
                messages.append({"role": "user", "content": entry.get("q", "")})
                messages.append({"role": "assistant", "content": entry.get("a", "")[:500]})

        messages.append({"role": "user", "content": task})
        return messages

    def _call_llm(self, messages):
        """
        通过 LLMClient 统一接口调用模型。

        Returns:
            OpenAI 格式的 message 对象，或 None
        """
        response = self.llm.chat(
            messages=messages,
            tools=self.tools if self.tools else None,
        )
        # 检查是否是错误返回（content 包含错误信息且无 tool_calls）
        content = response.get("content", "")
        if content and content.startswith("模型调用"):
            print(f"  [{self.name}] {content}")
            return None
        return response

    def _extract_tool_calls(self, message):
        """从 LLM 响应中提取 tool_calls"""
        if message is None:
            return []
        tool_calls = message.get("tool_calls")
        return tool_calls if tool_calls else []

    def _parse_tool_args(self, tool_call):
        """解析工具调用参数"""
        raw_args = tool_call.get("function", {}).get("arguments", "{}")
        if isinstance(raw_args, str):
            try:
                return json.loads(raw_args)
            except json.JSONDecodeError:
                print(f"  [{self.name}] 警告: 无法解析工具参数: {raw_args[:200]}")
                return {}
        return raw_args

    def _execute_tool(self, tool_name, tool_args):
        """
        执行工具并返回结果。

        子类可以重写此方法实现自定义工具调度。
        默认从 tool_handlers 字典查找。
        """
        handler = self.tool_handlers.get(tool_name)
        if handler:
            try:
                result = handler(tool_args)
                return str(result)
            except Exception as e:
                return f"工具执行错误: {str(e)}"
        else:
            return f"未知工具: {tool_name}，可用工具: {list(self.tool_handlers.keys())}"

    def add_to_history(self, question, answer):
        """记录对话历史（供多轮对话使用）"""
        self.conversation_history.append({"q": question, "a": answer})
        # 最多保留10轮
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]
