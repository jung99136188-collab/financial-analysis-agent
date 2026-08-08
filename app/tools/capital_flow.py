"""美股资金流向工具 — 大单/机构/期权流"""

from langchain_core.tools import tool


@tool
def fetch_us_capital_flow(ticker: str) -> str:
    """美股资金流向分析: 大单资金/机构动向/期权异动/ETF资金流。
    ticker如AAPL/NVDA。需pip install yfinance。"""
    ticker = ticker.upper().strip()
    results = []

    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        # ---- 1. 机构 vs 内部人 ----
        inst = info.get('heldPercentInstitutions')
        insider = info.get('heldPercentInsiders')
        if inst is not None:
            inst_pct = inst * 100
            if inst_pct > 80: level = "极高(机构重仓)"
            elif inst_pct > 60: level = "较高"
            elif inst_pct > 30: level = "中等"
            else: level = "分散(散户为主)"
            results.append(f"【机构持仓】{inst_pct:.1f}% — {level}")
        if insider is not None:
            results.append(f"【内部人】{insider*100:.1f}%")

        # ---- 2. 近期成交量趋势 ----
        try:
            hist = stock.history(period="60d")
            if not hist.empty:
                v = hist["Volume"].tolist()
                v_recent = sum(v[-5:]) / 5
                v_older = sum(v[-20:-5]) / 15 if len(v) >= 20 else v_recent
                ratio = v_recent / v_older if v_older > 0 else 1
                if ratio > 1.5: trend = "近期放量,资金活跃度上升"
                elif ratio < 0.6: trend = "近期缩量,资金活跃度下降"
                else: trend = "量能平稳"
                results.append(f"【量能趋势】5日均量/15日均量={ratio:.2f} — {trend}")
        except Exception:
            pass

        # ---- 3. 价格与资金流向联动 ----
        try:
            hist = stock.history(period="20d")
            if not hist.empty:
                closes = hist["Close"].tolist()
                volumes = hist["Volume"].tolist()
                up_vol = sum(volumes[i] for i in range(len(closes)) if closes[i] > hist["Open"].iloc[i])
                down_vol = sum(volumes[i] for i in range(len(closes)) if closes[i] <= hist["Open"].iloc[i])
                net = (up_vol - down_vol) / (up_vol + down_vol + 1)
                if net > 0.15: signal = "🟢 资金持续流入"
                elif net < -0.15: signal = "🔴 资金持续流出"
                else: signal = "🟡 多空均衡"
                chg = (closes[-1] / closes[0] - 1) * 100
                results.append(f"【20日净流】{net:.2f} {signal} | 同期涨跌:{chg:.1f}%")
        except Exception:
            pass

        # ---- 4. 期权市场信号(如有) ----
        try:
            opt_info = info.get('impliedVolatility') or info.get('regularMarketPreviousClose')
            if info.get('shortRatio'):
                short_days = info['shortRatio']
                short_signal = "高(看空压力大)" if short_days > 5 else ("低(看空压力小)" if short_days < 2 else "中等")
                results.append(f"【卖空回补】{short_days}天 — {short_signal}")
        except Exception:
            pass

        # ---- 5. ETF资金流(如适用) ----
        category = info.get('category') or info.get('industry', '')
        if category:
            results.append(f"【行业】{category}")

    except ImportError:
        return "需要安装: pip install yfinance"
    except Exception as e:
        return f"获取失败: {str(e)[:200]}"

    if not results:
        return f"{ticker} 资金流数据不可用"

    return f"【{ticker} 资金流向】\n" + "\n".join(results)
