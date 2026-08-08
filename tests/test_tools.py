"""工具单元测试"""

import pytest
from app.tools import search_financial_docs, fetch_kline_data, identify_stocks


def test_search_docs_definition():
    """验证搜索工具定义正确"""
    assert search_financial_docs.name == "search_financial_docs"
    assert "keyword" in search_financial_docs.args_schema.model_fields


def test_kline_definition():
    """验证K线工具定义正确"""
    assert fetch_kline_data.name == "fetch_kline_data"
    assert "ticker" in fetch_kline_data.args_schema.model_fields
    assert "days" in fetch_kline_data.args_schema.model_fields


def test_identify_stocks_definition():
    """验证股票识别工具定义正确"""
    assert identify_stocks.name == "identify_stocks"
    assert "text" in identify_stocks.args_schema.model_fields


def test_all_tools_unique():
    """验证工具名不重复"""
    from app.tools import ALL_TOOLS
    names = [t.name for t in ALL_TOOLS]
    assert len(names) == len(set(names)), f"Duplicate tool names: {names}"
