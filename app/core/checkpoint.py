"""LangGraph Checkpointer — SQLite 持久化"""

import os
from langgraph.checkpoint.sqlite import SqliteSaver
from app.core.config import settings


def get_checkpointer() -> SqliteSaver:
    """创建 SQLite checkpointer"""
    db_path = settings.checkpoint_db_path
    os.makedirs(os.path.dirname(db_path) or "data", exist_ok=True)
    conn_string = db_path if db_path.endswith(".db") else f"{db_path}?check_same_thread=False"
    return SqliteSaver.from_conn_string(conn_string)


checkpointer = get_checkpointer()
