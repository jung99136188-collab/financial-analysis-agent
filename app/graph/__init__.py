"""LangGraph 编排层 — 延迟导入避免循环依赖"""

_build_graph = None
_get_graph = None


def build_graph():
    global _build_graph
    if _build_graph is None:
        from app.graph.graph import build_graph as _bg
        _build_graph = _bg
    return _build_graph()


def get_graph():
    global _get_graph
    if _get_graph is None:
        from app.graph.graph import get_graph as _gg
        _get_graph = _gg
    return _get_graph()


__all__ = ["build_graph", "get_graph"]
