"""美股工具 — 行情 + 机构持仓 + 卖空 + SEC"""

import json
import urllib.request
from langchain_core.tools import tool


@tool
def fetch_us_stock_info(ticker: str, info_type: str = "all") -> str:
    """美股综合信息: 实时行情+机构持仓+卖空数据+SEC文件。
    ticker: AAPL/MSFT/NVDA。info_type: quote/holdings/short/filings/all。"""
    ticker = ticker.upper().strip()
    results = []

    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        # ---- 实时行情 ----
        if info_type in ("quote", "all") and info:
            results.append(
                f"【行情】{info.get('longName', ticker)}\n"
                f"  最新价: ${info.get('currentPrice') or info.get('regularMarketPrice', 'N/A')}\n"
                f"  市值: ${_fmt(info.get('marketCap'))} | "
                f"PE: {info.get('trailingPE', 'N/A')} | "
                f"EPS: {info.get('trailingEps', 'N/A')}\n"
                f"  52周高: ${info.get('fiftyTwoWeekHigh', 'N/A')} | "
                f"52周低: ${info.get('fiftyTwoWeekLow', 'N/A')}\n"
                f"  贝塔: {info.get('beta', 'N/A')} | "
                f"股息率: {info.get('dividendYield', 'N/A')}"
            )

        # ---- 机构持仓 ----
        if info_type in ("holdings", "all"):
            inst_pct = info.get('heldPercentInstitutions')
            insider_pct = info.get('heldPercentInsiders')
            if inst_pct or insider_pct:
                results.append(
                    f"【持仓结构】\n"
                    f"  机构持股: {f'{inst_pct*100:.1f}%' if inst_pct else 'N/A'}\n"
                    f"  内部人持股: {f'{insider_pct*100:.1f}%' if insider_pct else 'N/A'}"
                )
            # Top institutional holders
            try:
                holders = stock.institutional_holders
                if holders is not None and not holders.empty:
                    top3 = holders.head(3)
                    lines = ["【Top机构持仓】"]
                    for _, row in top3.iterrows():
                        name = str(row.get('Holder', ''))[:30]
                        shares = _fmt(row.get('Shares', 0))
                        pct = row.get('% Out', 0)
                        lines.append(f"  {name}: {shares}股 ({pct*100:.1f}%)" if isinstance(pct, float) else f"  {name}: {shares}股")
                    results.append("\n".join(lines))
            except Exception:
                pass

        # ---- 卖空数据 ----
        if info_type in ("short", "all"):
            short_ratio = info.get('shortRatio')
            short_pct = info.get('shortPercentOfFloat')
            if short_ratio or short_pct:
                results.append(
                    f"【卖空数据】\n"
                    f"  卖空比例: {f'{short_pct*100:.1f}%' if short_pct else 'N/A'} of float\n"
                    f"  回补天数: {short_ratio}天" if short_ratio else ""
                )

    except ImportError:
        results.append("【提示】安装 yfinance 获取更详细数据: pip install yfinance")
    except Exception as e:
        results.append(f"【Yahoo】获取失败: {str(e)[:100]}")

    # ---- SEC EDGAR ----
    if info_type in ("filings", "all"):
        results.append(f"【SEC】https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}")

    if not results:
        return f"未找到 {ticker} 数据"
    return "\n\n".join(results)


def _fmt(n):
    """格式化大数"""
    if n is None:
        return "N/A"
    n = float(n)
    if abs(n) >= 1e12: return f"{n/1e12:.2f}T"
    if abs(n) >= 1e9:  return f"{n/1e9:.2f}B"
    if abs(n) >= 1e6:  return f"{n/1e6:.2f}M"
    return f"{n:,.0f}"
