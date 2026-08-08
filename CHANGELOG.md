# 迭代日志

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
