"""速率限制 + 熔断器"""

import time
import threading
from collections import defaultdict


class RateLimiter:
    """滑动窗口限流"""

    def __init__(self, max_requests: int = 30, window_sec: int = 60):
        self._max = max_requests
        self._window = window_sec
        self._clients: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def allow(self, client_id: str = "default") -> bool:
        now = time.time()
        with self._lock:
            # 清理过期记录
            window = [t for t in self._clients[client_id] if now - t < self._window]
            if len(window) >= self._max:
                return False
            window.append(now)
            self._clients[client_id] = window
            return True

    def remaining(self, client_id: str = "default") -> int:
        now = time.time()
        with self._lock:
            window = [t for t in self._clients[client_id] if now - t < self._window]
            return max(0, self._max - len(window))


class CircuitBreaker:
    """熔断器 — 连续失败N次后暂时拒绝请求"""

    def __init__(self, failure_threshold: int = 5, recovery_sec: float = 30.0):
        self._threshold = failure_threshold
        self._recovery = recovery_sec
        self._failures = 0
        self._last_failure = 0.0
        self._open = False
        self._lock = threading.Lock()

    def call(self, fn, *args, **kwargs):
        with self._lock:
            if self._open:
                if time.time() - self._last_failure > self._recovery:
                    self._open = False  # 半开
                    self._failures = 0
                else:
                    raise RuntimeError("服务熔断中，请稍后重试")

        try:
            result = fn(*args, **kwargs)
            with self._lock:
                self._failures = 0
            return result
        except Exception:
            with self._lock:
                self._failures += 1
                self._last_failure = time.time()
                if self._failures >= self._threshold:
                    self._open = True
            raise


limiter = RateLimiter(max_requests=30, window_sec=60)
llm_breaker = CircuitBreaker(failure_threshold=5, recovery_sec=30.0)
