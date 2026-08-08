"""股票识别工具"""

import json
import sys
import os
import requests
from langchain_core.tools import tool

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.api_config import STOCK_MATCHER_URL, STOCK_MATCHER_HEADERS


@tool
def identify_stocks(text: str) -> str:
    """从文本中识别A股/港股/美股代码和名称。"""
    if not text or not text.strip():
        return "文本为空"

    try:
        payload = json.dumps({"is_keep_vague": "1", "scope": "prd", "content": text[:1000]})
        resp = requests.post(STOCK_MATCHER_URL, headers=STOCK_MATCHER_HEADERS, data=payload, timeout=10)
        if resp.status_code == 200:
            stocks = resp.json().get("data", [])
            if stocks:
                return "\n".join(f"  - {s.get('stock_code','?')} {s.get('stock_name','')}" for s in stocks)
            return "未识别到股票"
        return f"API状态码: {resp.status_code}"
    except Exception as e:
        return f"识别失败: {str(e)}"
