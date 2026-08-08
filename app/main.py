"""
金融分析多 Agent 系统 — 企业版入口

Usage:
    python app/main.py                    # FastAPI 服务 (默认)
    python app/main.py --cli              # CLI 交互模式 (兼容旧版)
    python app/main.py --cli --pipeline   # Pipeline 快速模式
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def start_api(host: str = "0.0.0.0", port: int = 8000):
    """启动 FastAPI 服务"""
    import uvicorn
    from app.core.config import settings
    from app.core.logging import setup_logging
    setup_logging()
    print(f"\n{'='*60}")
    print(f"  {settings.app_name} v{settings.app_version}")
    print(f"  LangGraph + FastAPI 企业版")
    print(f"  Swagger: http://{host}:{port}/docs")
    print(f"  Health:  http://{host}:{port}/health")
    print(f"{'='*60}\n")
    uvicorn.run("app.api.routes:router", host=host, port=port, reload=settings.debug)


def start_cli(pipeline_mode: bool = False):
    """CLI 交互模式"""
    if pipeline_mode:
        # 旧 Pipeline 模式
        from app.main import pipeline_chat
        pipeline_chat()
    else:
        # LangGraph Agent 模式
        from langchain_core.messages import HumanMessage
        from app.graph import get_graph
        from app.core.config import settings

        graph = get_graph()
        print(f"\n{'='*60}")
        print(f"  {settings.app_name} v{settings.app_version} — LangGraph Agent")
        print(f"  输入 '退出' 结束 | 输入 '切换' 切换 Pipeline 模式")
        print(f"{'='*60}\n")

        thread_id = "cli-1"
        while True:
            try:
                q = input("🧠 > ")
                if q.lower() in ["退出", "exit", "quit"]:
                    break
                if q.lower() in ["切换", "switch"]:
                    start_cli(pipeline_mode=True)
                    continue
                if not q.strip():
                    continue

                print()
                config = {"configurable": {"thread_id": thread_id}}
                result = graph.invoke(
                    {"messages": [HumanMessage(content=q)], "deep_mode": False, "error_count": 0},
                    config,
                )

                # 提取最佳响应
                output = (result.get("final_report")
                          or result.get("analysis_result")
                          or result.get("research_data")
                          or "")
                if not output:
                    for m in reversed(result.get("messages", [])):
                        if hasattr(m, "content") and m.content and m.type == "ai":
                            output = m.content
                            break

                print(f"\n{'='*60}")
                print(output or "分析完成")
                print(f"{'='*60}\n")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"错误: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="金融分析多Agent系统")
    parser.add_argument("--cli", action="store_true", help="CLI 交互模式")
    parser.add_argument("--pipeline", action="store_true", help="Pipeline 快速模式 (需 --cli)")
    parser.add_argument("--host", default="0.0.0.0", help="API 监听地址")
    parser.add_argument("--port", type=int, default=8000, help="API 端口")

    args = parser.parse_args()

    if args.cli:
        start_cli(pipeline_mode=args.pipeline)
    else:
        start_api(host=args.host, port=args.port)
