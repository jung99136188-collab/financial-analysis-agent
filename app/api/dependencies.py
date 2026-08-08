"""FastAPI 依赖注入"""

from functools import lru_cache
from langgraph.graph.state import CompiledStateGraph
from app.graph import get_graph
from app.core.config import Settings, settings


@lru_cache()
def get_settings() -> Settings:
    return settings


def get_agent_graph() -> CompiledStateGraph:
    return get_graph()
