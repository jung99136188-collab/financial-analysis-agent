"""Token 计量 + 成本估算 + 请求监控"""

import time
import threading
from dataclasses import dataclass, field
from collections import defaultdict


# 模型定价 (USD/1M tokens) — 近似值
MODEL_PRICES = {
    "deepseek-chat":      {"input": 0.14, "output": 0.28},
    "deepseek-reasoner":  {"input": 0.55, "output": 2.19},
    "gemini-2.5-flash":   {"input": 0.15, "output": 0.60},
    "gpt-4o":             {"input": 2.50, "output": 10.00},
    "default":            {"input": 0.50, "output": 1.50},
}


@dataclass
class RequestMetrics:
    thread_id: str = ""
    intent: str = ""
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    latency_ms: float = 0
    estimated_cost_usd: float = 0.0
    model: str = ""


class MetricsCollector:
    """线程安全的指标收集器"""

    def __init__(self):
        self._lock = threading.Lock()
        self._requests: list[RequestMetrics] = []
        self._totals = defaultdict(int)

    def record(self, metrics: RequestMetrics):
        with self._lock:
            self._requests.append(metrics)
            self._totals["requests"] += 1
            self._totals["total_tokens"] += metrics.total_tokens
            self._totals["total_cost"] += metrics.estimated_cost_usd
            self._totals["total_latency_ms"] += metrics.latency_ms
            # 只保留最近 1000 条
            if len(self._requests) > 1000:
                self._requests = self._requests[-500:]

    def stats(self) -> dict:
        with self._lock:
            avg_latency = (self._totals["total_latency_ms"] / self._totals["requests"]
                           if self._totals["requests"] > 0 else 0)
            return {
                "total_requests": self._totals["requests"],
                "total_tokens": self._totals["total_tokens"],
                "total_cost_usd": round(self._totals["total_cost"], 4),
                "avg_latency_ms": round(avg_latency, 0),
                "recent_requests": [
                    {"thread": r.thread_id, "intent": r.intent,
                     "tokens": r.total_tokens, "cost": f"${r.estimated_cost_usd:.6f}",
                     "latency_ms": r.latency_ms, "model": r.model}
                    for r in self._requests[-10:]
                ],
            }


collector = MetricsCollector()


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """估算单次调用成本"""
    prices = MODEL_PRICES.get(model, MODEL_PRICES["default"])
    return (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000
