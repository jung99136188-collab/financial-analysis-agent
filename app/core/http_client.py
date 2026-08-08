"""全局 HTTP 客户端 — 连接池复用

替代 requests 的每次新建连接，减少 TCP 握手开销。
"""

import httpx

# 连接池配置
_http_client: httpx.Client | None = None


def get_http_client() -> httpx.Client:
    """获取全局 HTTP 客户端（连接池复用）"""
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(
            timeout=httpx.Timeout(30.0, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
            http2=True,
        )
    return _http_client
