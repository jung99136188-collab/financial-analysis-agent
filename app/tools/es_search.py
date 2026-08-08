"""ES 金融文档搜索工具"""

import json
import sys
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from langchain_core.tools import tool

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.es_config import (
    es,
    MINUTES_INDEX, MINUTES_QUERY, MINUTES_SOURCE,
    REPORT_INDEX, REPORT_QUERY, REPORT_SOURCE,
    ANNOUNCEMENT_INDEX, ANNOUNCEMENT_QUERY, ANNOUNCEMENT_SOURCE,
    COMMENT_INDEX, COMMENT_QUERY, COMMENT_SOURCE,
)


def _search_single(index, query, fields, time_field, days, keyword):
    now = datetime.now()
    from_date = (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    q = json.loads(json.dumps(query))
    for c in q["query"]["bool"]["must"]:
        if "range" in c and time_field in c["range"]:
            c["range"][time_field]["gt"] = from_date
    should = []
    for f in ["content", "full_content"]:
        should.append({"match_phrase": {f: keyword}})
    q["query"]["bool"]["should"] = should
    q["query"]["bool"]["minimum_should_match"] = 1
    try:
        resp = es.search(index=index, body=q, _source=fields, size=20)
        return resp["hits"]["hits"]
    except Exception as e:
        return []


@tool
def search_financial_docs(keyword: str, doc_type: str = "all", top_n: int = 5) -> str:
    """搜索A股金融文档。doc_type: minutes(纪要)/report(研报)/announcement(公告)/comment(点评)/all(全部)。返回文档摘要。"""
    sources = []
    if doc_type in ("minutes", "all"):
        sources.append(("纪要", MINUTES_INDEX, MINUTES_QUERY, MINUTES_SOURCE, "publish_date", 90))
    if doc_type in ("report", "all"):
        sources.append(("研报", REPORT_INDEX, REPORT_QUERY, REPORT_SOURCE, "time", 90))
    if doc_type in ("announcement", "all"):
        sources.append(("公告", ANNOUNCEMENT_INDEX, ANNOUNCEMENT_QUERY, ANNOUNCEMENT_SOURCE, "end_date", 180))
    if doc_type in ("comment", "all"):
        sources.append(("点评", COMMENT_INDEX, COMMENT_QUERY, COMMENT_SOURCE, "time", 60))

    results = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(_search_single, idx, q, f, tf, tl, keyword): name
                   for name, idx, q, f, tf, tl in sources}
        for fut in futures:
            name = futures[fut]
            try:
                hits = fut.result()
                summaries = []
                for hit in hits[:top_n]:
                    src = hit.get("_source", {})
                    cf = "full_content" if "full_content" in src else "content"
                    c = src.get(cf, "") or ""
                    summaries.append({
                        "id": hit.get("_id", ""), "title": src.get("title", "无标题"),
                        "time": src.get("publish_date") or src.get("time") or src.get("end_date", ""),
                        "stock": str(src.get("stock") or src.get("sec", "未知")),
                        "snippet": (c if isinstance(c, str) else "")[:300],
                    })
                results[name] = summaries
            except Exception:
                results[name] = []

    lines = [f"搜索: '{keyword}'，共 {sum(len(v) for v in results.values())} 条"]
    for name, items in results.items():
        if items:
            lines.append(f"\n## {name} ({len(items)}条)")
            for i, d in enumerate(items, 1):
                lines.append(f"  {i}. [{d['id']}] {d['title']} | {d['stock']} | {d['time']}\n     {d['snippet'][:200]}")
    return "\n".join(lines)
