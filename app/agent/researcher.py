"""
Research Agent — 金融信息搜索专家

工具：
    - search_financial_docs: 统一搜索入口（纪要/研报/公告/点评）
    - identify_stocks_in_text: 从文本识别股票
"""

import json
import sys
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.agent_config import (
    RESEARCHER_SYSTEM_PROMPT,
)
from config.es_config import (
    es,
    MINUTES_INDEX, MINUTES_QUERY, MINUTES_SOURCE,
    REPORT_INDEX, REPORT_QUERY, REPORT_SOURCE,
    ANNOUNCEMENT_INDEX, ANNOUNCEMENT_QUERY, ANNOUNCEMENT_SOURCE,
    COMMENT_INDEX, COMMENT_QUERY, COMMENT_SOURCE,
)
from config.api_config import STOCK_MATCHER_URL, STOCK_MATCHER_HEADERS
from .base import BaseAgent

# ============================================================
# 工具定义（OpenAI function calling 格式）
# ============================================================
RESEARCHER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_financial_docs",
            "description": (
                "搜索金融文档，支持四种数据源。"
                "minutes=路演纪要(近3月), report=研报(近3月), "
                "announcement=股票公告(近6月), comment=分析师点评(近2月), "
                "all=全部搜索。返回文档摘要（标题、时间、股票、内容片段）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词，如'AIGC'、'光伏'、'减肥药'。支持中英文。"
                    },
                    "doc_type": {
                        "type": "string",
                        "enum": ["minutes", "report", "announcement", "comment", "all"],
                        "description": "文档类型，默认 all"
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "每种类型返回的最多文档数，默认5，最大20"
                    }
                },
                "required": ["keyword"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "identify_stocks_in_text",
            "description": (
                "从文本中识别股票代码和名称。"
                "用于确认某段内容涉及哪些股票，返回股票代码列表。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "需要识别股票的文本内容"
                    }
                },
                "required": ["text"]
            }
        }
    }
]


# ============================================================
# 工具实现
# ============================================================

def _search_single_source(index, base_query, source_fields, time_field, time_limit_days, keyword):
    """搜索单个数据源"""
    now = datetime.now()
    from_date = (now - timedelta(days=time_limit_days)).strftime("%Y-%m-%d %H:%M:%S")

    query_copy = json.loads(json.dumps(base_query))

    # 更新时间范围
    for condition in query_copy["query"]["bool"]["must"]:
        if "range" in condition and time_field in condition["range"]:
            condition["range"][time_field]["gt"] = from_date

    # 添加关键词搜索
    should_conditions = []
    for field in ["content", "full_content"]:
        should_conditions.append({"match_phrase": {field: keyword}})
    query_copy["query"]["bool"]["should"] = should_conditions
    query_copy["query"]["bool"]["minimum_should_match"] = 1

    try:
        response = es.search(
            index=index,
            body=query_copy,
            _source=source_fields,
            size=20
        )
        return response["hits"]["hits"]
    except Exception as e:
        print(f"    ES搜索 [{index}] 出错: {str(e)[:100]}")
        return []


def _search_financial_docs_impl(keyword, doc_type="all", top_n=5):
    """搜索金融文档的实现"""
    # 数据源配置: (索引, 基础查询, 返回字段, 时间字段, 时间范围天数)
    sources = []

    if doc_type in ("minutes", "all"):
        sources.append(("纪要", MINUTES_INDEX, MINUTES_QUERY, MINUTES_SOURCE, "publish_date", 90))
    if doc_type in ("report", "all"):
        sources.append(("研报", REPORT_INDEX, REPORT_QUERY, REPORT_SOURCE, "time", 90))
    if doc_type in ("announcement", "all"):
        sources.append(("公告", ANNOUNCEMENT_INDEX, ANNOUNCEMENT_QUERY, ANNOUNCEMENT_SOURCE, "end_date", 180))
    if doc_type in ("comment", "all"):
        sources.append(("点评", COMMENT_INDEX, COMMENT_QUERY, COMMENT_SOURCE, "time", 60))

    all_results = {}

    # 并发搜索所有数据源
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for source_name, index, query, src_fields, time_field, time_limit in sources:
            future = executor.submit(
                _search_single_source, index, query, src_fields, time_field, time_limit, keyword
            )
            futures[future] = source_name

        for future in futures:
            source_name = futures[future]
            try:
                hits = future.result()
                # 提取简要信息
                summaries = []
                for hit in hits[:top_n]:
                    src = hit.get("_source", {})
                    content_field = "full_content" if "full_content" in src else "content"
                    content = src.get(content_field, "")
                    if isinstance(content, str):
                        content = content[:300]
                    elif content is None:
                        content = ""

                    summaries.append({
                        "id": hit.get("_id", ""),
                        "title": src.get("title", "无标题"),
                        "time": src.get("publish_date") or src.get("time") or src.get("end_date", ""),
                        "stock": str(src.get("stock") or src.get("sec", "未知")),
                        "snippet": content,
                    })
                all_results[source_name] = summaries
                print(f"    [{source_name}] 找到 {len(hits)} 条，返回 {len(summaries)} 条")
            except Exception as e:
                all_results[source_name] = []
                print(f"    [{source_name}] 搜索失败: {str(e)[:100]}")

    # 格式化返回结果
    total = sum(len(v) for v in all_results.values())
    result_lines = [f"搜索关键词: '{keyword}'，共找到 {total} 条结果\n"]

    for source_name, summaries in all_results.items():
        if summaries:
            result_lines.append(f"\n## {source_name} ({len(summaries)}条)")
            for i, doc in enumerate(summaries, 1):
                result_lines.append(
                    f"  {i}. [{doc['id']}] {doc['title']}\n"
                    f"     股票: {doc['stock']} | 时间: {doc['time']}\n"
                    f"     摘要: {doc['snippet'][:200]}"
                )
        else:
            result_lines.append(f"\n## {source_name}: 无结果")

    return "\n".join(result_lines)


def _identify_stocks_impl(text):
    """识别文本中的股票"""
    if not text or len(text.strip()) == 0:
        return "文本为空，无法识别股票。"

    try:
        payload = json.dumps({
            "is_keep_vague": "1",
            "scope": "prd",
            "content": text[:1000]
        })

        response = requests.post(
            STOCK_MATCHER_URL,
            headers=STOCK_MATCHER_HEADERS,
            data=payload,
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            stocks = result.get("data", [])
            if stocks:
                lines = ["识别到的股票:"]
                for s in stocks:
                    code = s.get("stock_code", "未知")
                    name = s.get("stock_name", "")
                    lines.append(f"  - {code} {name}")
                return "\n".join(lines)
            else:
                return "未识别到股票。"
        else:
            return f"股票识别API返回状态码: {response.status_code}"
    except Exception as e:
        return f"股票识别失败: {str(e)}"


# ============================================================
# ResearcherAgent
# ============================================================

class ResearcherAgent(BaseAgent):
    """金融信息研究 Agent"""

    def __init__(self, llm_client):
        tool_handlers = {
            "search_financial_docs": lambda args: _search_financial_docs_impl(
                keyword=args.get("keyword", ""),
                doc_type=args.get("doc_type", "all"),
                top_n=args.get("top_n", 5),
            ),
            "identify_stocks_in_text": lambda args: _identify_stocks_impl(
                text=args.get("text", "")
            ),
        }
        super().__init__(
            name="Researcher",
            system_prompt=RESEARCHER_SYSTEM_PROMPT,
            tools=RESEARCHER_TOOLS,
            llm_client=llm_client,
            tool_handlers=tool_handlers,
        )
