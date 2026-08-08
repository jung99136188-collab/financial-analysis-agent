"""StateGraph 构建 — LangGraph 企业级编排"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import AgentState
from app.graph.nodes import greeting_node, researcher_node, analyst_node, writer_node
from app.graph.routing import classify_intent, route_by_intent, route_after_research, route_after_analysis

# 图实例缓存
_graph = None


def build_graph() -> StateGraph:
    """构建并编译 StateGraph"""
    workflow = StateGraph(AgentState)

    # 注册 Node
    workflow.add_node("classify", classify_intent)
    workflow.add_node("greeting", greeting_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("writer", writer_node)

    # 设置入口
    workflow.set_entry_point("classify")

    # 条件路由: classify → 根据 intent 分发
    workflow.add_conditional_edges("classify", route_by_intent, {
        "greeting": "greeting",
        "researcher": "researcher",
    })

    # greeting → END
    workflow.add_edge("greeting", END)

    # researcher → 条件路由
    workflow.add_conditional_edges("researcher", route_after_research, {
        "analyst": "analyst",
        "done": END,
    })

    # analyst → 条件路由
    workflow.add_conditional_edges("analyst", route_after_analysis, {
        "writer": "writer",
        "done": END,
    })

    # writer → END
    workflow.add_edge("writer", END)

    # 编译（先用 MemorySaver，生产环境换 SqliteSaver）
    try:
        from app.core.checkpoint import checkpointer
        return workflow.compile(checkpointer=checkpointer)
    except Exception:
        return workflow.compile(checkpointer=MemorySaver())


def get_graph() -> StateGraph:
    """获取图实例（单例）"""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
