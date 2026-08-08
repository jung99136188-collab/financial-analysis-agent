"""K线/技术数据工具 — A股+美股通用"""

from langchain_core.tools import tool


def _compute_ma(closes, period):
    if len(closes) < period:
        return [None] * len(closes)
    r = [None] * (period - 1)
    for i in range(period - 1, len(closes)):
        r.append(round(sum(closes[i - period + 1:i + 1]) / period, 2))
    return r


def _volume_profile(volumes, closes, bins=5):
    """成交量分布 — 判断资金在什么价位聚集"""
    if len(closes) < 20:
        return {}
    price_range = max(closes) - min(closes)
    if price_range == 0:
        return {}
    step = price_range / bins
    profile = {}
    for i in range(bins):
        low = min(closes) + i * step
        high = low + step
        vol_sum = 0
        for j, v in enumerate(volumes):
            if low <= closes[j] < high:
                vol_sum += v
        label = f"{low:.1f}-{high:.1f}"
        profile[label] = int(vol_sum)
    return profile


@tool
def fetch_kline_data(ticker: str, days: int = 120) -> str:
    """获取A股/美股/港股K线(含成交量分布和资金流信号)。
    A股:600519.SH / 美股:AAPL / 港股:00700.HK。
    返回OHLCV+MA5/20/60+成交量分布+资金流方向。需pip install yfinance。"""
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
            return f"未找到 {ticker} K线数据。格式: A股 600519.SH, 美股 AAPL, 港股 00700.HK"

        c = hist["Close"].tolist()
        h = hist["High"].tolist()
        l = hist["Low"].tolist()
        v = hist["Volume"].tolist()
        o = hist["Open"].tolist()
        dates = [str(d.date()) for d in hist.index]

        ma5 = _compute_ma(c, 5)
        ma20 = _compute_ma(c, 20)
        ma60 = _compute_ma(c, 60)
        m5, m20, m60 = ma5[-1] if ma5[-1] else None, ma20[-1] if ma20[-1] else None, ma60[-1] if ma60[-1] else None

        if m5 and m20 and m60:
            if m5 > m20 > m60: align = "多头排列 ↗"
            elif m5 < m20 < m60: align = "空头排列 ↘"
            else: align = "交织震荡 ↔"
        else: align = "数据不足"

        # ---- 量价关系 ----
        avg_vol20 = round(sum(v[-21:]) / min(len(v[-21:]), 20), 0) if len(v) >= 20 else round(sum(v) / len(v), 0)
        vol_ratio = round(v[-1] / avg_vol20, 2) if avg_vol20 > 0 else 1
        if vol_ratio > 2.0: vol_sig = "巨量⚠️"
        elif vol_ratio > 1.5: vol_sig = "放量"
        elif vol_ratio < 0.5: vol_sig = "地量"
        else: vol_sig = "量平"

        # ---- 资金流方向 ----
        up_days = down_days = 0
        up_vol = down_vol = 0
        for i in range(-20, 0):
            if i >= -len(c):
                if c[i] > o[i]:
                    up_days += 1; up_vol += v[i]
                else:
                    down_days += 1; down_vol += v[i]
        net_flow_ratio = round((up_vol - down_vol) / (up_vol + down_vol + 1), 2)
        if net_flow_ratio > 0.2: flow_dir = "资金净流入(买方主导)"
        elif net_flow_ratio < -0.2: flow_dir = "资金净流出(卖方主导)"
        else: flow_dir = "资金博弈均衡"

        # ---- 成交量分布 ----
        vol_profile = _volume_profile(v, c)

        # ---- 价格统计 ----
        chg5 = round((c[-1]/c[-6]-1)*100, 2) if len(c)>=6 else "N/A"
        chg20 = round((c[-1]/c[-21]-1)*100, 2) if len(c)>=21 else "N/A"
        h60 = round(max(h[-60:]), 2) if len(h)>=60 else round(max(h),2)
        l60 = round(min(l[-60:]), 2) if len(l)>=60 else round(min(l),2)

        # ---- 最近10日 ----
        recent = []
        for i in range(max(0, len(dates)-10), len(dates)):
            recent.append(f"{dates[i]} | {round(o[i],2)}→{round(c[i],2)} "
                          f"H:{round(h[i],2)} L:{round(l[i],2)} V:{int(v[i]):,}")

        # ---- 量价背离检测 ----
        div_signal = ""
        if len(c) >= 20:
            price_up = c[-1] > c[-20]
            vol_up = sum(v[-5:]) > sum(v[-25:-20])
            if price_up and not vol_up: div_signal = "\n⚠️ 量价背离: 价格上行但量能萎缩，上涨动力减弱"
            elif not price_up and vol_up: div_signal = "\n💡 量价背离: 价格下行但量能放大，可能接近底部"

        return (f"【{ticker}】{days}天K线\n\n"
                f"## 价格\n"
                f"最新:{c[-1]} | 60日高:{h60} | 60日低:{l60}\n"
                f"5日涨跌:{chg5}% | 20日涨跌:{chg20}%\n\n"
                f"## 均线\n"
                f"MA5:{m5} MA20:{m20} MA60:{m60}\n排列:{align}\n\n"
                f"## 量能\n"
                f"最新量:{int(v[-1]):,} | 20日均量:{int(avg_vol20):,}\n"
                f"量比:{vol_ratio}({vol_sig})\n\n"
                f"## 资金流(20日)\n"
                f"阳线:{up_days}天(量{int(up_vol):,}) | 阴线:{down_days}天(量{int(down_vol):,})\n"
                f"净流比:{net_flow_ratio} → {flow_dir}{div_signal}\n\n"
                f"## 成交量分布\n" +
                "\n".join(f"  {k}: {v:>12,}" for k, v in vol_profile.items()) +
                f"\n\n## 最近10日\n" + "\n".join(f"  {r}" for r in recent))
    except Exception as e:
        return f"K线获取失败: {str(e)[:200]}"
