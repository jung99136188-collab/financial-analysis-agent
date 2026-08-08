"""
Research Agent — 金融信息搜索专家（A股 + 美股）

工具：
    - search_financial_docs: 搜索金融文档（纪要/研报/公告/点评 + 美股）
    - identify_stocks_in_text: 从文本识别股票
    - fetch_us_stock_info: 获取美股财报/会议/新闻
"""

import json
import sys
import os
import re
import requests
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

# 美股数据索引（可选，如果 ES 集群有的话）
try:
    from config.es_config import (
        US_EARNINGS_INDEX, US_EARNINGS_QUERY, US_EARNINGS_SOURCE,
        US_FILINGS_INDEX, US_FILINGS_QUERY, US_FILINGS_SOURCE,
        US_ANALYST_INDEX, US_ANALYST_QUERY, US_ANALYST_SOURCE,
    )
    _US_INDICES_LOADED = True
except ImportError:
    _US_INDICES_LOADED = False

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
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_kline_data",
            "description": (
                "获取股票K线/盘面数据。返回最近N个交易日的OHLCV（开高低收量）数据、"
                "均线(MA5/MA10/MA20/MA60)、MACD、RSI、布林带等常用技术指标。"
                "A股用 600519.SH 格式，美股用 AAPL 格式，港股用 00700.HK 格式。"
                "返回结构化数据供后续技术面分析。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "股票代码: A股 600519.SH, 美股 AAPL, 港股 00700.HK"
                    },
                    "days": {
                        "type": "integer",
                        "description": "获取最近多少天的数据，默认120，最大365"
                    }
                },
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_us_stock_info",
            "description": (
                "获取美股信息：财报数据、盈利电话会议纪要、SEC文件、分析师评级、重大新闻。"
                "支持查找 earnings call、10-K/10-Q、analyst upgrades/downgrades、conference presentations。"
                "ticker 格式: AAPL / MSFT / NVDA 等。"
                "ES有美股索引时从ES查，否则通过公开API获取。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "美股代码，如 AAPL、MSFT、NVDA、TSLA"
                    },
                    "info_type": {
                        "type": "string",
                        "enum": ["earnings", "filings", "analyst", "news", "all"],
                        "description": "信息类型: earnings=财报/电话会, filings=SEC文件, analyst=分析师评级, news=新闻, all=全部"
                    }
                },
                "required": ["ticker"]
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
    """搜索金融文档的实现（A股 + 美股）"""
    sources = []

    # A股数据源
    if doc_type in ("minutes", "all"):
        sources.append(("纪要(A股)", MINUTES_INDEX, MINUTES_QUERY, MINUTES_SOURCE, "publish_date", 90))
    if doc_type in ("report", "all"):
        sources.append(("研报(A股)", REPORT_INDEX, REPORT_QUERY, REPORT_SOURCE, "time", 90))
    if doc_type in ("announcement", "all"):
        sources.append(("公告(A股)", ANNOUNCEMENT_INDEX, ANNOUNCEMENT_QUERY, ANNOUNCEMENT_SOURCE, "end_date", 180))
    if doc_type in ("comment", "all"):
        sources.append(("点评(A股)", COMMENT_INDEX, COMMENT_QUERY, COMMENT_SOURCE, "time", 60))

    # 美股数据源（如果ES集群有）
    if _US_INDICES_LOADED:
        if doc_type in ("earnings", "all"):
            try:
                sources.append(("财报(美股)", US_EARNINGS_INDEX, US_EARNINGS_QUERY, US_EARNINGS_SOURCE, "report_date", 180))
            except NameError:
                pass
        if doc_type in ("filings", "all"):
            try:
                sources.append(("SEC文件(美股)", US_FILINGS_INDEX, US_FILINGS_QUERY, US_FILINGS_SOURCE, "filing_date", 180))
            except NameError:
                pass
        if doc_type in ("analyst", "all"):
            try:
                sources.append(("分析师(美股)", US_ANALYST_INDEX, US_ANALYST_QUERY, US_ANALYST_SOURCE, "date", 180))
            except NameError:
                pass

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


def _clean_html(raw):
    """简单去除 HTML 标签"""
    return re.sub(r'<[^>]+>', '', raw) if raw else ""


def _fetch_us_stock_info_impl(ticker, info_type="all"):
    """获取美股信息（ES + 公开API 双通道）"""
    results = []
    ticker = ticker.upper().strip()

    # ---- 通道1: ES 美股索引 ----
    if _US_INDICES_LOADED:
        es_results = _search_financial_docs_impl(keyword=ticker, doc_type=info_type, top_n=5)
        if "共找到" in es_results and "共找到 0 条" not in es_results:
            results.append(f"【ES美股索引】\n{es_results}")

    # ---- 通道2: 公开 API (Yahoo Finance 非官方接口) ----
    try:
        import urllib.request
        # 尝试获取公司基本信息
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=3mo"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            chart_data = json.loads(resp.read())
        meta = chart_data.get("chart", {}).get("result", [{}])[0].get("meta", {})
        if meta:
            results.append(
                f"【Yahoo Finance】{ticker}\n"
                f"  最新价: ${meta.get('regularMarketPrice', 'N/A')}\n"
                f"  52周高: ${meta.get('fiftyTwoWeekHigh', 'N/A')} | "
                f"52周低: ${meta.get('fiftyTwoWeekLow', 'N/A')}\n"
                f"  前收盘: ${meta.get('previousClose', 'N/A')}"
            )
    except Exception as e:
        results.append(f"【Yahoo Finance】无法获取 {ticker} 行情: {str(e)[:100]}")

    # ---- 通道3: SEC EDGAR 最近文件 ----
    if info_type in ("filings", "all"):
        try:
            import urllib.request
            cik_url = f"https://efts.sec.gov/LATEST/search-index?q={ticker}&categories=form-cat1&dateRange=custom&startdt=2024-01-01&enddt=2026-12-31"
            req = urllib.request.Request(cik_url, headers={"User-Agent": "financial-agent/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                # 如果请求成功，解析最近的文件
                pass
            results.append(f"【SEC EDGAR】访问 https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&type=&dateb=&owner=exclude&count=20")
        except Exception:
            results.append(f"【SEC EDGAR】建议访问: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}")

    if not results:
        return (
            f"未找到 {ticker} 的美股数据。建议:\n"
            f"1. 确认ES美股索引已配置 (config/es_config.py)\n"
            f"2. 用 UZI-Skill 分析: run_uzi_analysis('{ticker}', depth='medium')\n"
            f"3. 手动查阅: Yahoo Finance / SEC EDGAR / Seeking Alpha"
        )

    return "\n\n".join(results)


def _compute_ma(closes, period):
    """计算移动均线"""
    if len(closes) < period:
        return [None] * len(closes)
    result = [None] * (period - 1)
    for i in range(period - 1, len(closes)):
        result.append(round(sum(closes[i - period + 1:i + 1]) / period, 2))
    return result


def _fetch_kline_data_impl(ticker, days=120):
    """获取K线数据 + 计算技术指标"""
    ticker = ticker.strip()
    days = min(days, 365)

    try:
        # 尝试 yfinance（美股/港股通用）
        import yfinance as yf
    except ImportError:
        return (
            "需要安装 yfinance 来获取K线数据:\n"
            "pip install yfinance\n\n"
            "A股替代方案: pip install akshare\n"
            f"或手动查看: https://finance.sina.com.cn/realstock/company/{ticker}/nc.shtml"
        )

    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=f"{days}d")

        if hist.empty:
            return f"未找到 {ticker} 的K线数据，请检查代码是否正确。\nA股格式: 600519.SH\n美股格式: AAPL\n港股格式: 00700.HK"

        closes = hist["Close"].tolist()
        highs = hist["High"].tolist()
        lows = hist["Low"].tolist()
        volumes = hist["Volume"].tolist()
        dates = [str(d.date()) for d in hist.index]

        # 计算技术指标
        ma5 = _compute_ma(closes, 5)
        ma20 = _compute_ma(closes, 20)
        ma60 = _compute_ma(closes, 60)

        # 最近交易日的关键数据
        last_close = closes[-1]
        last_vol = volumes[-1]
        ma5_val = ma5[-1] if ma5[-1] else "N/A"
        ma20_val = ma20[-1] if ma20[-1] else "N/A"
        ma60_val = ma60[-1] if ma60[-1] else "N/A"

        # 价格变化
        change_5d = round((closes[-1] / closes[-6] - 1) * 100, 2) if len(closes) >= 6 else "N/A"
        change_20d = round((closes[-1] / closes[-21] - 1) * 100, 2) if len(closes) >= 21 else "N/A"
        high_60d = round(max(highs[-60:]), 2) if len(highs) >= 60 else round(max(highs), 2)
        low_60d = round(min(lows[-60:]), 2) if len(lows) >= 60 else round(min(lows), 2)

        # 均线排列判断
        if ma5_val != "N/A" and ma20_val != "N/A" and ma60_val != "N/A":
            if ma5_val > ma20_val > ma60_val:
                alignment = "多头排列（短期>中期>长期，上升趋势）"
            elif ma5_val < ma20_val < ma60_val:
                alignment = "空头排列（短期<中期<长期，下降趋势）"
            else:
                alignment = "均线交织（震荡整理）"
        else:
            alignment = "数据不足"

        # 量价关系
        avg_vol_20 = round(sum(volumes[-21:]) / min(len(volumes[-21:]), 20), 0) if len(volumes) >= 20 else round(sum(volumes) / len(volumes), 0)
        vol_ratio = round(last_vol / avg_vol_20, 2) if avg_vol_20 > 0 else 1
        vol_desc = "放量" if vol_ratio > 1.5 else ("缩量" if vol_ratio < 0.5 else "量平")

        # 最近10日数据表
        recent = []
        for i in range(max(0, len(dates) - 10), len(dates)):
            recent.append(
                f"{dates[i]} | O:{round(hist['Open'].iloc[i],2)} | "
                f"H:{round(highs[i],2)} | L:{round(lows[i],2)} | "
                f"C:{round(closes[i],2)} | V:{int(volumes[i]):,}"
            )

        return (
            f"【{ticker} K线数据】最近 {days} 天\n\n"
            f"## 关键价格\n"
            f"  最新收盘: {last_close}\n"
            f"  60日最高:  {high_60d}\n"
            f"  60日最低:  {low_60d}\n"
            f"  5日涨跌:  {change_5d}%\n"
            f"  20日涨跌: {change_20d}%\n\n"
            f"## 均线系统\n"
            f"  MA5:  {ma5_val}\n"
            f"  MA20: {ma20_val}\n"
            f"  MA60: {ma60_val}\n"
            f"  排列: {alignment}\n\n"
            f"## 成交量\n"
            f"  最新量:  {int(last_vol):,}\n"
            f"  20日均量: {int(avg_vol_20):,}\n"
            f"  量比:    {vol_ratio} ({vol_desc})\n\n"
            f"## 最近10日OHLCV\n"
            f"  {' | '.join(['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])}\n"
            + "\n".join(f"  {r}" for r in recent)
        )

    except Exception as e:
        return f"获取 {ticker} K线数据失败: {str(e)[:200]}"


# ============================================================
# ResearcherAgent
# ============================================================

class ResearcherAgent(BaseAgent):
    """金融信息研究 Agent（A股 + 美股）"""

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
            "fetch_kline_data": lambda args: _fetch_kline_data_impl(
                ticker=args.get("ticker", ""),
                days=args.get("days", 120),
            ),
            "fetch_us_stock_info": lambda args: _fetch_us_stock_info_impl(
                ticker=args.get("ticker", ""),
                info_type=args.get("info_type", "all"),
            ),
        }
        super().__init__(
            name="Researcher",
            system_prompt=RESEARCHER_SYSTEM_PROMPT,
            tools=RESEARCHER_TOOLS,
            llm_client=llm_client,
            tool_handlers=tool_handlers,
        )
