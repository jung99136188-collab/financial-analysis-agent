"""
API 配置模板 — 复制此文件为 api_config.py 并填入真实密钥

注意: api_config.py 已在 .gitignore 中排除，不会被上传到 GitHub。
"""

# ============================================================
# DeepSeek API (火山引擎)
# ============================================================
API_KEY_VOLCENGINE = "your-volcengine-api-key-here"
BASE_URL_VOLCENGINE = "https://ark.cn-beijing.volces.com/api/v3"
DEEPSEEK_R1_ENDPOINT = "ep-xxxxxxxxxxxxxxxx"  # R1 深度推理
DEEPSEEK_V3_ENDPOINT = "ep-xxxxxxxxxxxxxxxx"  # V3 快速推理

# ============================================================
# OpenAI API (用于问题分析，可选)
# ============================================================
OPENAI_BASE_URL = "https://api.openai.com/v1/"
OPENAI_API_KEY = "sk-your-openai-api-key-here"

# ============================================================
# 股票识别 API (内部服务)
# ============================================================
STOCK_MATCHER_URL = "http://your-server:port/wechat/stock_matcher"
STOCK_MATCHER_HEADERS = {
    "Content-Type": "application/json"
}

# ============================================================
# 重试配置
# ============================================================
MAX_RETRIES = 3
RETRY_DELAY = 2
