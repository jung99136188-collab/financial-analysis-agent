"""
Analyst Agent — 金融数据分析专家

工具：
    - summarize_findings: 汇总提炼核心观点
    - compare_stocks: 多股票横向对比
    - extract_key_metrics: 提取关键指标
"""

import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.agent_config import (
    ANALYST_SYSTEM_PROMPT_CORE,
    ANALYST_SYSTEM_PROMPT_EXTENDED,
)
from .base import BaseAgent

# ============================================================
# 工具定义
# ============================================================
ANALYST_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "summarize_findings",
            "description": (
                "对搜集到的金融数据进行汇总分析，提炼核心观点和关键发现。"
                "输入原始数据，输出结构化的分析摘要。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "string",
                        "description": "需要分析的原始数据（Researcher 返回的搜索结果）"
                    },
                    "focus": {
                        "type": "string",
                        "description": "分析侧重点：'趋势判断'、'机构观点'、'政策影响'、'个股对比'、'风险识别' 等"
                    }
                },
                "required": ["data", "focus"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_stocks",
            "description": (
                "横向对比多只股票，从多个维度分析各自优劣。"
                "维度可包括：机构关注度、业绩表现、估值水平、市场情绪等。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "stocks_data": {
                        "type": "string",
                        "description": "包含多只股票相关信息的文本数据"
                    },
                    "dimensions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "需要对比的维度列表"
                    }
                },
                "required": ["stocks_data"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_key_metrics",
            "description": (
                "从文档中提取关键量化指标，如营收、利润、增速、PE、PB、目标价等。"
                "返回结构化的指标清单。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "包含金融数据的文本"
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_uzi_analysis",
            "description": (
                "调用 UZI-Skill 对指定股票做完整的量化深度分析。"
                "UZI-Skill 包含：22维数据采集、65位投资大佬角色扮演评审、"
                "DCF/Comps/BCG/Porter 等机构估值模型、杀猪盘检测。"
                "返回综合评分、评委投票分布、估值区间、HTML报告路径。"
                "适用场景：用户要求'深度分析某只股票'、'给个完整报告'。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "股票代码。A股: 600519.SH / 002273.SZ, 港股: 00700.HK, 美股: AAPL"
                    },
                    "depth": {
                        "type": "string",
                        "enum": ["lite", "medium", "deep"],
                        "description": "分析深度: lite(1-2分钟,速判), medium(5-8分钟,标准), deep(15-20分钟,深度)。默认 medium"
                    }
                },
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_technical_chart",
            "description": (
                "对K线数据进行技术面深度分析，识别形态和趋势信号。"
                "分析内容包括：趋势判断（多头/空头/震荡）、均线系统分析、"
                "经典形态识别（头肩顶/底、W底/M顶、三角形整理、旗形等）、"
                "量价关系分析、支撑阻力位识别、MACD/RSI/KDJ等指标信号。"
                "输入: fetch_kline_data 返回的K线数据。"
                "输出: 结构化的技术面分析报告。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kline_data": {
                        "type": "string",
                        "description": "fetch_kline_data 工具返回的K线数据（含OHLCV、均线、成交量等）"
                    },
                    "ticker": {
                        "type": "string",
                        "description": "股票代码，用于标注"
                    }
                },
                "required": ["kline_data"]
            }
        }
    }
]


# ============================================================
# 工具实现
# ============================================================

def _call_analysis_llm(llm_client, prompt, max_tokens=1500):
    """调用 LLM 做深度分析（通过注入的 llm_client）"""
    messages = [
        {"role": "system", "content": "你是专业的金融数据分析师，擅长从海量信息中提炼核心观点。"},
        {"role": "user", "content": prompt},
    ]
    response = llm_client.chat(messages=messages, temperature=0.3, max_tokens=max_tokens)
    return response.get("content", f"分析模型调用失败")


def _summarize_findings_impl(llm_client, data, focus):
    """汇总分析发现"""
    prompt = f"""请对以下金融数据进行深度分析，重点关注：{focus}

## 分析要求
1. 提取3-5个核心发现
2. 每个发现需要有数据支撑
3. 识别数据中的共识和分歧
4. 标注信息来源

## 原始数据
{data[:6000]}

请以结构化方式呈现分析结果：
### 核心发现
1. **发现一**: ...
   - 支撑数据: ...
   - 来源: ...

2. ...

### 关注要点
- ...

### 不确定性
- ...
"""
    return _call_analysis_llm(llm_client, prompt, max_tokens=2000)


def _compare_stocks_impl(llm_client, stocks_data, dimensions=None):
    """横向对比多只股票"""
    dims_text = "、".join(dimensions) if dimensions else "机构关注度、业绩表现、市场情绪"
    prompt = f"""请从以下维度对比分析相关股票：{dims_text}

## 对比要求
1. 列出每只股票在各维度的表现
2. 用表格呈现核心对比数据
3. 给出综合排名或推荐顺序
4. 标注信息来源

## 数据
{stocks_data[:6000]}

请输出：
### 维度对比表
| 股票 | {" | ".join(dimensions) if dimensions else "机构关注度 | 业绩表现 | 市场情绪"} | 综合评分 |
|------|------|------|------|------|
...

### 详细分析
...

### 关注建议
...
"""
    return _call_analysis_llm(llm_client, prompt, max_tokens=2000)


def _extract_key_metrics_impl(llm_client, text):
    """提取关键量化指标"""
    prompt = f"""请从以下文本中提取关键的量化指标：

{text[:4000]}

请以表格形式输出：
| 指标名称 | 数值 | 相关股票 | 来源 |
|----------|------|----------|------|
...

如果没有明确的量化指标，请说明"未发现量化指标"并列出文中提到的定性描述。
"""
    return _call_analysis_llm(llm_client, prompt, max_tokens=1000)


def _analyze_technical_chart_impl(llm_client, kline_data, ticker=""):
    """LLM 驱动的技术面分析（形态识别 + 趋势判断）"""
    prompt = f"""请对以下K线数据进行专业的技术面分析。

股票: {ticker or '未知'}

## 分析维度
1. **趋势判断**: 当前处于上升/下降/震荡趋势？给出判断依据
2. **均线系统**: 均线排列方向、金叉/死叉信号、支撑/压力位
3. **形态识别**: 是否出现经典形态（头肩顶/底、W底/M顶、三角形、旗形、箱体等）
4. **量价关系**: 放量上涨/缩量下跌的含义、量价背离信号
5. **关键位置**: 支撑位、阻力位、突破/破位判断
6. **综合评分**: 技术面 1-10 分

## K线数据
{kline_data[:5000]}

## 要求
- 每个判断都要引用具体数据（如"MA5=187.5上穿MA20=182.3，形成金叉"）
- 形态识别要描述位置和特征（如"在60日高点附近形成双顶，颈线位于175"）
- 给出具体的支撑/阻力价位
- 最后给出技术面综合评分（1-10）及操作建议（多头持有/观望/减仓/空仓）
"""
    return _call_analysis_llm(llm_client, prompt, max_tokens=2000)


def _run_uzi_analysis_impl(ticker, depth="medium"):
    """调用 UZI-Skill CLI 分析股票"""
    import subprocess
    from config.agent_config import UZI_ENABLED, UZI_PATH

    if not UZI_ENABLED:
        return "UZI-Skill 工具未启用。请在 config/agent_config.py 中设置 UZI_ENABLED=True"

    uzi_path = os.environ.get("UZI_PATH", UZI_PATH)
    if not os.path.isdir(uzi_path):
        return (
            f"UZI-Skill 未找到于 {uzi_path}。\n"
            f"安装方法: git clone https://github.com/wbh604/UZI-Skill.git {uzi_path}\n"
            f"然后: cd {uzi_path} && pip install -r requirements.txt"
        )

    cmd = f"python run.py {ticker} --depth {depth} --no-browser"
    print(f"    [Analyst] 调用 UZI-Skill: {cmd} (cwd={uzi_path})")

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=600, cwd=uzi_path
        )
        stdout = result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout
        stderr = result.stderr[-500:] if len(result.stderr) > 500 else result.stderr

        if result.returncode != 0:
            return f"UZI-Skill 运行失败 (exit={result.returncode})\nstderr:\n{stderr}\nstdout:\n{stdout}"

        # 尝试读取 synthesis.json 获取核心结论
        import glob
        cache_dir = os.path.join(uzi_path, "skills", "deep-analysis", "scripts", ".cache", ticker.replace(".", "_"))
        synthesis_files = glob.glob(os.path.join(cache_dir, "synthesis*.json")) if os.path.isdir(cache_dir) else []
        if synthesis_files:
            with open(synthesis_files[0], "r", encoding="utf-8") as f:
                synthesis = json.load(f)
            score = synthesis.get("composite_score", "N/A")
            verdict = synthesis.get("verdict", "N/A")
            return (
                f"UZI-Skill 分析完成 ({depth}模式)\n"
                f"综合评分: {score} | 判定: {verdict}\n"
                f"完整报告: {uzi_path}/skills/deep-analysis/scripts/reports/\n"
                f"摘要:\n{stdout[:2000]}"
            )

        return f"UZI-Skill 运行完成\nstdout:\n{stdout}"

    except subprocess.TimeoutExpired:
        return "UZI-Skill 运行超时（超过10分钟）。建议使用 lite 模式或检查网络。"
    except Exception as e:
        return f"UZI-Skill 调用异常: {str(e)}"


# ============================================================
# AnalystAgent
# ============================================================

class AnalystAgent(BaseAgent):
    """金融数据分析 Agent（内置 UZI 方法论 + 可选 UZI CLI 工具）"""

    def __init__(self, llm_client):
        self._analysis_llm = llm_client
        tool_handlers = {
            "summarize_findings": lambda args: _summarize_findings_impl(
                llm_client=self._analysis_llm,
                data=args.get("data", ""),
                focus=args.get("focus", "综合分析"),
            ),
            "compare_stocks": lambda args: _compare_stocks_impl(
                llm_client=self._analysis_llm,
                stocks_data=args.get("stocks_data", ""),
                dimensions=args.get("dimensions"),
            ),
            "extract_key_metrics": lambda args: _extract_key_metrics_impl(
                llm_client=self._analysis_llm,
                text=args.get("text", "")
            ),
            "analyze_technical_chart": lambda args: _analyze_technical_chart_impl(
                llm_client=self._analysis_llm,
                kline_data=args.get("kline_data", ""),
                ticker=args.get("ticker", ""),
            ),
            "run_uzi_analysis": lambda args: _run_uzi_analysis_impl(
                ticker=args.get("ticker", ""),
                depth=args.get("depth", "medium"),
            ),
        }
        super().__init__(
            name="Analyst",
            system_prompt=ANALYST_SYSTEM_PROMPT_CORE,
            extended_prompt=ANALYST_SYSTEM_PROMPT_EXTENDED,
            tools=ANALYST_TOOLS,
            llm_client=llm_client,
            tool_handlers=tool_handlers,
        )
