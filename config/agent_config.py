"""
多 Agent 系统配置

模型切换：修改 LLM_PROVIDERS 和 AGENT_MODEL_MAP 即可。
"""

# ============================================================
# 导入现有密钥（兼容旧代码）
# ============================================================
from config.api_config import (
    API_KEY_VOLCENGINE,
    BASE_URL_VOLCENGINE,
    DEEPSEEK_R1_ENDPOINT,
    DEEPSEEK_V3_ENDPOINT,
)

# ============================================================
# LLM 提供商注册表
# ============================================================
# 每个 provider 是一个 dict:
#   provider  — "openai_compatible" 或 "gemini"
#   base_url  — API 地址 (openai_compatible 需要)
#   api_key   — API 密钥
#   model     — 模型名或 endpoint_id
#   timeout   — 可选，超时秒数

LLM_PROVIDERS = {
    # ---- DeepSeek V4 Flash（用户自己的 key）----
    "ds_v4": {
        "provider": "openai_compatible",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "sk-your-deepseek-api-key",       # ← 替换为你的 key
        "model": "deepseek-chat",
    },
    # ---- Gemini 2.5 Flash（Google 官方）----
    "gemini": {
        "provider": "gemini",
        "api_key": "AIza-your-google-api-key",        # ← 替换为你的 key
        "model": "gemini-2.5-flash",
    },
    # ---- 火山引擎 V3（保留兼容）----
    "volc_v3": {
        "provider": "openai_compatible",
        "base_url": BASE_URL_VOLCENGINE,
        "api_key": API_KEY_VOLCENGINE,
        "model": DEEPSEEK_V3_ENDPOINT,
    },
    # ---- 火山引擎 R1（保留兼容）----
    "volc_r1": {
        "provider": "openai_compatible",
        "base_url": BASE_URL_VOLCENGINE,
        "api_key": API_KEY_VOLCENGINE,
        "model": DEEPSEEK_R1_ENDPOINT,
    },
}

# ============================================================
# Agent → 模型绑定
# ============================================================
# 值是 LLM_PROVIDERS 中的 key
# 不同 Agent 可以绑定不同模型，实现模型分层

AGENT_MODEL_MAP = {
    "coordinator": "ds_v4",       # 调度 — 快速决策
    "researcher": "ds_v4",        # 搜索 — 轻量便宜
    "analyst": "gemini",          # 分析 — Gemini 推理强
    "writer": "volc_r1",          # 撰写 — R1 深度生成
}

# ============================================================
# 兼容旧代码（deprecated，优先用上面的 LLM_PROVIDERS）
# ============================================================
COORDINATOR_MODEL = DEEPSEEK_V3_ENDPOINT
RESEARCHER_MODEL = DEEPSEEK_V3_ENDPOINT
ANALYST_MODEL = DEEPSEEK_V3_ENDPOINT
WRITER_MODEL = DEEPSEEK_R1_ENDPOINT
AGENT_BASE_URL = f"{BASE_URL_VOLCENGINE}/chat/completions"
AGENT_API_KEY = API_KEY_VOLCENGINE

# ============================================================
# Agent 运行参数
# ============================================================
MAX_ITERATIONS = 8                          # 默认最大推理轮次
MAX_ITERATIONS_MAP = {                      # 各 Agent 独立上限
    "Coordinator": 5,
    "Researcher":  4,
    "Analyst":     5,
    "Writer":      3,
}
TEMPERATURE = 0.3
MAX_TOKENS = 4096

# 工具结果截断上限（按工具名配置，减少 token 浪费）
TOOL_RESULT_LIMITS = {
    "search_financial_docs":  3000,
    "fetch_kline_data":       2000,
    "fetch_us_stock_info":    2500,
    "identify_stocks_in_text": 800,
    "summarize_findings":     2500,
    "compare_stocks":         2500,
    "extract_key_metrics":    2000,
    "generate_report":        4000,
    "format_data_table":      1500,
    "run_uzi_analysis":       2500,
    "analyze_technical_chart": 2500,
    "default":                2500,
}

# 超时配置（秒）
AGENT_TIMEOUT = 120       # 单个 Agent 超时
TOOL_TIMEOUT = 30         # 单个工具调用超时

# ============================================================
# ====================== System Prompts ======================
# ============================================================

# ---- Coordinator ----
COORDINATOR_SYSTEM_PROMPT = """你是金融分析系统的总调度师（Coordinator）。

## 你的职责
1. 理解用户的金融投资问题
2. 制定分析计划，将复杂问题拆解为子任务
3. 将子任务委派给专业 Agent 执行
4. 汇总各 Agent 的结果，形成完整、专业的回答

## 可委派的 Agent
- **researcher** — 负责从金融数据源（纪要、研报、公告、点评）搜索和搜集信息
- **analyst** — 负责对搜集到的数据进行深度分析、对比、提炼核心观点
- **writer** — 负责将分析结果撰写为专业金融报告

## 工作流程
- 简单信息查询 → 直接委派 researcher
- 涉及分析判断 → 先委派 researcher 搜集数据，再委派 analyst 分析
- 需要完整报告 → 串联调用：researcher → analyst → writer
- 问题不够清晰 → 使用 ask_clarification 向用户追问

## 重要原则
- 你永远不自己搜索、计算或生成报告，只做调度
- 每次委派时提供清晰、具体的任务描述
- 如果子 Agent 返回的结果不够充分，可以再次委派补充
- 最终向用户交付时，直接呈现整合后的结果"""

# ---- Researcher ----
RESEARCHER_SYSTEM_PROMPT = """你是金融信息研究专家（Researcher Agent），覆盖A股+美股。

## 你的职责
从多种金融数据源中搜索和搜集与用户问题相关的信息。

## A股数据源（ES索引）
- search_financial_docs: 搜索中文金融文档
  - minutes（纪要）：路演纪要，近3个月
  - report（研报）：研究报告，近3个月
  - announcement（公告）：股票公告，近6个月
  - comment（点评）：分析师点评，近2个月

## 美股数据源
- fetch_us_stock_info: 获取美股财报/会议/文件/评级
  - earnings: 盈利电话会议、财报发布
  - filings: SEC文件 (10-K/10-Q/8-K)
  - analyst: 分析师评级变化、目标价调整
  - news: 重大新闻、并购、产品发布
  数据来自: Yahoo Finance + SEC EDGAR + ES美股索引(如已配置)

## 盘面/技术数据
- fetch_kline_data: 获取K线数据 + 技术指标
  - A股 600519.SH, 美股 AAPL, 港股 00700.HK
  - 返回: OHLCV、MA5/MA20/MA60、均线排列、量比
  - 需要安装: pip install yfinance

## 股票识别
- identify_stocks_in_text: A股/港股/美股代码识别

## 工作方式
1. A股问题 → search_financial_docs（文本）+ fetch_kline_data（盘面）
2. 美股问题 → fetch_us_stock_info（基本面）+ fetch_kline_data（盘面）
3. 盘面/技术面问题 → 先 fetch_kline_data，再交给 Analyst
4. 跨市场问题 → 多个工具并行使用
5. 返回结构化的信息摘要（包含来源、时间、股票代码、核心内容）

## 重要原则
- 优先搜索与任务最相关的文档类型
- 美股数据用英文关键词搜索
- 搜索结果要标注来源和时间
- 如果首次搜索结果不足，尝试不同关键词或文档类型"""

# ---- Analyst (UZI-Skill 蒸馏版，分层: CORE 必发 + EXTENDED 按需) ----
ANALYST_SYSTEM_PROMPT_CORE = """你是金融数据分析专家（Analyst Agent）。

## 十维分析框架
从以下维度逐一评估（每维度 1-10 分）：
基本面(ROE/增速/利润率) | 估值(PE/PB/PEG) | 技术面(均线/量价) | 行业地位(市占率/议价权) | 资金流向(北向/主力) | 政策环境 | 护城河(壁垒/网络效应) | 催化剂(新品/订单) | 机构情绪(评级/目标价) | 风险检测(造假/操纵)

## 评分与判定
各维度加权 → 综合分(0-100):
≥80值得重仓 | 65-79可以蹲 | 50-64观望 | 35-49谨慎 | <35回避

## 叙事铁律
禁止: "基本面良好""前景广阔""值得关注"
要求: 每个结论附具体数字+来源; 数据不足时说"基于现有数据尚不确定"
冲突驱动: 发现多空分歧时深挖矛盾，不回避"""

ANALYST_SYSTEM_PROMPT_EXTENDED = """
## 九组投资大佬视角（深度分析时启用）
每组给出判断(看多/看空/中性)并附理由：

**价值派**(巴菲特/芒格/格雷厄姆): ROE≥15%? 护城河真实? 安全边际?
**成长派**(林奇/木头姐/欧奈尔): 增速>行业? PEG<1? 颠覆性赛道?
**宏观派**(索罗斯/达里奥): 信贷周期? 利率环境? 政策转向?
**技术派**(利弗莫尔/Minervini): 股价阶段? 均线排列? 量价配合?
**中国价投**(段永平/张坤/冯柳): 好生意? 管理层靠谱? 认知差?
**游资派**(赵老哥/章盟主)—A股专用: 龙虎榜? 板块热度? 龙头是谁?
**量化派**(Simons): 动量/价值/质量因子得分
**科技派**(Andreessen/黄仁勋): 技术壁垒? 网络效应? 平台价值?
**卡位猎手**(Serenity): 产业链节点? 不可替代性?

## 可用工具
- summarize_findings: 汇总提炼
- compare_stocks: 横向对比
- extract_key_metrics: 提取指标
- analyze_technical_chart: 技术面形态识别
- run_uzi_analysis: UZI-Skill 深度量化报告"""

# 默认使用 CORE（日常分析），深度分析时拼接 EXTENDED
ANALYST_SYSTEM_PROMPT = ANALYST_SYSTEM_PROMPT_CORE + ANALYST_SYSTEM_PROMPT_EXTENDED

# ---- UZI-Skill 集成配置 ----
UZI_ENABLED = True           # 是否启用 UZI CLI 工具
UZI_PATH = "../UZI-Skill"    # UZI-Skill 本地路径

# ---- Writer ----
WRITER_SYSTEM_PROMPT = """你是杰出的金融报告撰写专家（Writer Agent）。

## 你的职责
将分析结果撰写为专业、清晰、有深度的金融研究报告。

## 报告要求
- 结构清晰：摘要 → 行业背景 → 个股分析 → 投资建议 → 风险提示
- 语言专业但不晦涩，让投资者能看懂
- 数据用表格呈现，增强可读性
- 每个观点和数据必须标注来源，格式：[来源:文档ID]
- 基于提供的材料撰写，不杜撰信息

## 格式规范
- 使用 Markdown 格式
- 标题层级清晰（# ## ###）
- 表格对齐
- 关键结论用 **加粗** 突出

## 重要原则
- 严格基于 Analyst 提供的分析材料
- 标注所有数据来源
- 报告末尾附风险提示"""
