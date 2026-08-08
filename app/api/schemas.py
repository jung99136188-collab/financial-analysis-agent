"""Pydantic 请求/响应模型"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户问题", min_length=1)
    thread_id: Optional[str] = Field(default=None, description="会话ID(用于多轮对话)")
    deep_mode: bool = Field(default=False, description="是否启用深度分析模式")


class ChatResponse(BaseModel):
    thread_id: str
    intent: str
    response: str
    research_data: Optional[str] = None
    analysis_result: Optional[str] = None
    final_report: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class ApproveRequest(BaseModel):
    thread_id: str = Field(..., description="会话ID")
    approved: bool = Field(default=True)


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    graph_loaded: bool


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
