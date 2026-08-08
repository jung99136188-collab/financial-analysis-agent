import json
import requests
from datetime import datetime, timedelta
import sys
import os
import time
import re
import random
from collections import defaultdict

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.es_config import es, MINUTES_INDEX, MINUTES_QUERY, MINUTES_SOURCE
from config.es_config import REPORT_INDEX, REPORT_QUERY, REPORT_SOURCE
from config.es_config import ANNOUNCEMENT_INDEX, ANNOUNCEMENT_QUERY, ANNOUNCEMENT_SOURCE
from config.es_config import COMMENT_INDEX, COMMENT_QUERY, COMMENT_SOURCE
from config.api_config import STOCK_MATCHER_URL, STOCK_MATCHER_HEADERS
from config.api_config import OPENAI_BASE_URL, OPENAI_API_KEY
from config.api_config import API_KEY_VOLCENGINE, BASE_URL_VOLCENGINE, DEEPSEEK_R1_ENDPOINT, DEEPSEEK_V3_ENDPOINT
from config.api_config import MAX_RETRIES, RETRY_DELAY

def clean_text_for_xml(text):
    """清理字符串中的XML不兼容字符"""
    if not isinstance(text, str):
        return text
    
    # 移除XML不兼容字符（NULL字节和控制字符）
    # XML 1.0允许的字符: #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
    return re.sub(r'[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]', '', text)

def analyze_question(question):
    """分析用户问题，提取关键词和概念"""
    prompt = f"""
    请对用户的【问题】按照如下要求进行进行理解和分析，
    关键词匹配信息：从问题中提取需要进行关键词匹配的核心信息。请注意：
    a. 不要包含与文档类别相关的词语，例如："A股"、"美股"、"研究报告"、"纪要"、"点评"、"研报"、"深度报告"、"路演"、"美股纪要"、"外资研报"、"公告"、"外资"、"新财富"等。
    b、核心信息为题材或板块，请充分理解并进行联想，例如减肥药可以拓展为利拉鲁肽、司美格鲁肽、降糖等。
    c. 务必确保提取的关键词和概念是能在金融文档原文中出现的实际词汇，以便能在后续搜索中找到匹配的内容。
                
    用户问题：{question}
            
    请严格按照JSON格式返回结果，不要有任何额外的文字说明，只返回以下JSON对象：
    {{
      "keywords": ["关键词1", "关键词2"],
      "concept": ["联想词1", "联想词2"]
    }}
    """
    
    # 使用OpenAI API进行问题分析
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,  # 降低温度以获得更确定性的输出
        "response_format": {"type": "json_object"}  # 指定响应格式为JSON
    }
    
    response = requests.post(f"{OPENAI_BASE_URL}chat/completions", 
                            headers=headers, 
                            json=data)
    
    if response.status_code == 200:
        try:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            parsed_result = json.loads(content)
            
            # 确保keywords和concept是列表
            if isinstance(parsed_result.get("keywords", []), str):
                parsed_result["keywords"] = [parsed_result["keywords"]]
            if isinstance(parsed_result.get("concept", []), str):
                parsed_result["concept"] = [parsed_result["concept"]]
                
            print(f"解析结果: {parsed_result}")
            return parsed_result
        except json.JSONDecodeError as e:
            print(f"无法解析JSON响应: {e}")
            print(f"原始响应内容: {content if 'content' in locals() else '未获取到内容'}")
            return {"keywords": [], "concept": []}
        except Exception as e:
            print(f"处理响应时出错: {str(e)}")
            return {"keywords": [], "concept": []}
    else:
        error_message = f"API请求失败: 状态码 {response.status_code}"
        try:
            error_details = response.json()
            error_message += f", 详情: {error_details}"
        except:
            pass
        print(error_message)
        return {"keywords": [], "concept": []}

def query_elasticsearch(index, query, source_fields, time_field, time_limit, keywords=None):
    """查询Elasticsearch并返回结果"""
    # 更新查询时间范围
    now = datetime.now()
    # 使用完整的日期时间格式，包含时分秒
    from_date = (now - timedelta(days=time_limit)).strftime("%Y-%m-%d %H:%M:%S")
    
    # 深拷贝查询条件，避免修改原始配置
    query_copy = json.loads(json.dumps(query))
    
    # 更新时间范围
    for must_condition in query_copy["query"]["bool"]["must"]:
        if "range" in must_condition and time_field in must_condition["range"]:
            must_condition["range"][time_field]["gt"] = from_date
    
    # 如果提供了关键词，添加到查询条件中
    if keywords and len(keywords) > 0:
        # 查找content或full_content字段中包含关键词的文档
        should_conditions = []
        for field in ["content", "full_content"]:
            for keyword in keywords:
                should_conditions.append({"match_phrase": {field: keyword}})
        
        # 添加关键词搜索条件
        if "should" not in query_copy["query"]["bool"]:
            query_copy["query"]["bool"]["should"] = []
        
        query_copy["query"]["bool"]["should"].extend(should_conditions)
        
        # 设置最小匹配数，至少匹配一个关键词
        if len(should_conditions) > 0:
            query_copy["query"]["bool"]["minimum_should_match"] = 1
    
    print(f"执行ES查询: {json.dumps(query_copy, ensure_ascii=False)}")
    
    try:
        # 执行查询
        response = es.search(
            index=index,
            body=query_copy,
            _source=source_fields,
            size=100  # 设置合适的查询大小
        )
        
        print(f"查询到 {len(response['hits']['hits'])} 条结果")
        return response["hits"]["hits"]
    except Exception as e:
        print(f"ES查询出错: {str(e)}")
        # 尝试不同的日期格式
        try:
            # 如果之前的查询失败，尝试只使用日期部分
            for must_condition in query_copy["query"]["bool"]["must"]:
                if "range" in must_condition and time_field in must_condition["range"]:
                    must_condition["range"][time_field]["gt"] = (now - timedelta(days=time_limit)).strftime("%Y-%m-%d")
            
            print(f"使用简化日期格式重试查询: {json.dumps(query_copy, ensure_ascii=False)}")
            response = es.search(
                index=index,
                body=query_copy,
                _source=source_fields,
                size=100
            )
            
            print(f"查询到 {len(response['hits']['hits'])} 条结果")
            return response["hits"]["hits"]
        except Exception as e2:
            print(f"使用简化日期格式重试查询仍然失败: {str(e2)}")
            return []

def extract_relevant_content(search_results, concept_keywords, content_field, max_chars=300):
    """从搜索结果中提取与概念相关的内容段落并立即识别股票"""
    relevant_contents = []
    
    for hit in search_results:
        try:
            source = hit.get("_source", {})
            # 获取内容字段
            content = source.get(content_field)
            
            # 如果内容为None，直接跳过该文档
            if content is None:
                print(f"跳过文档: ID {hit.get('_id', '未知')} 的内容字段 {content_field} 为None")
                continue
            
            # 检查content是否为字符串类型
            if not isinstance(content, str):
                print(f"警告: 文档ID {hit.get('_id', '未知')} 的内容字段 {content_field} 不是字符串类型，尝试转换")
                try:
                    content = str(content)
                except:
                    print(f"无法将内容转换为字符串，跳过该文档")
                    continue
            
            # 简单的文本匹配，查找包含概念关键词的段落
            paragraphs = content.split("\n\n")
            matching_contexts = []
            
            for paragraph in paragraphs:
                # 查找所有关键词的位置
                keyword_positions = []
                for keyword in concept_keywords:
                    if keyword in paragraph:
                        # 记录所有出现位置
                        start = 0
                        while True:
                            pos = paragraph.find(keyword, start)
                            if pos == -1:
                                break
                            keyword_positions.append((pos, pos + len(keyword), keyword))
                            start = pos + 1
                
                # 如果找到关键词
                if keyword_positions:
                    # 按位置排序
                    keyword_positions.sort(key=lambda x: x[0])
                    
                    # 处理每个关键词位置
                    for start_pos, end_pos, matched_keyword in keyword_positions:
                        # 计算上下文窗口
                        context_half = (max_chars - len(matched_keyword)) // 2
                        context_start = max(0, start_pos - context_half)
                        context_end = min(len(paragraph), end_pos + context_half)
                        
                        # 如果超出文本边界，调整另一边的窗口大小
                        if start_pos < context_half:
                            # 开始位置不够，增加结束位置
                            context_end = min(len(paragraph), context_end + (context_half - start_pos))
                        if context_end > len(paragraph) - context_half:
                            # 结束位置不够，增加开始位置
                            context_start = max(0, context_start - (context_half - (len(paragraph) - end_pos)))
                        
                        # 提取上下文
                        context = paragraph[context_start:context_end]
                        
                        # 添加省略号表示截断
                        if context_start > 0:
                            context = "..." + context
                        if context_end < len(paragraph):
                            context = context + "..."
                        
                        # 如果上下文太短，跳过
                        if len(context) < 50:  # 太短的上下文可能无意义
                            continue
                        
                        # 检查是否与已有上下文有大量重叠
                        overlap = False
                        for existing in matching_contexts:
                            if existing in context or context in existing:
                                overlap = True
                                break
                        
                        if not overlap:
                            matching_contexts.append(context)
            
            # 如果没有找到匹配的上下文，尝试检查整个内容是否包含关键词
            if not matching_contexts and any(keyword in content for keyword in concept_keywords):
                print(f"在文档 {hit.get('_id', '未知')} 中没有找到匹配段落，尝试全文匹配")
                
                # 在整个内容中查找第一个关键词
                for keyword in concept_keywords:
                    if keyword in content:
                        pos = content.find(keyword)
                        context_half = (max_chars - len(keyword)) // 2
                        context_start = max(0, pos - context_half)
                        context_end = min(len(content), pos + len(keyword) + context_half)
                        
                        # 调整上下文窗口
                        if pos < context_half:
                            context_end = min(len(content), context_end + (context_half - pos))
                        if context_end > len(content) - pos - len(keyword):
                            context_start = max(0, context_start - (context_half - (len(content) - pos - len(keyword))))
                        
                        context = content[context_start:context_end]
                        
                        if context_start > 0:
                            context = "..." + context
                        if context_end < len(content):
                            context = context + "..."
                        
                        matching_contexts.append(context)
                        break
            
            # 如果没有匹配上下文，跳过该文档
            if not matching_contexts:
                print(f"文档 {hit.get('_id', '未知')} 中未找到有效上下文，跳过")
                continue
                
            # 为每个匹配的上下文创建一个结果项并立即识别股票
            for context in matching_contexts[:3]:  # 限制每个文档最多3个上下文
                # 创建结果字典
                result = {
                    "_id": hit.get("_id", ""),
                    "title": source.get("title", "无标题"),
                    "content": context
                }
                
                # 添加时间信息
                if "publish_date" in source:
                    result["time"] = source["publish_date"]
                elif "time" in source:
                    result["time"] = source["time"]
                elif "end_date" in source:
                    result["time"] = source["end_date"]
                else:
                    result["time"] = "未知时间"
                
                # 首先检查源数据中是否已有股票信息
                stock_value = None
                if "stock" in source:
                    stock_value = source["stock"]
                elif "sec" in source:
                    stock_value = source["sec"]
                
                # 确保stock是字符串类型
                if stock_value:
                    if isinstance(stock_value, list):
                        # 如果是列表，取第一个元素
                        if len(stock_value) > 0:
                            result["stock"] = str(stock_value[0])
                        else:
                            stock_value = None
                    else:
                        result["stock"] = str(stock_value)
                
                # 如果没有有效的股票信息，调用API识别
                if not stock_value:
                    # 如果没有股票信息，立即调用股票识别API
                    try:
                        stocks = identify_stocks(context)
                        if stocks and len(stocks) > 0:
                            result["stock"] = str(stocks[0]["stock_code"])  # 确保是字符串
                        else:
                            print(f"未识别到股票，跳过文档 {result['_id']}")
                            continue  # 如果没有识别到股票，跳过这个段落
                    except Exception as e:
                        print(f"股票识别出错: {str(e)}，跳过文档 {result['_id']}")
                        continue  # 如果识别出错，跳过这个段落
                
                # 只有成功识别到股票的内容才会被添加
                relevant_contents.append(result)
        except Exception as e:
            print(f"处理文档时出错: {str(e)}")
            continue
    
    return relevant_contents

def identify_stocks(text, max_length=1000):
    """
    使用股票识别API识别文本中的股票
    
    参数:
        text (str): 要识别的文本内容
        max_length (int): 最大文本长度限制，过长会被截断
        
    返回:
        list: 识别到的股票列表，每项包含股票代码和名称
    """
    try:
        # 限制文本长度，避免请求过大
        if len(text) > max_length:
            print(f"文本过长 ({len(text)}字符)，截断至{max_length}字符")
            text = text[:max_length]
        
        # 确保文本不为空
        if not text or len(text.strip()) == 0:
            print("警告: 尝试识别空文本")
            return []
            
        # 构建与成功案例一致的请求格式
        payload = json.dumps({
            "is_keep_vague": "1",
            "scope": "prd",
            "content": text
        })
        
        # 打印请求信息
        print(f"发送股票识别请求，文本长度: {len(text)}字符")
        
        response = requests.request(
            "POST",
            STOCK_MATCHER_URL,
            headers=STOCK_MATCHER_HEADERS,
            data=payload,  # 使用data而不是json
            timeout=5
        )
        
        if response.status_code == 200:
            result = response.json()
            stocks = result.get("data", [])
            if stocks:
                stock_codes = [s.get("stock_code", "未知") for s in stocks]
                print(f"识别到股票: {', '.join(stock_codes)}")
            else:
                print("未识别到股票")
            return stocks
        else:
            print(f"股票识别API请求失败: 状态码 {response.status_code}")
            if response.status_code == 422:
                print(f"请求内容可能不合规: {payload[:100]}...")
            try:
                error_details = response.json()
                print(f"错误详情: {error_details}")
            except:
                print(f"无法解析错误响应")
            return []
    except requests.exceptions.Timeout:
        print("股票识别API请求超时")
        return []
    except requests.exceptions.ConnectionError:
        print("股票识别API连接错误")
        return []
    except Exception as e:
        print(f"股票识别API请求异常: {str(e)}")
        return []

def filter_by_stocks(contents):
    """
    过滤内容，确保其中含有股票
    注意：此函数现在只是保留用于兼容现有代码，实际过滤已在extract_relevant_content中完成
    """
    # 所有传入的内容都已经通过股票识别，直接返回
    return contents

def generate_ngrams(text, n):
    """
    生成文本的n-gram
    
    参数:
        text (str): 输入文本
        n (int): n-gram的n值
        
    返回:
        set: 文本的n-gram集合
    """
    if not isinstance(text, str):
        return set()
        
    # 清洗文本，移除标点和多余空格
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    # 如果清洗后文本太短，直接返回
    if len(text) < n:
        return set()
        
    # 生成n-gram
    ngrams = set()
    for i in range(len(text) - n + 1):
        ngram = text[i:i+n]
        ngrams.add(ngram)
    
    return ngrams

def calculate_similarity(text1, text2, n=3):
    """
    计算两个文本基于n-gram的相似度
    
    参数:
        text1 (str): 第一个文本
        text2 (str): 第二个文本
        n (int): n-gram的n值
        
    返回:
        float: 两个文本的相似度 (0-1)
    """
    # 生成n-gram
    ngrams1 = generate_ngrams(text1, n)
    ngrams2 = generate_ngrams(text2, n)
    
    # 如果任一文本的n-gram为空，返回0
    if not ngrams1 or not ngrams2:
        return 0
    
    # 计算Jaccard相似度: 交集大小 / 并集大小
    intersection = ngrams1.intersection(ngrams2)
    union = ngrams1.union(ngrams2)
    
    return len(intersection) / len(union)

def remove_duplicates(items, similarity_threshold=0.7, n=None):
    """
    使用n-gram去除列表中的重复内容
    
    参数:
        items (list): 内容项列表
        similarity_threshold (float): 相似度阈值，超过该值视为重复
        n (int): n-gram的n值，如果为None则随机在2-3之间选择
        
    返回:
        list: 去重后的列表
    """
    if not items:
        return []
        
    # 如果n未指定，随机选择2或3
    if n is None:
        n = random.choice([2, 3])
    
    print(f"使用n-gram (n={n})去重，相似度阈值={similarity_threshold}")
    
    unique_items = []
    # 记录每个项目的指纹，用于快速去重
    fingerprints = defaultdict(set)
    
    for item in items:
        content = item.get("content", "")
        
        # 生成当前项目的n-gram
        current_ngrams = generate_ngrams(content, n)
        
        # 如果内容为空或太短，直接保留
        if not current_ngrams:
            unique_items.append(item)
            continue
        
        # 检查是否与已有项目重复
        is_duplicate = False
        for idx, unique_item in enumerate(unique_items):
            unique_content = unique_item.get("content", "")
            
            # 计算相似度
            similarity = calculate_similarity(content, unique_content, n)
            
            if similarity > similarity_threshold:
                print(f"发现重复内容 (相似度: {similarity:.2f})")
                is_duplicate = True
                break
        
        # 如果不是重复内容，添加到唯一列表
        if not is_duplicate:
            unique_items.append(item)
    
    print(f"去重前: {len(items)}项, 去重后: {len(unique_items)}项")
    return unique_items

def rerank_by_relevance(contents_by_stock, concept_keywords):
    """
    使用相关性排序对内容进行排序，并按类型分组保留最相关的内容
    
    参数:
        contents_by_stock: 按股票分组的内容
        concept_keywords: 概念关键词列表
    
    返回:
        dict: 按股票和类型分组的排序后内容，每类最多保留指定数量
    """
    reranked_contents = {}
    
    for stock, items in contents_by_stock.items():
        if not items:
            continue
            
        # 分类
        minutes = []
        reports = []
        announcements = []
        comments = []
        
        # 按类型分组
        for item in items:
            source_id = str(item.get("_id", ""))
            
            if "roadshow_summary" in source_id:
                minutes.append(item)
            elif "report" in source_id:
                reports.append(item)
            elif "announcement" in source_id:
                announcements.append(item)
            elif "comment" in source_id:
                comments.append(item)
        
        # 计算相关性分数
        def calculate_relevance(item):
            content = item.get("content", "")
            # 基本分数：关键词出现次数
            base_score = sum(content.count(keyword) for keyword in concept_keywords)
            
            # 关键词密度因子：关键词出现次数 / 文本长度
            density = base_score / max(len(content), 1) * 1000
            
            # 标题因子：标题中包含关键词加分
            title = item.get("title", "")
            title_score = sum(title.count(keyword) * 2 for keyword in concept_keywords)
            
            # 最终分数
            item["relevance_score"] = base_score + density + title_score
            return item["relevance_score"]
        
        # 对每类内容进行排序
        minutes.sort(key=calculate_relevance, reverse=True)
        reports.sort(key=calculate_relevance, reverse=True)
        announcements.sort(key=calculate_relevance, reverse=True)
        comments.sort(key=calculate_relevance, reverse=True)
        
        # 使用n-gram对各类内容进行去重
        # 为每种类型随机选择n=2或n=3
        minutes = remove_duplicates(minutes, similarity_threshold=0.6)
        reports = remove_duplicates(reports, similarity_threshold=0.6)
        announcements = remove_duplicates(announcements, similarity_threshold=0.6)
        comments = remove_duplicates(comments, similarity_threshold=0.6)
        
        # 限制每类数量
        reranked_contents[stock] = {
            "minutes": minutes[:5],        # 最多5篇纪要
            "reports": reports[:5],        # 最多5篇研报
            "announcements": announcements[:3],  # 最多3篇公告
            "comments": comments[:5]       # 最多5条点评
        }
        
        # 记录日志
        print(f"股票 {stock} 最相关内容:")
        print(f"  - 纪要: {len(minutes[:5])}/{len(minutes)}")
        print(f"  - 研报: {len(reports[:5])}/{len(reports)}")
        print(f"  - 公告: {len(announcements[:3])}/{len(announcements)}")
        print(f"  - 点评: {len(comments[:5])}/{len(comments)}")
    
    return reranked_contents

def group_by_stock_and_type(contents):
    """
    按股票和内容类型分组（简化版，直接调用rerank_by_relevance）
    """
    # 按股票分组
    contents_by_stock = {}
    for item in contents:
        try:
            # 确保stock是字符串类型
            stock = item.get("stock", "unknown")
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
            print(f"分组时出错: {str(e)}")
            continue
    
    # 调用rerank_by_relevance进行更精确的分组和排序
    return rerank_by_relevance(contents_by_stock, [""])

def generate_final_report(concept, grouped_contents):
    """生成最终报告"""
    # 清理和简化输入数据
    clean_data = {}
    
    for stock, data in grouped_contents.items():
        clean_data[stock] = {
            "minutes": [],
            "reports": [],
            "announcements": [],
            "comments": []
        }
        
        # 对每种类型只保留必要的字段，限制数据量
        for item in data.get("minutes", [])[:5]:  # 最多5篇纪要
            clean_data[stock]["minutes"].append({
                "_id": item.get("_id", ""),  # 使用_id而不是id，与ES保持一致
                "title": item.get("title", ""),
                "content": item.get("content", "")[:300],  # 限制内容长度
                "time": item.get("time", "")
            })
            
        for item in data.get("reports", [])[:5]:  # 最多5篇研报
            clean_data[stock]["reports"].append({
                "_id": item.get("_id", ""),  # 使用_id而不是id，与ES保持一致
                "title": item.get("title", ""),
                "content": item.get("content", "")[:300],  # 限制内容长度
                "time": item.get("time", "")
            })
            
        for item in data.get("announcements", [])[:3]:  # 最多3篇公告
            clean_data[stock]["announcements"].append({
                "_id": item.get("_id", ""),  # 使用_id而不是id，与ES保持一致
                "title": item.get("title", ""),
                "content": item.get("content", "")[:300],  # 限制内容长度
                "time": item.get("time", "")
            })
            
        for item in data.get("comments", [])[:5]:  # 最多5条点评
            clean_data[stock]["comments"].append({
                "_id": item.get("_id", ""),  # 使用_id而不是id，与ES保持一致
                "title": item.get("title", ""),
                "content": item.get("content", "")[:300],  # 限制内容长度
                "time": item.get("time", "")
            })
    
    # 清理数据
    clean_json = clean_text_for_xml(json.dumps(clean_data, ensure_ascii=False))
    
    prompt = f"""
    你是一名杰出的金融分析师，擅长撰写高质量的金融深度研究报告。
    现在请根据【整体草稿】与【概念/板块】撰写与"{concept}"相关的内容：
    
    【重要】请注意：在撰写过程中必须标注来源，格式统一为[来源:XXX]，其中XXX是文档的_id字段值。
    这些_id通常是长字符串（如RRP00000000058924250），而不是股票代码（如301127.SZ）。
    每个引用的来源必须使用文档的_id，即JSON数据中每个条目的"_id"字段。
    
    如果同一要点有多个来源，则直接在同一处连续添加来源标注，如：[来源:RRP00000000058924250][来源:RRP00000000059924251]。
    请确保仅基于【整体章节草稿】进行撰写，避免杜撰或使用任何未证实的数据或信息，并尽量保证内容的丰富和充分。
    请特别注意，在书写过程中，如果觉得部分文字（特别涉及到数据方面的），可以通过表格的形式呈现会更加直观，
    那么这部分信息可以使用表格的格式呈现。
    
    【整体草稿】:
    {clean_json}
    """
    
    # ===== 完全按照QUERY_5.py的方式调用DeepSeek API =====
    url = f"{BASE_URL_VOLCENGINE}/chat/completions"
    
    # QUERY_5中的用法是将endpoint_id直接用作model参数的值
    r1_endpoint = "ep-20250204184813-x7d7b"  # 硬编码确保正确
    
    payload = {
        "model": r1_endpoint,  # 直接使用endpoint_id作为model值，不需要单独的endpoint_id字段
        "messages": [
            {"role": "system", "content": "你是一名杰出的金融分析师，擅长撰写高质量的金融深度研究报告。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "top_p": 0.8,
        "max_tokens": 2000
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY_VOLCENGINE}"
    }
    
    for retry in range(MAX_RETRIES):
        try:
            print(f"正在调用DeepSeek R1模型生成报告... (尝试 {retry+1}/{MAX_RETRIES})")
            print(f"使用model参数: {r1_endpoint}")
            
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                # 检查是否正确引用了_id
                if "[来源:" in content and not any(stock_code in content for stock_code in ["SZ", "SH", "BJ", "."] if "[来源:" + stock_code in content):
                    return content
                else:
                    print("警告：生成的内容可能没有正确引用_id，重新尝试...")
                    continue  # 如果发现引用格式不对，重试
            else:
                print(f"API调用失败，状态码: {response.status_code}")
                print(f"错误信息: {response.text}")
                
            if retry < MAX_RETRIES - 1:
                print(f"将在 {RETRY_DELAY} 秒后重试...")
                time.sleep(RETRY_DELAY)
        
        except Exception as e:
            print(f"调用API时出错: {str(e)}")
            if retry < MAX_RETRIES - 1:
                print(f"将在 {RETRY_DELAY} 秒后重试...")
                time.sleep(RETRY_DELAY)
    
    print("无法成功调用模型，返回错误信息")
    return "无法生成报告，API请求失败。请稍后再试。" 