"""美股数据工具 — Yahoo Finance + SEC EDGAR"""

import json
import urllib.request
from langchain_core.tools import tool


@tool
def fetch_us_stock_info(ticker: str, info_type: str = "all") -> str:
    """获取美股信息: 实时行情+Yahoo Finance+SEC文件。ticker如AAPL/MSFT/NVDA。info_type: earnings/filings/analyst/news/all。"""
    ticker = ticker.upper().strip()
    results = []

    # Yahoo Finance
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=3mo"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
        if meta:
            results.append(f"【Yahoo Finance】{ticker} 最新:{meta.get('regularMarketPrice','N/A')} "
                           f"52W高:{meta.get('fiftyTwoWeekHigh','N/A')} 52W低:{meta.get('fiftyTwoWeekLow','N/A')}")
    except Exception as e:
        results.append(f"【Yahoo Finance】获取失败: {str(e)[:80]}")

    # SEC EDGAR
    if info_type in ("filings", "all"):
        results.append(f"【SEC EDGAR】https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}")

    if not results:
        return f"未找到 {ticker} 美股数据。建议用 UZI-Skill: run_uzi_analysis('{ticker}')"

    return "\n".join(results)
