"""LangChain Tools — 金融分析工具集"""

from app.tools.es_search import search_financial_docs
from app.tools.kline import fetch_kline_data
from app.tools.us_stocks import fetch_us_stock_info
from app.tools.stock_id import identify_stocks
from app.tools.uzi import run_uzi_analysis
from app.tools.analyze import summarize_findings, compare_stocks

ALL_TOOLS = [
    search_financial_docs,
    fetch_kline_data,
    fetch_us_stock_info,
    identify_stocks,
    run_uzi_analysis,
    summarize_findings,
    compare_stocks,
]
