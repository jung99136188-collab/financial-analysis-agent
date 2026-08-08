# 金融分析多 Agent 协作系统
> Multi-Agent Financial Analysis System

基于 ReAct 模式的多智能体金融分析系统。Coordinator 调度 Researcher、Analyst、Writer 三个专业 Agent 协作，自动完成从信息搜集到报告生成的全流程。覆盖 A 股 + 美股，内置 UZI-Skill 十维分析框架，支持 DeepSeek / Gemini 多模型切换。

*A ReAct-based multi-agent system for financial analysis. Coordinator orchestrates Researcher, Analyst, and Writer agents to automate the full pipeline from data collection to report generation. Covers A-shares + US stocks, with built-in UZI-Skill methodology and multi-model support (DeepSeek / Gemini).*

---

## 架构 / Architecture

```
                         User Input
                            │
                            ▼
                  ┌─────────────────┐
                  │  Coordinator    │  Scheduler / 总调度
                  │  Intent → Plan  │
                  └───────┬─────────┘
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
   ┌────────────┐ ┌────────────┐ ┌────────────┐
   │ Researcher │ │  Analyst   │ │   Writer   │
   │  Data Fetch │ │  Deep Dive │ │  Report    │
   └──────┬─────┘ └──────┬─────┘ └──────┬─────┘
          │              │              │
     ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
     │ ES Search│   │ Scoring │    │ Markdown  │
     │ K-line   │   │ Compare │    │ Tables    │
     │ US Stocks│   │ Charts  │    │ Citations │
     └─────────┘    └─────────┘    └─────────┘
```

### Agent 角色 / Roles

| Agent | Role | Tools |
|-------|------|-------|
| **Coordinator** | Understands intent, plans workflow, delegates tasks | delegate ×3, ask, deliver |
| **Researcher** | Searches financial docs, fetches K-line, US stock data | ES search, yfinance, SEC EDGAR |
| **Analyst** | 10-dim scoring, 9-group investor role-play, chart analysis | summarize, compare, technical chart |
| **Writer** | Generates professional markdown reports with citations | report generation, table formatting |

### ReAct 循环 / ReAct Loop

Each agent runs a **ReAct (Reasoning + Acting)** loop internally:

```
Think → Choose Tool → Execute → Observe → Think → ... → Output
```

The LLM decides when to call tools and when to stop — not hardcoded steps.

---

## 项目结构 / Project Structure

```
.
├── app/
│   ├── agent/                 # Multi-Agent System
│   │   ├── __init__.py
│   │   ├── base.py            # BaseAgent — ReAct loop engine
│   │   ├── coordinator.py     # Scheduler + delegation tools
│   │   ├── researcher.py      # Data fetching (ES/K-line/US)
│   │   ├── analyst.py         # Deep analysis (UZI methodology)
│   │   └── writer.py          # Report generation
│   ├── llm/                   # LLM Adapter Layer
│   │   ├── __init__.py        # LLMClient interface + factory
│   │   ├── openai_compatible.py  # DeepSeek / GPT / any /v1/chat
│   │   └── gemini.py          # Gemini adapter (format conversion)
│   ├── main.py                # Entry point (Agent + Pipeline dual mode)
│   └── utils.py               # Pipeline utilities (legacy)
├── config/
│   ├── agent_config.py        # Agent config + System Prompts
│   ├── api_config.py          # API keys (gitignored, create from example)
│   ├── api_config.example.py  # API config template
│   └── es_config.py           # Elasticsearch config
├── docs/
│   └── token-optimization.md  # Token optimization guide (Chinese)
├── CHANGELOG.md               # Iteration log (Chinese)
├── requirements.txt
├── .gitignore
└── LICENSE
```

---

## 快速开始 / Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
# Optional: K-line data support
pip install yfinance
```

### 2. Configure API Keys

```bash
cp config/api_config.example.py config/api_config.py
```

Edit `config/api_config.py` and fill in:
- `API_KEY_VOLCENGINE` — Volcengine API key (for DeepSeek)
- `DEEPSEEK_V3_ENDPOINT` / `DEEPSEEK_R1_ENDPOINT` — endpoint IDs
- `STOCK_MATCHER_URL` — stock identification service
- Optionally add your own DeepSeek / Gemini keys

### 3. Ensure Backend Services Are Available

- **Elasticsearch** — stores financial documents. Configure in `config/es_config.py`
- **Stock Matcher API** — REST endpoint for ticker identification

### 4. Run

```bash
python app/main.py
```

```
============================================================
  Financial Analysis Assistant / 金融分析助手
============================================================
  1. Multi-Agent Mode (recommended) — AI agents collaborate
  2. Pipeline Mode — legacy fixed workflow
============================================================

Select mode (1/2):
```

---

## 使用示例 / Usage Example

### Multi-Agent Mode

```
🧠 > What are the notable stocks in AIGC recently?

[Coordinator] → Delegate Researcher: search AIGC concept...
[Researcher] → search_financial_docs(keyword="AIGC") → 23 results

[Coordinator] → Delegate Analyst: analyze institutional views
[Analyst] → summarize_findings(data=..., focus="institutional attention")

[Coordinator] → Delegate Writer: generate report
[Writer] → generate_report(topic="AIGC Sector")

============================================================
# AIGC Sector Investment Analysis Report
## Key Findings
1. **AI application accelerating**: AIGC mentions in roadshow notes up 45% QoQ...
   [Source: RRP00000000058924250]
...
```

Type `切换` or `switch` to toggle between Agent and Pipeline modes mid-session.

---

## 技术栈 / Tech Stack

### No Framework — Pure ReAct + Function Calling

```python
# app/agent/base.py — core loop (~80 lines)
class BaseAgent:
    def run(self, task, deep_mode=False):
        messages = [system_prompt, user_task]
        for _ in range(max_iterations):
            response = llm.chat(messages, tools=self.tools)
            if response.tool_calls:
                for tc in response.tool_calls:
                    result = execute_tool(tc.name, tc.args)
                    messages.append(tool_result(result))
            else:
                return response.content
```

### Multi-Model Support

Switch models via `config/agent_config.py` — each agent can use a different provider:

```python
LLM_PROVIDERS = {
    "ds_v4": {"provider": "openai_compatible", ...},
    "gemini": {"provider": "gemini", ...},
}

AGENT_MODEL_MAP = {
    "coordinator": "ds_v4",    # DeepSeek V4 Flash — fast decisions
    "researcher": "ds_v4",     # DeepSeek V4 Flash — cheap queries
    "analyst": "gemini",       # Gemini 2.5 Flash — strong reasoning
    "writer": "gemini",        # Gemini — quality generation
}
```

Supported: **OpenAI-compatible** (DeepSeek, GPT-4o, any `/v1/chat/completions`) + **Gemini** (native Google API with format conversion).

### UZI-Skill Integration (Optional)

The Analyst agent has [UZI-Skill](https://github.com/wbh604/UZI-Skill) (5.6k stars) methodology distilled into its system prompt:

- **10-dimension framework**: fundamentals, valuation, technicals, industry position, capital flows, policy, moat, catalysts, sentiment, risk detection
- **9 investor groups**: Value (Buffett/Munger), Growth (Lynch/Wood), Macro (Soros/Dalio), Technical (Livermore), China Value (Duan Yongping/Zhang Kun), Hot Money (A-share only), Quant (Simons), Tech (Andreessen), Position Hunter (Serenity)
- **Scoring**: 1-10 per dimension → weighted → composite → verdict (Buy / Hold / Watch / Caution / Avoid)
- **Narrative rules**: ban vague phrases, require specific numbers + sources, surface conflicts

Optional CLI integration:
```bash
git clone https://github.com/wbh604/UZI-Skill.git ../UZI-Skill
cd ../UZI-Skill && pip install -r requirements.txt
# Set UZI_ENABLED=True in config/agent_config.py
```

---

## 数据源 / Data Sources

### A-Shares (ES Indices)

| Source | Index | Period | Notes |
|--------|-------|--------|-------|
| Roadshow Notes / 路演纪要 | roadshow_summary | 3 months | MT recorded |
| Research Reports / 研报 | report | 3 months | Broker reports |
| Announcements / 公告 | stock_announcement | 6 months | Company filings |
| Analyst Comments / 点评 | comment | 2 months | TXT category |

### US Stocks (Multi-Channel)

| Channel | Coverage | Notes |
|---------|----------|-------|
| Yahoo Finance | Real-time quotes, company info | Free, no config |
| SEC EDGAR | 10-K / 10-Q / 8-K filings | Free, public |
| ES US Indices | Earnings calls, analyst ratings | Optional, configure in `es_config.py` |
| UZI-Skill | Full quantitative analysis | `run_uzi_analysis('AAPL')` |

### Technical Analysis / 盘面分析

| Tool | Output | Requires |
|------|--------|----------|
| `fetch_kline_data` | OHLCV + MA5/20/60 + alignment + volume ratio | `pip install yfinance` |
| `analyze_technical_chart` | Trend, patterns, support/resistance | LLM-driven |
| UZI-Skill | Full technical (MACD/RSI/Bollinger) | Optional install |

---

## 依赖 / Requirements

```
elasticsearch>=7.0.0,<8.0.0
requests>=2.25.0
pandas>=1.3.0
openpyxl>=3.0.0
python-dateutil>=2.8.2
```

Optional: `yfinance` (K-line data), `akshare` (A-share alternative)

---

## 注意事项 / Notes

- Requires accessible Elasticsearch and stock identification backend services.
- Multi-agent mode triggers multiple API calls per conversation — monitor usage if on limited plans.
- `config/api_config.py` is gitignored. Copy from `api_config.example.py` and fill in your keys.
- The system is optimized for Chinese financial content but supports US stocks via Yahoo Finance + SEC EDGAR.

## 文档 / Documentation

- [CHANGELOG.md](CHANGELOG.md) — 迭代日志 (Chinese)
- [docs/token-optimization.md](docs/token-optimization.md) — Token 优化方案 (Chinese)
