# 金融分析多 Agent 协作系统
> Multi-Agent Financial Analysis System — LangGraph + FastAPI Enterprise Edition

基于 **LangGraph StateGraph** 编排的多智能体金融分析系统。覆盖 A 股 + 美股，8 个专业工具，REST API + SSE 流式双接口，Docker 一键部署。

*LangGraph-powered multi-agent financial analysis. Covers A-shares + US stocks, 8 tools, REST + SSE streaming, Docker-ready.*

---

## 架构 / Architecture

```
                         User Input (REST / CLI / SSE)
                            │
                            ▼
                  ┌─────────────────┐
                  │    Router       │  classify_intent (0 token)
                  │  意图分类/路由    │
                  └───────┬─────────┘
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
      [greeting]   [researcher]    [analyst]    [writer]
        END         cheap模型       standard     premium
                   5 tools         3 tools     纯LLM生成
```

### 技术栈 / Tech Stack

| 层 | 技术 |
|----|------|
| Agent 编排 | **LangGraph** StateGraph + 条件路由 + SQLite Checkpointer |
| 工具封装 | **LangChain** @tool 装饰器 |
| API 服务 | **FastAPI** + SSE 流式 + Swagger |
| 模型接入 | **ChatOpenAI** (兼容 DeepSeek/GPT/任何 OpenAI API) |
| 配置 | **pydantic-settings** + `.env` |
| 日志 | **structlog** (JSON 结构化) |
| 部署 | **Docker** 多阶段构建 + docker-compose |
| 测试 | **pytest** |

---

## 项目结构 / Project Structure

```
.
├── app/
│   ├── api/                    # FastAPI 层
│   │   ├── routes.py           # /chat /chat/stream /health /metrics
│   │   ├── schemas.py          # Pydantic 请求/响应
│   │   └── dependencies.py     # Graph 实例注入
│   ├── graph/                  # LangGraph 层
│   │   ├── state.py            # AgentState TypedDict
│   │   ├── nodes.py            # 4 个 Agent Node (含模型分层)
│   │   ├── routing.py          # 条件路由 + 意图分类
│   │   └── graph.py            # StateGraph 构建 + 编译
│   ├── tools/                  # LangChain Tool 封装
│   │   ├── es_search.py        # A股 ES 四路搜索
│   │   ├── kline.py            # K线 + 成交量分布 + 资金流方向
│   │   ├── us_stocks.py        # 美股行情 + 机构持仓 + 卖空
│   │   ├── capital_flow.py     # 美股资金流向
│   │   ├── stock_id.py         # 股票代码识别
│   │   ├── uzi.py              # UZI-Skill 量化报告
│   │   └── analyze.py          # 汇总 + 对比
│   ├── core/                   # 基础设施
│   │   ├── config.py           # pydantic-settings
│   │   ├── logging.py          # structlog
│   │   ├── checkpoint.py       # SQLite Checkpointer
│   │   ├── metrics.py          # Token 计量 + 成本估算
│   │   ├── cache.py            # TTL 响应缓存
│   │   ├── http_client.py      # httpx 连接池
│   │   └── rate_limiter.py     # 限流 + 熔断
│   └── main.py                 # 入口 (API 默认 / CLI --cli)
├── config/
│   ├── agent_config.py         # System Prompts + UZI 框架
│   ├── es_config.py            # Elasticsearch (脱敏)
│   └── api_config.example.py   # API 配置模板
├── docker/                     # Dockerfile + docker-compose
├── tests/                      # pytest
├── docs/                       # 优化文档
├── pyproject.toml              # 依赖管理
└── .env.example                # 环境变量模板
```

---

## 快速开始 / Quick Start

### 1. 安装

```bash
pip install -e ".[kline]"
```

或手动：

```bash
pip install langgraph langchain-core langchain-openai fastapi uvicorn httpx structlog pydantic-settings elasticsearch pandas openpyxl
pip install yfinance  # K线可选
```

### 2. 配置

```bash
cp config/api_config.example.py config/api_config.py
cp .env.example .env
```

编辑 `.env`:
```bash
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-your-key
LLM_MODEL=deepseek-chat
```

### 3. 启动

```bash
# API 服务 (默认)
python app/main.py
# → http://localhost:8000/docs

# CLI 交互
python app/main.py --cli
```

---

## API 接口 / Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat` | 对话 |
| `POST` | `/chat/stream` | SSE 流式对话 |
| `GET` | `/chat/{thread_id}` | 查询历史 |
| `GET` | `/metrics` | 成本/性能指标 |
| `GET` | `/health` | 健康检查 |
| `GET` | `/docs` | Swagger 文档 |

---

## 8 个专业工具 / Tools

| Tool | Market | Output |
|------|--------|--------|
| `search_financial_docs` | A股 | 纪要/研报/公告/点评 |
| `fetch_kline_data` | A股/美股/港股 | OHLCV + MA + 成交量分布 + 资金流方向 + 背离检测 |
| `fetch_us_stock_info` | 美股 | 行情 + 机构持仓% + 卖空数据 + Top3 机构 |
| `fetch_us_capital_flow` | 美股 | 净流比 + 量能趋势 + 机构/散户结构 |
| `identify_stocks` | 通用 | A股/港股/美股代码识别 |
| `summarize_findings` | 通用 | LLM 汇总提炼 |
| `compare_stocks` | 通用 | LLM 横向对比 |
| `run_uzi_analysis` | 通用 | UZI-Skill 22维量化报告 |

---

## 企业级特性 / Enterprise Features

| 特性 | 实现 |
|------|------|
| **模型分层** | Cheap(搜索) / Standard(分析) / Premium(报告) → 省 80% 成本 |
| **TTL 缓存** | 5 分钟同问题 0 token |
| **速率限制** | 30 次/分钟滑动窗口 |
| **熔断器** | 连续 5 次失败自动暂停 |
| **连接池** | httpx HTTP/2 复用 |
| **成本追踪** | `/metrics` — 实时 token 用量 + USD 成本 |
| **流式输出** | SSE — 逐 token 推送 |

详见 [docs/production-optimization.md](docs/production-optimization.md)

---

## 文档 / Docs

| Document | Content |
|----------|---------|
| [CHANGELOG.md](CHANGELOG.md) | 迭代日志 v1.0 → v3.1 |
| [docs/token-optimization.md](docs/token-optimization.md) | Token 优化: 路由/分层/截断/缓存/压缩 |
| [docs/production-optimization.md](docs/production-optimization.md) | 降本增效: 模型分层/缓存/限流/熔断/连接池 |

---

## 注意事项 / Notes

- `config/api_config.py` 和 `.env` 已被 gitignore，不会上传
- ES 和股票识别服务需自行部署
- Python ≥ 3.10
