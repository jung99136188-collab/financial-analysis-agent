# 迭代日志

## v3.1 — 企业级降本增效 + 代码清理 (2026-08-09)

### 移除
- `app/agent/` — 旧 BaseAgent ReAct 循环 (已被 LangGraph 替代)
- `app/utils.py` — 旧 Pipeline 工具函数 (已被 tools/ 替代)
- `app/llm/` — 自建 LLM 适配器 (已被 ChatOpenAI 替代)
- `--pipeline` CLI 模式 (已移除，仅保留 LangGraph Agent CLI)

### 架构

### 新增
- **模型分层** (cheap/standard/premium): 搜索用便宜模型, 报告用旗舰 → 省 80% 推理成本
- **TTL 响应缓存**: 5 分钟同样问题 0 token (`app/core/cache.py`)
- **速率限制**: 滑动窗口 30次/分钟 (`app/core/rate_limiter.py`)
- **熔断器**: 连续 5 次失败自动暂停 (`app/core/rate_limiter.py`)
- **HTTP 连接池**: httpx 替代 requests, TCP 复用 (`app/core/http_client.py`)
- **成本追踪**: `/metrics` + Token 计量 + 美元估算 (`app/core/metrics.py`)
- **美股资金流**: `fetch_us_capital_flow` 工具
- 文档: `docs/production-optimization.md`

### 增强
- K线工具: 成交量分布 + 资金流方向 + 量价背离
- 美股工具: 机构持仓 + 卖空数据 + Top3 机构名单
- 工具精准分配: Researcher 5个 / Analyst 3个 / Writer 0个

---

## v3.0 — LangGraph + FastAPI 企业级升级 (2026-08-09)

### 新增
- **LangGraph StateGraph**: 替代自建 ReAct 循环 (`app/graph/`)
- **7 个 LangChain @tool**: ES搜索/K线/美股/资金流/股票识别/UZI/分析
- **FastAPI REST API**: `/chat` `/chat/stream` `/health` `/metrics` `/docs`
- **SSE 流式**: 实时 token 输出
- **SQLite Checkpointer**: LangGraph 状态持久化
- **pydantic-settings**: 配置管理 + `.env`
- **structlog**: 结构化日志
- **Docker**: 多阶段构建 + docker-compose
- **pytest**: 单元测试 (tools + graph)
- 文档: `docs/token-optimization.md`

---

## v2.5 — Token 优化 + Bug 修复 (2026-08-09)

### 优化
- **智能路由**：关键词分类器 `classify_query()`，简单问题 0 token，搜索类跳过 Analyst/Writer
- **Prompt 分层**：Analyst System Prompt 拆为 CORE(900字必发) + EXTENDED(550字按需)，节省 ~1500 tokens
- **动态截断**：工具结果从统一 8000 字 → 按类型 800~4000 字 (`TOOL_RESULT_LIMITS`)
- **Prompt Caching**：System Prompt 固定排第一，享受 DeepSeek 自动缓存
- **历史压缩**：3 轮对话从 6 条消息压缩为 1 条摘要
- **减少轮次**：MAX_ITERATIONS 从统一 8 → Coordinator:5, Researcher:4, Analyst:5, Writer:3

### 修复
- [P0] Gemini 适配器 tool result 缺 `name` 字段 (`base.py:80`)
- [P1] `_call_llm` 错误检测改用精确前缀匹配，避免误判
- [P2] 清理 `writer.py`/`analyst.py` 未使用的 import
- [P3] `classify_query` 去重 `"k线"` 关键词

---

## v2.4 — 美股数据 + 盘面分析 (2026-08-09)

### 新增
- **Researcher**: `fetch_kline_data` 工具 — yfinance 拉取 OHLCV + MA5/20/60 + 均线排列 + 量比
- **Analyst**: `analyze_technical_chart` 工具 — LLM 驱动的形态识别/趋势判断/支撑阻力
- **Researcher**: `fetch_us_stock_info` 工具 — Yahoo Finance + SEC EDGAR 美股数据
- **es_config**: 美股索引配置模板（可选启用）

---

## v2.3 — UZI-Skill 集成 (2026-08-09)

### 新增
- **Analyst System Prompt 蒸馏**：内置 UZI-Skill 的十维分析框架 + 9 组投资大佬视角 + 评分判定 + 叙事铁律
- **Analyst**: `run_uzi_analysis` 工具 — 可选调用 UZI CLI 获取完整量化报告

---

## v2.2 — 多模型适配器 (2026-08-09)

### 新增
- **`app/llm/` 适配层**：`LLMClient` 统一接口 + `create_llm_client()` 工厂
- **OpenAICompatibleClient**：DeepSeek V3/V4/GPT/任何兼容 `/v1/chat/completions` 的服务
- **GeminiClient**：Google Gemini API，内部做 OpenAI↔Gemini 格式双向转换
- **config 改造**：`LLM_PROVIDERS` 注册表 + `AGENT_MODEL_MAP` 绑定，每个 Agent 独立选模型

---

## v2.1 — 多 Agent 架构 (2026-04-27)

### 新增
- **`app/agent/` 包**：Coordinator + Researcher + Analyst + Writer 四 Agent 协作
- **`base.py`**：ReAct 循环引擎（Think → Act → Observe → Think）
- **Coordinator**：5 个委派工具（delegate × 3 + ask + deliver）
- **Researcher**：ES 四路并发搜索 + 股票识别
- **Analyst**：summarize / compare / extract 分析工具
- **Writer**：generate_report / format_table 报告工具
- **双模式**：多 Agent + Pipeline，运行中可 `切换`

---

## v1.0 — 初始 Pipeline (2025-04)

### 功能
- `process_question()`：LLM 提取关键词 → ES 四路查询 → 股票识别 → 去重排序 → R1 生成报告
- 数据源：纪要 / 研报 / 公告 / 点评
- 输出：文本报告 + Excel 汇总
