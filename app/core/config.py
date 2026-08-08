"""企业级配置管理 — pydantic-settings，支持 .env + YAML"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ---- 应用 ----
    app_name: str = "financial-analysis-agent"
    app_version: str = "3.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # ---- LLM 提供商 ----
    llm_provider: str = "openai_compatible"
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"

    # ---- 备用模型 (Analyst/Writer 可独立配置) ----
    analyst_provider: str = ""
    analyst_model: str = ""
    writer_provider: str = ""
    writer_model: str = ""

    # ---- Elasticsearch ----
    es_host: str = "http://localhost:9201"
    es_user: str = ""
    es_password: str = ""

    # ---- 股票识别 API ----
    stock_matcher_url: str = "http://localhost:32230/wechat/stock_matcher"

    # ---- UZI-Skill ----
    uzi_enabled: bool = False
    uzi_path: str = "../UZI-Skill"

    # ---- 数据库 ----
    checkpoint_db_path: str = "data/checkpoints.db"

    # ---- 服务 ----
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
