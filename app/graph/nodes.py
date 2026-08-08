"""LangGraph Nodes — 每个 Agent 作为一个 Graph Node

复用现有 Agent 类和工具，用 LangGraph 的 create_react_agent 包装。
"""

import sys
import os
from typing import Literal
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.graph.state import AgentState
from app.tools import ALL_TOOLS
from config.agent_config import (
    RESEARCHER_SYSTEM_PROMPT,
    ANALYST_SYSTEM_PROMPT_CORE,
    WRITER_SYSTEM_PROMPT,
    COORDINATOR_SYSTEM_PROMPT,
)


def _get_llm():
    """创建 LangChain ChatOpenAI 实例（兼容 DeepSeek/Gemini）"""
    from app.core.config import settings
    return ChatOpenAI(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        temperature=0.3,
    )


# ---- 研究员工具 (搜索 + K线 + 美股 + 股票识别) ----
_RESEARCHER_TOOLS = [
    t for t in ALL_TOOLS
    if t.name in ("search_financial_docs", "fetch_kline_data",
                   "fetch_us_stock_info", "identify_stocks")
]

# ---- 分析员工具 (汇总 + 对比 + UZI) ----
_ANALYST_TOOLS = [
    t for t in ALL_TOOLS
    if t.name in ("summarize_findings", "compare_stocks", "run_uzi_analysis")
]


def greeting_node(state: AgentState) -> AgentState:
    """欢迎信息 — 不调 LLM"""
    return {
        "messages": [AIMessage(content=(
            "你好！我是金融分析助手，可以帮你:\n"
            "• 搜索A股/美股金融文档（纪要/研报/公告/点评）\n"
            "• 分析股票盘面（K线/均线/形态/技术指标）\n"
            "• 获取美股数据（财报/SEC/评级）\n"
            "• 生成专业分析报告\n\n"
            "直接输入问题即可，例如: '分析茅台最近走势' 或 '搜索AIGC概念纪要'"
        ))],
        "intent": "greeting",
    }


def researcher_node(state: AgentState) -> AgentState:
    """研究员 Node — 搜集金融数据"""
    llm = _get_llm()
    agent = create_react_agent(llm, _RESEARCHER_TOOLS, state_modifier=RESEARCHER_SYSTEM_PROMPT)

    messages = list(state["messages"])
    if state.get("intent") in ("analyze", "report"):
        last = messages[-1].content if messages else ""
        task = f"请搜索以下问题的相关金融数据:\n{last}"
        messages[-1] = HumanMessage(content=task)

    result = agent.invoke({"messages": messages})

    # 提取最后一条 AI 消息作为研究数据
    research_data = ""
    for m in reversed(result.get("messages", [])):
        if isinstance(m, AIMessage) and m.content:
            research_data = m.content
            break

    return {
        "messages": result.get("messages", list(messages)),
        "research_data": research_data,
    }


def analyst_node(state: AgentState) -> AgentState:
    """分析员 Node — 深度分析数据"""
    llm = _get_llm()
    agent = create_react_agent(llm, _ANALYST_TOOLS, state_modifier=ANALYST_SYSTEM_PROMPT_CORE)

    research = state.get("research_data", "")
    question = ""
    for m in state.get("messages", []):
        if hasattr(m, "type") and m.type == "human":
            question = m.content
            break

    task = f"请分析以下研究数据，回答用户问题: {question}\n\n研究数据:\n{research[:6000]}"
    if state.get("deep_mode"):
        from config.agent_config import ANALYST_SYSTEM_PROMPT_EXTENDED
        # 拼接扩展 prompt（通过 system modifier 无法动态切换，这里附加到任务中）
        task = ANALYST_SYSTEM_PROMPT_EXTENDED + "\n\n" + task

    result = agent.invoke({"messages": [HumanMessage(content=task)]})

    analysis = ""
    for m in reversed(result.get("messages", [])):
        if isinstance(m, AIMessage) and m.content:
            analysis = m.content
            break

    return {
        "messages": state.get("messages", []),  # 保持原有消息不变
        "analysis_result": analysis,
    }


def writer_node(state: AgentState) -> AgentState:
    """撰写员 Node — 生成报告"""
    llm = _get_llm()
    agent = create_react_agent(llm, [], state_modifier=WRITER_SYSTEM_PROMPT)

    analysis = state.get("analysis_result", "")
    research = state.get("research_data", "")
    question = ""
    for m in state.get("messages", []):
        if hasattr(m, "type") and m.type == "human":
            question = m.content
            break

    task = (
        f"请根据以下分析材料撰写专业金融报告。\n\n"
        f"用户问题: {question}\n\n"
        f"分析材料:\n{analysis[:5000]}\n\n"
        f"原始数据(用于引用):\n{research[:3000]}"
    )

    result = agent.invoke({"messages": [HumanMessage(content=task)]})

    report = ""
    for m in reversed(result.get("messages", [])):
        if isinstance(m, AIMessage) and m.content:
            report = m.content
            break

    return {
        "messages": state.get("messages", []),
        "final_report": report,
    }
