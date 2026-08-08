"""K线/技术数据工具"""

from langchain_core.tools import tool


def _compute_ma(closes, period):
    if len(closes) < period:
        return [None] * len(closes)
    r = [None] * (period - 1)
    for i in range(period - 1, len(closes)):
        r.append(round(sum(closes[i - period + 1:i + 1]) / period, 2))
    return r


@tool
def fetch_kline_data(ticker: str, days: int = 120) -> str:
    """获取股票K线数据(OHLCV)+均线+量比。A股:600519.SH 美股:AAPL 港股:00700.HK。需pip install yfinance。"""
    ticker = ticker.strip()
    days = min(days, 365)
    try:
        import yfinance as yf
    except ImportError:
        return "需要安装 yfinance: pip install yfinance"

    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=f"{days}d")
        if hist.empty:
            return f"未找到 {ticker} K线数据，检查代码格式"

        c = hist["Close"].tolist()
        h = hist["High"].tolist()
        l = hist["Low"].tolist()
        v = hist["Volume"].tolist()
        dates = [str(d.date()) for d in hist.index]

        ma5 = _compute_ma(c, 5)
        ma20 = _compute_ma(c, 20)
        ma60 = _compute_ma(c, 60)

        m5, m20, m60 = ma5[-1], ma20[-1], ma60[-1]
        if m5 and m20 and m60:
            if m5 > m20 > m60:
                align = "多头排列"
            elif m5 < m20 < m60:
                align = "空头排列"
            else:
                align = "交织震荡"
        else:
            align = "数据不足"

        avg_vol = round(sum(v[-21:]) / min(len(v[-21:]), 20), 0) if len(v) >= 20 else round(sum(v) / len(v), 0)
        ratio = round(v[-1] / avg_vol, 2) if avg_vol > 0 else 1
        vol_desc = "放量" if ratio > 1.5 else ("缩量" if ratio < 0.5 else "量平")

        recent = []
        for i in range(max(0, len(dates) - 10), len(dates)):
            recent.append(f"{dates[i]} O:{round(hist['Open'].iloc[i],2)} H:{round(h[i],2)} "
                          f"L:{round(l[i],2)} C:{round(c[i],2)} V:{int(v[i]):,}")

        chg5 = round((c[-1]/c[-6]-1)*100, 2) if len(c) >= 6 else "N/A"
        chg20 = round((c[-1]/c[-21]-1)*100, 2) if len(c) >= 21 else "N/A"
        h60 = round(max(h[-60:]), 2) if len(h) >= 60 else round(max(h), 2)
        l60 = round(min(l[-60:]), 2) if len(l) >= 60 else round(min(l), 2)

        return (f"【{ticker}】{days}天\n"
                f"收盘:{c[-1]} 60日高:{h60} 60日低:{l60} 5日:{chg5}% 20日:{chg20}%\n"
                f"MA5:{m5} MA20:{m20} MA60:{m60} 排列:{align}\n"
                f"量:{int(v[-1]):,} 均量:{int(avg_vol):,} 量比:{ratio}({vol_desc})\n"
                f"最近10日:\n" + "\n".join(f"  {r}" for r in recent))
    except Exception as e:
        return f"K线获取失败: {str(e)[:200]}"
