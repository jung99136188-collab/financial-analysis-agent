"""FastAPI 路由 — REST + SSE 流式 + 限流/缓存/指标"""

import uuid
import time
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage

from app.api.schemas import ChatRequest, ChatResponse, ApproveRequest, HealthResponse
from app.api.dependencies import get_agent_graph
from app.core.config import settings
from app.core.metrics import collector, RequestMetrics, estimate_cost
from app.core.cache import response_cache
from app.core.rate_limiter import limiter, llm_breaker

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    try:
        graph = get_agent_graph()
        loaded = graph is not None
    except Exception:
        loaded = False
    return HealthResponse(version=settings.app_version, graph_loaded=loaded)


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """对话 — 含限流/缓存/成本追踪"""
    # 限流
    client_ip = "default"
    if not limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail=f"请求太频繁，剩余:{limiter.remaining(client_ip)}次/分钟")

    # 命中缓存直接返回
    cached = response_cache.get(req.message)
    if cached and not req.deep_mode:
        return ChatResponse(
            thread_id="cached", intent="cached", response=cached,
            timestamp=None  # type: ignore
        )

    graph = get_agent_graph()
    thread_id = req.thread_id or str(uuid.uuid4())[:8]
    config = {"configurable": {"thread_id": thread_id}}
    t_start = time.perf_counter()

    try:
        result = llm_breaker.call(
            lambda: graph.invoke(
                {"messages": [HumanMessage(content=req.message)],
                 "deep_mode": req.deep_mode, "error_count": 0}, config
            )
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph error: {str(e)}")

    latency = round((time.perf_counter() - t_start) * 1000)

    # 提取响应
    messages = result.get("messages", [])
    response_text = result.get("final_report") or result.get("analysis_result") or ""
    if not response_text:
        for m in reversed(messages):
            if isinstance(m, AIMessage) and m.content:
                response_text = m.content
                break

    # Token 估算 (LangGraph 不直接返回 usage，按字符估算)
    input_chars = len(req.message) + len(result.get("research_data", "") or "")
    output_chars = len(response_text or "")
    input_tokens = input_chars // 3
    output_tokens = output_chars // 3
    total_tokens = input_tokens + output_tokens
    cost = estimate_cost(settings.llm_model, input_tokens, output_tokens)

    # 记录指标
    collector.record(RequestMetrics(
        thread_id=thread_id, intent=result.get("intent", "unknown"),
        total_tokens=total_tokens, input_tokens=input_tokens,
        output_tokens=output_tokens, llm_calls=1, tool_calls=0,
        latency_ms=latency, estimated_cost_usd=cost, model=settings.llm_model,
    ))

    # 写入缓存
    if len(response_text or "") > 50:
        response_cache.set(req.message, response_text)

    return ChatResponse(
        thread_id=thread_id, intent=result.get("intent", "unknown"),
        response=response_text or "分析完成",
        research_data=result.get("research_data"),
        analysis_result=result.get("analysis_result"),
        final_report=result.get("final_report"),
    )


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE 流式对话"""
    if not limiter.allow("stream"):
        raise HTTPException(status_code=429, detail="请求太频繁")

    graph = get_agent_graph()
    thread_id = req.thread_id or str(uuid.uuid4())[:8]
    config = {"configurable": {"thread_id": thread_id}}

    async def event_generator():
        yield f"data: {json.dumps({'type': 'start', 'thread_id': thread_id})}\n\n"
        try:
            async for event in graph.astream_events(
                {"messages": [HumanMessage(content=req.message)],
                 "deep_mode": req.deep_mode, "error_count": 0}, config, version="v2",
            ):
                kind = event.get("event", "")
                name = event.get("name", "")
                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"
                elif kind == "on_tool_start":
                    yield f"data: {json.dumps({'type': 'tool_start', 'tool': name})}\n\n"
                elif kind == "on_tool_end":
                    yield f"data: {json.dumps({'type': 'tool_end', 'tool': name})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/chat/{thread_id}")
async def get_history(thread_id: str):
    graph = get_agent_graph()
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = graph.get_state(config)
        if state.values:
            msgs = state.values.get("messages", [])
            return {
                "thread_id": thread_id,
                "message_count": len(msgs),
                "intent": state.values.get("intent", ""),
                "messages": [{"role": m.type, "content": m.content[:500]} for m in msgs[-10:]],
            }
        return {"thread_id": thread_id, "message_count": 0, "messages": []}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/approve/{thread_id}")
async def approve(thread_id: str, req: ApproveRequest):
    graph = get_agent_graph()
    config = {"configurable": {"thread_id": thread_id}}
    try:
        graph.update_state(config, {"approved": req.approved})
        return {"thread_id": thread_id, "approved": req.approved}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def metrics():
    """成本/性能指标 + 缓存命中率"""
    return {
        **collector.stats(),
        "cache": response_cache.stats(),
        "rate_limiter": {"remaining": limiter.remaining()},
    }
