"""重复查询缓存 — TTL 过期 + LRU 淘汰"""

import hashlib
import time
import threading
from functools import lru_cache


class TTLCache:
    """简单 TTL 缓存，线程安全"""

    def __init__(self, ttl_seconds: int = 300, max_size: int = 100):
        self._ttl = ttl_seconds
        self._max = max_size
        self._store: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    def _key(self, message: str) -> str:
        return hashlib.md5(message.strip().lower().encode()).hexdigest()

    def get(self, message: str) -> str | None:
        key = self._key(message)
        with self._lock:
            if key in self._store:
                ts, value = self._store[key]
                if time.time() - ts < self._ttl:
                    return value
                del self._store[key]
        return None

    def set(self, message: str, value: str):
        key = self._key(message)
        with self._lock:
            if len(self._store) >= self._max:
                # 淘汰最老的 10%
                sorted_items = sorted(self._store.items(), key=lambda x: x[1][0])
                for old_key, _ in sorted_items[:max(1, self._max // 10)]:
                    del self._store[old_key]
            self._store[key] = (time.time(), value)

    def stats(self) -> dict:
        with self._lock:
            total = len(self._store)
            active = sum(1 for _, (ts, _) in self._store.items() if time.time() - ts < self._ttl)
            return {"cached": total, "active": active, "ttl_sec": self._ttl}


response_cache = TTLCache(ttl_seconds=300)  # 5分钟缓存
