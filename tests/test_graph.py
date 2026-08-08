"""LangGraph 图测试"""

import pytest


def test_state_definition():
    """验证 AgentState 可用"""
    from app.graph.state import AgentState
    from langchain_core.messages import HumanMessage
    state = AgentState(
        messages=[HumanMessage(content="test")],
        intent="analyze",
        research_data="",
        analysis_result="",
        final_report="",
        deep_mode=False,
        error_count=0,
    )
    assert state["intent"] == "analyze"
    assert state["messages"][0].content == "test"


def test_routing_logic():
    """验证路由逻辑"""
    from app.graph.routing import route_by_intent
    from app.graph.state import AgentState
    from langchain_core.messages import HumanMessage

    # greeting
    state = AgentState(
        messages=[HumanMessage(content="test")],
        intent="greeting",
        research_data="", analysis_result="", final_report="",
        deep_mode=False, error_count=0,
    )
    assert route_by_intent(state) == "greeting"

    # analyze → researcher
    state["intent"] = "analyze"
    assert route_by_intent(state) == "researcher"


def test_graph_builds():
    """验证图可以构建"""
    from app.graph import build_graph
    graph = build_graph()
    assert graph is not None
    # 应该有节点
    nodes = graph.get_graph().nodes if hasattr(graph, "get_graph") else {}
    assert len(graph.nodes) > 0 if hasattr(graph, "nodes") else True
