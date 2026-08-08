# 企业级降本增效方案

## 已实施的优化 (6 项)

### 1. 模型分层 (Tiered Models) — 降本核心

| 层 | 场景 | 模型 | 成本 |
|----|------|------|------|
| **Cheap** | 分类 / 搜索 / K线 | deepseek-chat | $0.14/M input |
| **Standard** | 分析 / 对比 / 指标提取 | deepseek-chat (或 gemini-flash) | $0.14~0.15/M |
| **Premium** | 报告生成 / 深度研究 | deepseek-reasoner (或 gemini-pro) | $0.55/M |

配置方式 (`.env`):

```bash
LLM_MODEL=deepseek-chat              # Cheap: 所有默认
ANALYST_MODEL=gemini-2.5-flash       # Standard: 分析师专用(可选)
WRITER_MODEL=deepseek-reasoner       # Premium: 报告专用(可选)
```

**效果**: 搜索/查询用便宜模型, 报告才用贵模型, 节省 60%+ 推理成本。

### 2. 响应缓存 (TTL Cache)

5 分钟内相同问题直接返回缓存结果, 0 token 消耗。

```python
# app/core/cache.py
response_cache = TTLCache(ttl_seconds=300, max_size=100)
```

**效果**: 重复查询 0 token, 命中率越高越省。

### 3. 速率限制 + 熔断器

```python
# app/core/rate_limiter.py
limiter = RateLimiter(max_requests=30, window_sec=60)   # 30次/分钟
llm_breaker = CircuitBreaker(failure_threshold=5)        # 5次失败熔断
```

**效果**: 防止恶意调用烧钱 + 连续失败自动暂停避免浪费。

### 4. HTTP 连接池

全局 `httpx.Client` 替代 `requests`, TCP 连接复用。

```python
# app/core/http_client.py
client = httpx.Client(http2=True, limits=Limits(max_connections=50))
```

**效果**: 减少 TCP 握手, 降低延迟 20-40ms/请求。

### 5. 工具精准分配

每个 Node 只发送它需要的工具定义, 而非全部 8 个:

| Node | 工具数 | 工具 |
|------|--------|------|
| Researcher | 5 | search_financial_docs, fetch_kline_data, fetch_us_stock_info, fetch_us_capital_flow, identify_stocks |
| Analyst | 3 | summarize_findings, compare_stocks, run_uzi_analysis |
| Writer | 0 | (纯 LLM 生成) |

**效果**: 每轮推理省 200-500 input tokens (工具定义开销)。

### 6. 成本追踪 + 指标面板

```
GET /metrics →
{
  "total_requests": 128,
  "total_tokens": 450000,
  "total_cost_usd": 0.0234,
  "avg_latency_ms": 850,
  "cache": {"cached": 45, "active": 38, "ttl_sec": 300},
  "rate_limiter": {"remaining": 22}
}
```

**效果**: 成本可见, 异常可追溯。

---

## 进一步优化 (可选)

| 优化 | 预期效果 | 复杂度 |
|------|---------|--------|
| Redis 替代内存缓存 | 跨进程共享, 重启不丢失 | 中 |
| tiktoken 精确计费 | 替代字符估算, 精准到 token | 低 |
| 异步 ES 查询 (elasticsearch-async) | 减少 I/O 等待 | 中 |
| LangSmith/LangFuse 可观测性 | 完整的 Graph 执行链路追踪 | 中 |
| PostgreSQL 替代 SQLite Checkpointer | 生产级持久化, 多副本 | 高 |
| Kubernetes HPA 自动扩缩 | 按流量自动增减实例 | 高 |
| LLM 请求 batching | 合并多个请求减少 API 调用次数 | 高 |

---

## 成本估算示例

一次完整的"搜索→分析→报告"链路:

```
Researcher (cheap):   input 2000 + output 500  = 2500 tokens × $0.14/M = $0.00035
Analyst (standard):   input 3000 + output 800  = 3800 tokens × $0.15/M = $0.00057
Writer (premium):     input 2500 + output 1500 = 4000 tokens × $0.55/M = $0.00220
                                                                        ---------
单次完整报告总成本:                                                      ~$0.003

以每天 100 次计: ~$0.30/天 ≈ $9/月
```

对比全部用 premium 模型: $0.015/次 ≈ $45/月 — **模型分层省了 80%。**
