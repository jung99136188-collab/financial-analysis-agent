import sys
import os
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import os.path

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.es_config import (
    MINUTES_INDEX, MINUTES_QUERY, MINUTES_SOURCE,
    REPORT_INDEX, REPORT_QUERY, REPORT_SOURCE,
    ANNOUNCEMENT_INDEX, ANNOUNCEMENT_QUERY, ANNOUNCEMENT_SOURCE,
    COMMENT_INDEX, COMMENT_QUERY, COMMENT_SOURCE
)

from app.utils import (
    analyze_question,
    query_elasticsearch,
    extract_relevant_content,
    filter_by_stocks,
    rerank_by_relevance,
    group_by_stock_and_type,
    generate_final_report
)

def process_question(question):
    """处理用户问题并生成报告"""
    print(f"收到用户问题: {question}")
    
    # 第一步：分析问题，提取关键词和概念
    analysis_result = analyze_question(question)
    keywords = analysis_result.get("keywords", [])
    concept_keywords = analysis_result.get("concept", [])
    
    # 如果keywords是字符串，转换为列表
    if isinstance(keywords, str):
        keywords = [keywords]
    
    # 如果concept是字符串，转换为列表
    if isinstance(concept_keywords, str):
        concept_keywords = [concept_keywords]
    
    # 合并关键词列表
    all_keywords = keywords + concept_keywords
    
    if not all_keywords:
        return "无法从问题中提取关键词，请提供更具体的问题。"
    
    print(f"提取的关键词: {all_keywords}")

    # 第二步：查询ES获取相关内容
    def query_minutes():
        return query_elasticsearch(
            MINUTES_INDEX, MINUTES_QUERY, MINUTES_SOURCE, "publish_date", 90, all_keywords
        )
    
    def query_comments():
        return query_elasticsearch(
            COMMENT_INDEX, COMMENT_QUERY, COMMENT_SOURCE, "time", 60, all_keywords
        )
    
    def query_announcements():
        return query_elasticsearch(
            ANNOUNCEMENT_INDEX, ANNOUNCEMENT_QUERY, ANNOUNCEMENT_SOURCE, "end_date", 180, all_keywords
        )
    
    def query_reports():
        return query_elasticsearch(
            REPORT_INDEX, REPORT_QUERY, REPORT_SOURCE, "time", 90, all_keywords
        )
    
    # 使用线程池并发查询
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [
            executor.submit(query_minutes),
            executor.submit(query_comments),
            executor.submit(query_announcements),
            executor.submit(query_reports)
        ]
        
        minutes_results = futures[0].result()
        comments_results = futures[1].result()
        announcements_results = futures[2].result()
        reports_results = futures[3].result()
    
    # 从结果中提取相关内容（同时识别股票）
    minutes_content = extract_relevant_content(minutes_results, all_keywords, "content")
    comments_content = extract_relevant_content(comments_results, all_keywords, "content")
    announcements_content = extract_relevant_content(announcements_results, all_keywords, "content")
    reports_content = extract_relevant_content(reports_results, all_keywords, "full_content")
    
    # 为每种类型的内容添加来源标识
    for item in minutes_content:
        item["es_source"] = "roadshow_summary"
    
    for item in comments_content:
        item["es_source"] = "comment"
    
    for item in announcements_content:
        item["es_source"] = "announcement"
    
    for item in reports_content:
        item["es_source"] = "report"
    
    # 记录各源的内容数量
    print(f"纪要内容数量: {len(minutes_content)}")
    print(f"点评内容数量: {len(comments_content)}")
    print(f"公告内容数量: {len(announcements_content)}")
    print(f"研报内容数量: {len(reports_content)}")
    
    # 合并所有内容（每个内容项都已包含股票信息）
    all_contents = minutes_content + comments_content + announcements_content + reports_content
    
    if not all_contents:
        return "未找到与关键词相关且包含股票的内容，请尝试其他关键词。"
    
    print(f"可用的内容总数: {len(all_contents)}")
    
    # 将all_contents输出到txt文件
    output_dir = "output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_path = os.path.join(output_dir, f"所有内容_{timestamp}.txt")
    
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(f"内容总数: {len(all_contents)}\n\n")
        for i, item in enumerate(all_contents):
            f.write(f"--- 文档 {i+1} ---\n")
            f.write(f"ID: {item.get('_id', '无ID')}\n")
            f.write(f"标题: {item.get('title', '无标题')}\n")
            f.write(f"股票: {item.get('stock', '无股票')}\n")
            f.write(f"来源: {item.get('es_source', '未知来源')}\n")
            f.write(f"时间: {item.get('time', item.get('publish_date', item.get('end_date', '无时间')))}\n")
            f.write(f"内容摘要: {item.get('content', item.get('full_content', ''))[:200]}...\n")
            f.write("\n-------------------\n\n")
    
    print(f"所有内容已输出到: {txt_path}")
    
    # 按股票分组
    contents_by_stock = {}
    for item in all_contents:
        try:
            stock = item.get("stock", "unknown")
            # 确保stock是字符串
            if isinstance(stock, list):
                if len(stock) > 0:
                    stock = str(stock[0])
                else:
                    stock = "unknown"
            else:
                stock = str(stock)
                
            if stock not in contents_by_stock:
                contents_by_stock[stock] = []
            contents_by_stock[stock].append(item)
        except Exception as e:
            print(f"股票分组错误: {str(e)}")
            continue
    
    print(f"相关股票数量: {len(contents_by_stock)}")
    
    # 创建用于存储Excel数据的列表
    excel_data = []
    
    for stock, items in contents_by_stock.items():
        print(f"股票 {stock}: {len(items)} 项内容")
        # 输出每个文档的标题和ID
        for i, item in enumerate(items):
            doc_id = item.get("_id", "无ID")
            title = item.get("title", "无标题")
            doc_type = item.get("type", "未知类型")
            es_source = item.get("es_source", "未知来源")
            print(f"  {i+1}. ID: {doc_id} | 标题: {title} | 来源: {es_source}")
            # 添加到Excel数据
            excel_data.append({
                "股票代码": stock if isinstance(stock, str) else str(stock),
                "序号": i+1,
                "文档ID": doc_id,
                "标题": title,
                "文档类型": doc_type,
                "ES来源": es_source
            })
        print("----------------------------")
    
    # 生成Excel文件
    if excel_data:
        df = pd.DataFrame(excel_data)
        output_dir = "output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_path = os.path.join(output_dir, f"股票相关文档_{timestamp}.xlsx")
        df.to_excel(excel_path, index=False)
        print(f"Excel文件已生成: {excel_path}")
    
    # 第三步：使用相关性排序，并按类型分组，同时限制每类数量
    # 纪要（5篇）、点评（5条）、公告（3篇）、研报（5篇）
    reranked_contents = rerank_by_relevance(contents_by_stock, all_keywords)
    
    # 第四步：生成最终报告
    # 使用第一个关键词作为主要概念
    primary_concept = keywords[0] if keywords else concept_keywords[0]
    final_report = generate_final_report(primary_concept, reranked_contents)
    
    return final_report

def agent_chat():
    """多 Agent 协作模式 — Coordinator 调度专业 Agent 协作"""
    from app.agent import CoordinatorAgent, ResearcherAgent, AnalystAgent, WriterAgent
    from app.llm import create_llm_client
    from config.agent_config import LLM_PROVIDERS, AGENT_MODEL_MAP

    print("=" * 60)
    print("  金融分析多Agent系统 v2.0")
    print("  Coordinator → Researcher → Analyst → Writer")
    print("  输入'退出'结束 | 输入'切换'切换到Pipeline快速模式")
    print("=" * 60)

    # 初始化各 Agent 的 LLM 客户端
    print("\n[系统] 正在初始化 LLM 客户端...")
    coordinator_llm = create_llm_client(LLM_PROVIDERS[AGENT_MODEL_MAP["coordinator"]])
    researcher_llm = create_llm_client(LLM_PROVIDERS[AGENT_MODEL_MAP["researcher"]])
    analyst_llm = create_llm_client(LLM_PROVIDERS[AGENT_MODEL_MAP["analyst"]])
    writer_llm = create_llm_client(LLM_PROVIDERS[AGENT_MODEL_MAP["writer"]])
    print(f"  Coordinator: {AGENT_MODEL_MAP['coordinator']} ({coordinator_llm.model_name})")
    print(f"  Researcher:  {AGENT_MODEL_MAP['researcher']} ({researcher_llm.model_name})")
    print(f"  Analyst:     {AGENT_MODEL_MAP['analyst']} ({analyst_llm.model_name})")
    print(f"  Writer:      {AGENT_MODEL_MAP['writer']} ({writer_llm.model_name})")

    # 初始化各 Agent
    print("\n[系统] 正在初始化 Agent 团队...")
    researcher = ResearcherAgent(llm_client=researcher_llm)
    analyst = AnalystAgent(llm_client=analyst_llm)
    writer = WriterAgent(llm_client=writer_llm)
    coordinator = CoordinatorAgent(
        llm_client=coordinator_llm,
        researcher=researcher,
        analyst=analyst,
        writer=writer,
    )
    print("[系统] Agent 团队就绪！\n")

    while True:
        try:
            question = input("🧠 > ")

            if question.lower() in ["退出", "exit", "quit"]:
                print("感谢使用多Agent系统，再见！")
                break

            if question.lower() in ["切换", "switch"]:
                print("切换到 Pipeline 快速模式...")
                pipeline_chat()
                print("返回多 Agent 模式...")
                continue

            if not question.strip():
                print("请输入有效问题。")
                continue

            print()  # 空行分隔
            result = coordinator.chat(question)
            print(f"\n{'='*60}")
            print(result)
            print(f"{'='*60}\n")

        except KeyboardInterrupt:
            print("\n感谢使用，再见！")
            break
        except Exception as e:
            print(f"\n[系统] 处理过程中发生错误: {str(e)}")
            import traceback
            traceback.print_exc()


def pipeline_chat():
    """原有 Pipeline 模式（快速模式，向后兼容）"""
    print("Pipeline 快速模式已启动（输入'切换'返回多Agent模式，输入'退出'结束）：")

    while True:
        question = input("⚡ > ")

        if question.lower() in ["退出", "exit", "quit"]:
            print("感谢使用，再见！")
            break

        if question.lower() in ["切换", "switch"]:
            print("切换到多 Agent 模式...")
            return

        if not question.strip():
            print("请输入有效问题。")
            continue

        try:
            report = process_question(question)
            print("\n===== 分析报告 =====\n")
            print(report)
            print("\n====================\n")
        except Exception as e:
            print(f"处理过程中发生错误: {str(e)}")


def main():
    """主函数 — 选择运行模式"""
    print("=" * 60)
    print("  金融分析助手")
    print("=" * 60)
    print("  1. 多 Agent 协作模式（推荐）— AI Agent 自主决策协作")
    print("  2. Pipeline 快速模式 — 原有固定流程")
    print("=" * 60)

    while True:
        choice = input("\n请选择模式 (1/2): ").strip()

        if choice == "1":
            agent_chat()
            break
        elif choice == "2":
            pipeline_chat()
            break
        elif choice.lower() in ["退出", "exit", "quit"]:
            print("再见！")
            break
        else:
            print("请输入 1 或 2")


if __name__ == "__main__":
    main()