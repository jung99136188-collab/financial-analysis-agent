"""条件路由逻辑"""

import json
import sys
import os
from langchain_core.messages import HumanMessage


def classify_intent(state: "AgentState") -> dict:
    """从用户最后一条消息中提取意图 — 关键词匹配(0 token)"""
    messages = state.get("messages", [])
    if not messages:
        return {"intent": "greeting", "deep_mode": False}

    last = messages[-1]
    q = (last.content if hasattr(last, "content") else str(last)).lower()

    deep = any(w in q for w in ["深度", "详细", "deep", "全面", "估值", "dcf"])
    intent = "greeting"

    if any(w in q for w in ["你好", "帮助", "怎么用", "谢谢", "再见", "hello", "hi", "help"]):
        intent = "greeting"
    elif any(w in q for w in ["搜索", "查", "找", "有没有", "search", "find"]):
        intent = "search"
    elif any(w in q for w in ["报告", "report", "生成", "写", "write"]):
        intent = "report"
    else:
        intent = "analyze"  # 默认分析路径

    return {"intent": intent, "deep_mode": deep}


def route_by_intent(state: "AgentState") -> str:
    """根据意图路由到不同节点"""
    intent = state.get("intent", "greeting")
    routes = {
        "greeting": "greeting",
        "search": "researcher",
        "analyze": "researcher",
        "report": "researcher",
    }
    return routes.get(intent, "researcher")


def route_after_research(state: "AgentState") -> str:
    """Researcher 之后的路由"""
    intent = state.get("intent", "analyze")
    if intent == "search":
        return "done"
    return "analyst"


def route_after_analysis(state: "AgentState") -> str:
    """Analyst 之后的路由"""
    intent = state.get("intent", "analyze")
    if intent == "report":
        return "writer"
    # 有足够分析结果就结束，否则继续
    analysis = state.get("analysis_result", "")
    if len(analysis) > 200:
        return "done"
    return "writer"  # 不够详细的话让 writer 补
