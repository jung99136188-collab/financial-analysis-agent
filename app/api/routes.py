"""FastAPI 路由 — REST + SSE 流式"""

import uuid
import asyncio
import json
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage
from sse_starlette.sse import EventSourceResponse

from app.api.schemas import ChatRequest, ChatResponse, ApproveRequest, HealthResponse, ErrorResponse
from app.api.dependencies import get_agent_graph
from app.core.config import settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    """健康检查"""
    try:
        graph = get_agent_graph()
        loaded = graph is not None
    except Exception:
        loaded = False
    return HealthResponse(version=settings.app_version, graph_loaded=loaded)


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """非流式对话"""
    graph = get_agent_graph()
    thread_id = req.thread_id or str(uuid.uuid4())[:8]
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = graph.invoke(
            {"messages": [HumanMessage(content=req.message)],
             "deep_mode": req.deep_mode,
             "error_count": 0},
            config,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph execution failed: {str(e)}")

    # 提取最终响应
    messages = result.get("messages", [])
    response_text = ""
    for m in reversed(messages):
        if isinstance(m, AIMessage) and m.content:
            response_text = m.content
            break

    if result.get("final_report"):
        response_text = result["final_report"]
    elif result.get("analysis_result"):
        response_text = result["analysis_result"]

    return ChatResponse(
        thread_id=thread_id,
        intent=result.get("intent", "unknown"),
        response=response_text or "分析完成，但未生成文本输出",
        research_data=result.get("research_data"),
        analysis_result=result.get("analysis_result"),
        final_report=result.get("final_report"),
    )


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE 流式对话"""
    graph = get_agent_graph()
    thread_id = req.thread_id or str(uuid.uuid4())[:8]
    config = {"configurable": {"thread_id": thread_id}}

    async def event_generator() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'type': 'start', 'thread_id': thread_id})}\n\n"

        try:
            # 使用 astream_events 实现流式
            async for event in graph.astream_events(
                {"messages": [HumanMessage(content=req.message)],
                 "deep_mode": req.deep_mode,
                 "error_count": 0},
                config,
                version="v2",
            ):
                kind = event.get("event", "")
                name = event.get("name", "")

                if kind == "on_chat_model_stream" and event.get("data", {}).get("chunk"):
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, "content") and chunk.content:
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"

                elif kind == "on_tool_start":
                    yield f"data: {json.dumps({'type': 'tool_start', 'tool': name})}\n\n"

                elif kind == "on_tool_end":
                    yield f"data: {json.dumps({'type': 'tool_end', 'tool': name})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chat/{thread_id}")
async def get_history(thread_id: str):
    """查询历史对话"""
    graph = get_agent_graph()
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = graph.get_state(config)
        if state.values:
            messages = state.values.get("messages", [])
            return {
                "thread_id": thread_id,
                "message_count": len(messages),
                "intent": state.values.get("intent", ""),
                "messages": [
                    {"role": m.type, "content": m.content[:500]}
                    for m in messages[-10:]
                ],
            }
        return {"thread_id": thread_id, "message_count": 0, "messages": []}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Thread not found: {str(e)}")


@router.post("/approve/{thread_id}")
async def approve(thread_id: str, req: ApproveRequest):
    """人工审批（预留 Human-in-the-loop）"""
    graph = get_agent_graph()
    config = {"configurable": {"thread_id": thread_id}}
    try:
        graph.update_state(config, {"approved": req.approved})
        return {"thread_id": thread_id, "approved": req.approved}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
