"""分析工具 — summarize + compare (LLM-driven)"""

from langchain_core.tools import tool


@tool
def summarize_findings(data: str, focus: str = "综合分析") -> str:
    """对金融数据做汇总分析，提炼核心观点。data=原始数据, focus=分析侧重点。注:此工具由LLM驱动。"""
    return (
        f"请基于以下数据进行分析，关注: {focus}\n\n"
        f"{data[:5000]}\n\n"
        "请输出: 1)核心发现(3-5条) 2)共识与分歧 3)不确定性"
    )


@tool
def compare_stocks(stocks_data: str, dimensions: str = "") -> str:
    """横向对比多只股票。stocks_data=股票数据, dimensions=对比维度(逗号分隔)。注:此工具由LLM驱动。"""
    dims = dimensions or "机构关注度,业绩表现,估值水平,市场情绪"
    return (
        f"请从以下维度对比: {dims}\n\n"
        f"{stocks_data[:5000]}\n\n"
        "请输出: 1)维度对比表 2)各股优劣 3)综合排序"
    )
