"""
Coordinator Agent — 多 Agent 系统总调度师

职责：
    1. 理解用户意图
    2. 制定分析计划
    3. 委派任务给专业 Agent（Researcher、Analyst、Writer）
    4. 汇总结果交付用户

工具：
    - delegate_to_researcher: 委派信息搜集任务
    - delegate_to_analyst: 委派数据分析任务
    - delegate_to_writer: 委派报告撰写任务
    - ask_clarification: 向用户追问
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.agent_config import (
    COORDINATOR_SYSTEM_PROMPT,
)
from .base import BaseAgent

# ============================================================
# 工具定义
# ============================================================
COORDINATOR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "delegate_to_researcher",
            "description": (
                "将信息搜集任务委派给 Researcher Agent。"
                "Researcher 可以从金融数据源（纪要、研报、公告、点评）搜索相关信息。"
                "适用场景：需要查找某概念/板块/股票的相关文档、新闻、数据。"
                "提供清晰具体的搜索任务描述，Researcher 会返回结构化的搜索结果。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": (
                            "具体的搜索任务描述，例如："
                            "'搜索AIGC概念板块最近3个月的纪要和研究报告' 或 "
                            "'查找宁德时代近期的公告和点评'"
                        )
                    }
                },
                "required": ["task"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_to_analyst",
            "description": (
                "将数据分析任务委派给 Analyst Agent。"
                "Analyst 可以对搜集到的数据进行深度分析、对比、提炼核心观点。"
                "适用场景：需要分析趋势、对比股票、提取关键指标、评估风险。"
                "确保提供充足的数据给 Analyst 分析。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": (
                            "具体的分析任务描述，应包含："
                            "1. 需要分析什么数据（附上 Researcher 返回的关键结果）"
                            "2. 分析侧重点（趋势/对比/风险/机会）"
                        )
                    }
                },
                "required": ["task"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_to_writer",
            "description": (
                "将报告撰写任务委派给 Writer Agent。"
                "Writer 可以将分析结果撰写为专业的金融研究报告。"
                "适用场景：需要生成完整的分析报告、投资建议书、数据周报等。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": (
                            "具体的撰写任务描述，应包含："
                            "1. 报告主题"
                            "2. 需要使用的分析材料"
                            "3. 报告风格要求（深度研究/快速简报/数据周报）"
                        )
                    }
                },
                "required": ["task"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_clarification",
            "description": (
                "当用户问题不够清晰、信息不足以做出判断时，向用户追问。"
                "例如：概念模糊、时间范围不明确、需要指定具体股票等。"
                "不要在能直接回答时使用此工具。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "向用户提出的澄清问题"
                    }
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deliver_final_answer",
            "description": (
                "向用户交付最终答案。当你认为已经获得了足够的信息来回答用户的问题时，"
                "调用此工具将最终结果输出。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "string",
                        "description": "最终回答内容，整合了各 Agent 的结果"
                    }
                },
                "required": ["answer"]
            }
        }
    }
]


# ============================================================
# CoordinatorAgent
# ============================================================

class CoordinatorAgent(BaseAgent):
    """多 Agent 系统总调度师"""

    def __init__(self, llm_client, researcher=None, analyst=None, writer=None):
        """
        Args:
            llm_client: LLMClient 实例
            researcher: ResearcherAgent 实例
            analyst: AnalystAgent 实例
            writer: WriterAgent 实例
        """
        self._researcher = researcher
        self._analyst = analyst
        self._writer = writer

        # 工具处理器
        tool_handlers = {
            "delegate_to_researcher": self._handle_delegate_researcher,
            "delegate_to_analyst": self._handle_delegate_analyst,
            "delegate_to_writer": self._handle_delegate_writer,
            "ask_clarification": self._handle_ask_clarification,
            "deliver_final_answer": self._handle_deliver_answer,
        }

        super().__init__(
            name="Coordinator",
            system_prompt=COORDINATOR_SYSTEM_PROMPT,
            tools=COORDINATOR_TOOLS,
            llm_client=llm_client,
            tool_handlers=tool_handlers,
        )

    # ---- 工具处理器 ----

    def _handle_delegate_researcher(self, args):
        task = args.get("task", "")
        print(f"\n{'='*50}")
        print(f"[Coordinator] → 委派 Researcher: {task[:100]}...")
        print(f"{'='*50}")
        if self._researcher:
            result = self._researcher.run(task)
            print(f"[Coordinator] ← Researcher 返回 {len(result)} 字符")
            return result
        return "错误: Researcher Agent 未初始化"

    def _handle_delegate_analyst(self, args):
        task = args.get("task", "")
        print(f"\n{'='*50}")
        print(f"[Coordinator] → 委派 Analyst: {task[:100]}...")
        print(f"{'='*50}")
        if self._analyst:
            result = self._analyst.run(task)
            print(f"[Coordinator] ← Analyst 返回 {len(result)} 字符")
            return result
        return "错误: Analyst Agent 未初始化"

    def _handle_delegate_writer(self, args):
        task = args.get("task", "")
        print(f"\n{'='*50}")
        print(f"[Coordinator] → 委派 Writer: {task[:100]}...")
        print(f"{'='*50}")
        if self._writer:
            result = self._writer.run(task)
            print(f"[Coordinator] ← Writer 返回 {len(result)} 字符")
            return result
        return "错误: Writer Agent 未初始化"

    def _handle_ask_clarification(self, args):
        question = args.get("question", "")
        # 标记这是需要用户回答的问题
        return f"[需要用户澄清] {question}"

    def _handle_deliver_answer(self, args):
        # deliver_final_answer 只是个标记，实际内容通过返回值传递
        return args.get("answer", "")

    # ---- 运行入口 ----

    def chat(self, user_question: str) -> str:
        """
        处理用户问题并返回回答。

        这是对外的对话接口，内部调用 run() 执行 ReAct 循环。
        """
        # 将 context 信息注入到任务描述中
        task = user_question
        if self.conversation_history:
            recent = self.conversation_history[-2:]
            history_summary = "\n".join(
                f"用户: {h['q'][:100]}\n助手: {h['a'][:200]}" for h in recent
            )
            task = f"【对话历史】\n{history_summary}\n\n【当前问题】\n{user_question}"

        result = self.run(task)

        # 记录对话历史
        self.add_to_history(user_question, result)

        return result
