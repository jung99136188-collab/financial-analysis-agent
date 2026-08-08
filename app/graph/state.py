"""AgentState — LangGraph 共享状态"""

from typing import TypedDict, Annotated, Sequence
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """金融分析 Agent 共享状态"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    intent: str                          # direct | search | analyze | report
    research_data: str                   # Researcher 输出
    analysis_result: str                 # Analyst 输出
    final_report: str                    # Writer 输出
    deep_mode: bool                      # 是否深度分析模式
    error_count: int                     # 错误计数(用于 fallback)
