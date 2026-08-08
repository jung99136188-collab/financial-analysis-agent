# Token 与响应时间优化方案

## 问题分析

每次对话的 token 消耗路径：

```
Coordinator调用 (System ~1500 tokens + tools ~800 tokens)
  → Researcher调用 (System ~1000 tokens + tools ~600 tokens)
    → Analyst调用 (System ~2500 tokens + tools ~1200 tokens)
      → Writer调用 (System ~800 tokens + tools ~600 tokens)
```

完整链路需 4 次 LLM 调用，每次重发 System Prompt + Tools 定义，固定开销 ~8000+ tokens。

---

## 优化 1: 智能路由 — 减少 Agent 跳数

**问题**：所有问题都走全链路。

**方案**：`app/main.py` 入口加关键词分类器，0 token 开销：

```python
def classify_query(question: str) -> str:
    if any(w in q for w in ["你好","帮助","怎么用"]):
        return "direct"           # 直接回答
    if any(w in q for w in ["搜索","查","找","有没有"]):
        return "research_only"    # 只调 Researcher
    if any(w in q for w in ["分析","对比","怎么看","盘面"]):
        return "research+analysis" # Researcher + Analyst
    return "full"                 # 完整链路
```

**效果**：
- "你好" → 0 token
- "搜索AIGC纪要" → 省 60%
- 仅明确要报告时走全链路

---

## 优化 2: System Prompt 分层

**问题**：Analyst 的 UZI 方法论 (~2500 tokens) 每次都全量发送。

**方案**：拆为 CORE(必发) + EXTENDED(按需)：

```python
# config/agent_config.py
ANALYST_SYSTEM_PROMPT_CORE = """你是金融数据分析专家。
## 十维分析框架
基本面|估值|技术面|...每个维度1-10分
## 评分判定
≥80值得重仓 | 65-79可以蹲 | ...
## 叙事铁律
禁用空话，每个结论附具体数字
"""

ANALYST_SYSTEM_PROMPT_EXTENDED = """
## 九组投资大佬视角（深度分析时启用）
巴菲特/芒格 | 林奇/木头姐 | 索罗斯/达里奥 | ...
"""

# BaseAgent.__init__ 支持 extended_prompt 参数
# run(deep_mode=True) 时拼接，日常不加载
```

**效果**：日常分析省 ~1500 tokens。

---

## 优化 3: 工具结果动态截断

**问题**：统一 8000 字符上限，大部分工具不需要。

**方案**：`config/agent_config.py` 按工具类型配置：

```python
TOOL_RESULT_LIMITS = {
    "search_financial_docs":  3000,
    "fetch_kline_data":       2000,
    "fetch_us_stock_info":    2500,
    "identify_stocks_in_text": 800,
    "summarize_findings":     2500,
    "generate_report":        4000,
    "default":                2500,
}
```

**效果**：每轮对话省 4000+ tokens。

---

## 优化 4: Prompt Caching

**问题**：System Prompt 每次重发，不计缓存。

**方案**：`app/agent/base.py` 消息顺序优化：

```python
def _build_initial_messages(self, task, deep_mode=False):
    messages = [
        {"role": "system", "content": full_prompt},  # 排第一，自动缓存
    ]
    # 历史压缩为 1 条摘要（而非 6 条逐条消息）
    if summary := self._summarize_history():
        messages.append({"role": "user", "content": summary})
    messages.append({"role": "user", "content": task})
    return messages
```

关键点：
- System Prompt 固定放首条（DeepSeek prefix cache 命中条件）
- 历史对话压缩，减少消息数
- Tools 定义不变 → 也享缓存

**效果**：命中缓存后每次调用省 ~3000 input tokens。

---

## 优化 5: 对话历史压缩

**问题**：逐条发送最近 3 轮对话（6 条消息），~1000 tokens。

**方案**：压缩为 1 条摘要：

```python
def _summarize_history(self):
    recent = self.conversation_history[-3:]
    lines = []
    for h in recent:
        q, a = h["q"][:80], h["a"][:120]
        lines.append(f"Q: {q}\nA: {a}")
    return "【对话历史】\n" + "\n---\n".join(lines)
```

**效果**：~1000 → ~300 tokens。

---

## 优化 6: 减少 ReAct 最大轮次

**问题**：`MAX_ITERATIONS = 8`，大部分任务 2-3 轮完成。

**方案**：`config/agent_config.py` 按 Agent 角色分档：

```python
MAX_ITERATIONS_MAP = {
    "Coordinator": 5,
    "Researcher":  4,
    "Analyst":     5,
    "Writer":      3,
}
```

**效果**：避免无效推理轮次。

---

## 预估效果汇总

| 场景 | 优化前 | 优化后 | 节省 |
|------|--------|--------|------|
| "你好" | ~500 tokens | 0 tokens | 100% |
| "搜索AIGC纪要" | ~8000 tokens | ~3000 tokens | ~60% |
| "分析茅台盘面" | ~12000 tokens | ~6000 tokens | ~50% |
| "生成深度报告" | ~20000 tokens | ~12000 tokens | ~40% |

---

## 涉及文件

| 文件 | 改动 |
|------|------|
| `app/main.py` | `classify_query()` 智能路由 |
| `config/agent_config.py` | System Prompt 分层、TOOL_RESULT_LIMITS、MAX_ITERATIONS_MAP |
| `app/agent/base.py` | 动态截断、历史压缩、缓存优化、token 日志 |
| `app/agent/analyst.py` | `extended_prompt` 参数支持 |
