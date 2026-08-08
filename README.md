# 金融分析多 Agent 协作系统

基于 ReAct 模式的多智能体金融分析系统。Coordinator 调度 Researcher、Analyst、Writer 三个专业 Agent 协作，自动完成从信息搜集到报告生成的全流程。

## 架构

```
                         用户提问
                            │
                            ▼
                  ┌─────────────────┐
                  │  Coordinator    │  DeepSeek V3 — 总调度
                  │  理解意图·委派任务  │
                  └───────┬─────────┘
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
   ┌────────────┐ ┌────────────┐ ┌────────────┐
   │ Researcher │ │  Analyst   │ │   Writer   │
   │  V3 信息搜集 │ │  V3 数据分析 │ │  R1 报告撰写 │
   └──────┬─────┘ └──────┬─────┘ └──────┬─────┘
          │              │              │
     ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
     │ ES 搜索  │    │ 观点提炼 │    │ 报告生成 │
     │ 股票识别  │    │ 横向对比 │    │ 表格格式化│
     │ 多源并发  │    │ 指标提取 │    │ 来源引用 │
     └─────────┘    └─────────┘    └─────────┘
```

### Agent 工作流

| Agent | 模型 | 职责 | 工具 |
|-------|------|------|------|
| **Coordinator** | DeepSeek V3 | 理解意图、制定计划、委派任务、汇总交付 | 委派×3、追问、交付 |
| **Researcher** | DeepSeek V3 | 多源搜索金融文档、识别股票 | ES搜索、股票识别API |
| **Analyst** | DeepSeek V3 | 提炼观点、对比股票、提取指标 | R1辅助分析、对比分析 |
| **Writer** | DeepSeek R1 | 撰写专业金融报告 | R1深度生成、表格格式化 |

### ReAct 循环

每个 Agent 内部运行 **ReAct（Reasoning + Acting）** 循环：

```
Think → 选择工具 → 执行工具 → 观察结果 → Think → ... → 输出答案
```

LLM 自主决定何时调用工具、何时结束，而非代码预设流程。

## 项目结构

```
.
├── app/
│   ├── agent/                 # 多 Agent 系统
│   │   ├── __init__.py        # Agent 包
│   │   ├── base.py            # Agent 基类 — ReAct 循环引擎
│   │   ├── coordinator.py     # 调度 Agent + 委派工具
│   │   ├── researcher.py      # 研究 Agent + ES搜索/股票识别
│   │   ├── analyst.py         # 分析 Agent + 观点提炼/对比
│   │   └── writer.py          # 撰写 Agent + 报告生成
│   ├── main.py                # 主入口（Agent / Pipeline 双模式）
│   └── utils.py               # 工具函数
├── config/
│   ├── agent_config.py        # Agent 配置 + System Prompts
│   ├── api_config.py          # API 密钥（需自行创建，见快速开始）
│   ├── api_config.example.py  # API 配置模板
│   └── es_config.py           # Elasticsearch 配置
├── output/                    # 输出目录（报告/excel）
├── requirements.txt
├── .gitignore
└── LICENSE
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API 密钥

```bash
# 复制模板
cp config/api_config.example.py config/api_config.py

# 编辑 api_config.py，填入真实密钥：
#   - API_KEY_VOLCENGINE: 火山引擎 API Key
#   - DEEPSEEK_V3_ENDPOINT: V3 模型 endpoint
#   - DEEPSEEK_R1_ENDPOINT: R1 模型 endpoint
#   - STOCK_MATCHER_URL: 股票识别服务地址
```

### 3. 确保 ES 和股票识别服务可用

系统依赖两个后端服务：
- **Elasticsearch**：存储金融文档（纪要/研报/公告/点评），配置见 `config/es_config.py`
- **股票识别 API**：REST 接口，URL 在 `api_config.py` 中配置

### 4. 运行

```bash
python app/main.py
```

```
============================================================
  金融分析助手
============================================================
  1. 多 Agent 协作模式（推荐）— AI Agent 自主决策协作
  2. Pipeline 快速模式 — 原有固定流程
============================================================

请选择模式 (1/2):
```

## 使用示例

### 多 Agent 模式

```
🧠 > 最近AIGC概念板块有哪些值得关注的股票？

[Coordinator] → 委派 Researcher: 搜索AIGC概念板块近3个月纪要和研究报告
[Researcher] → search_financial_docs(keyword="AIGC", doc_type="all")
[Researcher] → 找到 23 条结果

[Coordinator] → 委派 Analyst: 分析AIGC相关股票的机构观点
[Analyst] → summarize_findings(data=..., focus="机构关注度")
[Analyst] → 完成分析

[Coordinator] → 委派 Writer: 生成AIGC板块分析报告
[Writer] → generate_report(topic="AIGC板块", ...)

============================================================
# AIGC板块投资分析报告
## 核心发现
1. **AI应用加速落地**: 近3个月路演纪要中AIGC提及率环比增长45%...
   [来源:RRP00000000058924250]
...
```

### Pipeline 模式（原版）

输入问题 → 自动提取关键词 → ES四路并发查询 → 股票识别 → 排序去重 → 生成报告。

两种模式可通过输入 `切换` 互相切换。

## 技术栈

Agent 核心通过 LLM 适配层调用模型，不依赖任何 Agent 框架：

```python
# app/agent/base.py 核心逻辑
class BaseAgent:
    def run(self, task):
        messages = [system_prompt, user_task]
        for _ in range(max_iterations):
            response = llm.chat(messages, tools=self.tools)  # 适配层统一接口
            if response.tool_calls:
                for tc in response.tool_calls:
                    result = execute_tool(tc.name, tc.args)
                    messages.append(tool_result(result))
            else:
                return response.content
```

ReAct 循环约 80 行代码，LLM 自主决定工具调用时机和终止条件。

### 多模型支持

通过 `config/agent_config.py` 切换模型，每个 Agent 可独立绑定不同模型：

```python
# 注册模型
LLM_PROVIDERS = {
    "ds_v4": {"provider": "openai_compatible", "base_url": "...", "api_key": "...", "model": "deepseek-chat"},
    "gemini": {"provider": "gemini", "api_key": "...", "model": "gemini-2.5-flash"},
}

# 绑定到 Agent
AGENT_MODEL_MAP = {
    "coordinator": "ds_v4",    # DeepSeek V4 Flash
    "researcher": "ds_v4",     # DeepSeek V4 Flash
    "analyst": "gemini",       # Gemini 2.5 Flash
    "writer": "gemini",        # Gemini 2.5 Flash
}
```

支持的模型格式：
- **OpenAI 兼容**：DeepSeek (官方/火山引擎)、GPT-4o、任何兼容 `/v1/chat/completions` 的服务
- **Gemini**：Google 官方 API，适配器内部自动做格式转换

### UZI-Skill 集成（可选）

Analyst Agent 内置了 [UZI-Skill](https://github.com/wbh604/UZI-Skill)（5.6k stars）的分析方法论：

- **10 维分析框架**：基本面 / 估值 / 技术面 / 行业地位 / 资金流向 / 政策环境 / 护城河 / 催化剂 / 机构情绪 / 风险检测
- **9 组投资大佬视角**：价值派(巴菲特/芒格) / 成长派(林奇/木头姐) / 宏观派(索罗斯/达里奥) / 技术派(利弗莫尔) / 中国价投(段永平/张坤) / 游资派(赵老哥/章盟主) / 量化派(Simons) / 科技派(Andreessen) / 卡位猎手(Serenity)
- **评分体系**：1-10 维度评分 → 加权 → 综合分 → 判定档位(值得重仓/可以蹲/观望/谨慎/回避)
- **叙事铁律**：禁用"基本面良好"等空话，每个结论必须有具体数字和来源

**可选 CLI 工具**：安装 UZI-Skill 后，Analyst 可调用 `run_uzi_analysis` 工具获取完整量化报告：

```bash
git clone https://github.com/wbh604/UZI-Skill.git ../UZI-Skill
cd ../UZI-Skill && pip install -r requirements.txt
```

在 `config/agent_config.py` 中确认：
```python
UZI_ENABLED = True
UZI_PATH = "../UZI-Skill"
```

### 关键设计决策

1. **Coordinator 中转模式**：Agent 之间不直接通信，统一由 Coordinator 调度，架构清晰可追踪
2. **上下文隔离**：子 Agent 只接收委派任务所需的上下文片段，不被全量历史淹没
3. **优雅降级**：子 Agent 失败时 Coordinator 可重试、换策略或向用户坦诚说明
4. **向后兼容**：保留原 Pipeline 作为快速模式，两套模式可互相切换

## 数据源

| 数据源 | 索引 | 时间范围 | 说明 |
|--------|------|----------|------|
| 路演纪要 | roadshow_summary | 近3个月 | MT 记录 |
| 研究报告 | report | 近3个月 | 券商研报 |
| 股票公告 | stock_announcement | 近6个月 | 公司公告 |
| 分析师点评 | comment | 近2个月 | txt 类点评 |

## 依赖

```
elasticsearch>=7.0.0,<8.0.0
requests>=2.25.0
pandas>=1.3.0
openpyxl>=3.0.0
python-dateutil>=2.8.2
```

## 注意事项

- 本项目依赖 Elasticsearch 和内部股票识别服务，需确保这些后端服务可访问
- 查询结果质量取决于数据源中的内容质量和时效性
- 多 Agent 模式下每次对话可能产生多次 API 调用，请注意用量
