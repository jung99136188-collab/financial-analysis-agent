"""
Writer Agent — 金融报告撰写专家

工具：
    - generate_report: 生成专业金融分析报告
    - format_data_table: 将数据格式化为 Markdown 表格

使用 DeepSeek R1 模型进行深度报告生成。
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.agent_config import (
    WRITER_SYSTEM_PROMPT,
)
from .base import BaseAgent

# ============================================================
# 工具定义
# ============================================================
WRITER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "generate_report",
            "description": (
                "根据分析材料生成专业的金融研究报告。"
                "报告包含：摘要、行业背景、核心观点、个股分析、风险提示。"
                "所有引用必须标注来源 [来源:文档ID]。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "报告主题/概念，如'AIGC板块'、'光伏产业链'"
                    },
                    "analysis_data": {
                        "type": "string",
                        "description": "Analyst Agent 提供的分析材料"
                    },
                    "raw_data": {
                        "type": "string",
                        "description": "Researcher Agent 提供的原始数据（用于引用标注）"
                    },
                    "report_style": {
                        "type": "string",
                        "enum": ["深度研究", "快速简报", "数据周报"],
                        "description": "报告风格，默认'深度研究'"
                    }
                },
                "required": ["topic", "analysis_data"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "format_data_table",
            "description": (
                "将结构化数据格式化为 Markdown 表格，便于在报告中展示。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "data_description": {
                        "type": "string",
                        "description": "数据描述和需要制作的表格说明"
                    },
                    "table_style": {
                        "type": "string",
                        "enum": ["comparison", "timeline", "metrics"],
                        "description": "表格风格: comparison(对比表), timeline(时间线), metrics(指标表)"
                    }
                },
                "required": ["data_description"]
            }
        }
    }
]


# ============================================================
# 工具实现
# ============================================================

def _call_writer_llm(llm_client, prompt, max_tokens=3000):
    """调用 LLM 生成报告（通过注入的 llm_client）"""
    messages = [
        {"role": "system", "content": "你是杰出的金融分析师，擅长撰写高质量的金融深度研究报告。"},
        {"role": "user", "content": prompt},
    ]
    response = llm_client.chat(messages=messages, temperature=0.2, max_tokens=max_tokens)
    return response.get("content", "报告生成失败，请稍后重试。")


def _generate_report_impl(llm_client, topic, analysis_data, raw_data="", report_style="深度研究"):
    """生成金融分析报告"""
    # 根据报告风格调整详细程度
    style_guide = {
        "深度研究": "撰写一份详尽的深度研究报告，包含摘要、行业背景、核心观点（3-5个）、个股详细分析、风险提示",
        "快速简报": "撰写一份简洁的快速简报，包含核心发现（2-3点）、关键数据、简要建议",
        "数据周报": "撰写一份数据周报，以表格为主呈现核心数据，配简要文字说明",
    }

    prompt = f"""请撰写一份关于"{topic}"的金融分析报告。

## 报告类型
{report_style}

## 内容要求
{style_guide.get(report_style, style_guide["深度研究"])}

## 格式要求
- 使用 Markdown 格式
- 重要数据用表格呈现
- 每个观点和数据标注来源，格式：[来源:文档ID]
- 关键结论用 **加粗** 突出
- 语言专业但不晦涩，面向投资从业者

## 分析材料（来自 Analyst）
{analysis_data[:6000]}

## 原始数据参考（用于精确引用）
{raw_data[:3000] if raw_data else "（无额外原始数据）"}

## 特别提醒
- 仅基于提供的材料撰写，不要杜撰信息
- 不能确定的内容请标注"基于现有数据尚不明确"
- 报告末尾附：免责声明
"""
    return _call_writer_llm(llm_client, prompt, max_tokens=3000)


def _format_data_table_impl(llm_client, data_description, table_style="comparison"):
    """格式化数据表格"""
    prompt = f"""请根据以下描述，生成一个格式规范的 Markdown 表格。

表格类型: {table_style}
数据描述: {data_description}

要求：
- 表格对齐、格式规范
- 表头清晰
- 如有数值，保留合适精度
- 直接输出表格，不需要额外解释
"""
    return _call_writer_llm(llm_client, prompt, max_tokens=800)


# ============================================================
# WriterAgent
# ============================================================

class WriterAgent(BaseAgent):
    """金融报告撰写 Agent"""

    def __init__(self, llm_client):
        self._writer_llm = llm_client
        tool_handlers = {
            "generate_report": lambda args: _generate_report_impl(
                llm_client=self._writer_llm,
                topic=args.get("topic", ""),
                analysis_data=args.get("analysis_data", ""),
                raw_data=args.get("raw_data", ""),
                report_style=args.get("report_style", "深度研究"),
            ),
            "format_data_table": lambda args: _format_data_table_impl(
                llm_client=self._writer_llm,
                data_description=args.get("data_description", ""),
                table_style=args.get("table_style", "comparison"),
            ),
        }
        super().__init__(
            name="Writer",
            system_prompt=WRITER_SYSTEM_PROMPT,
            tools=WRITER_TOOLS,
            llm_client=llm_client,
            tool_handlers=tool_handlers,
        )
