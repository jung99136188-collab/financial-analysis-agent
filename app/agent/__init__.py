"""
多 Agent 协作金融分析系统

架构：
    Coordinator (调度) → Researcher (研究) → Analyst (分析) → Writer (撰写)

每个 Agent 基于 ReAct 模式运行，通过工具调用完成子任务。
"""

from .base import BaseAgent
from .coordinator import CoordinatorAgent
from .researcher import ResearcherAgent
from .analyst import AnalystAgent
from .writer import WriterAgent

__all__ = [
    "BaseAgent",
    "CoordinatorAgent",
    "ResearcherAgent",
    "AnalystAgent",
    "WriterAgent",
]
