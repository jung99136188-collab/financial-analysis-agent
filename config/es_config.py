from elasticsearch import Elasticsearch

# ES连接配置
es = Elasticsearch(['http://192.168.60.180:9201'], http_auth=('data_saas_ro', '7lDO#&^458c3$H!I'))

# ES索引配置
# 纪要索引配置
MINUTES_INDEX = "rabyte_saas_reading_roadshow_summary_index"
MINUTES_QUERY = {
    "query": {
        "bool": {
            "must": [
                {"term": {"recorder": "MT"}},
                {"term": {"is_deleted": 0}},
                {"range": {"publish_date": {"gt": "2025-01-01 00:00:00"}}}
            ]
        }
    }
}
MINUTES_SOURCE = ["_id", "title", "publish_date", "stock", "content"]

# 研报索引配置
REPORT_INDEX = "rabyte_saas_reading_report_index"
REPORT_QUERY = {
    "query": {
        "bool": {
            "must": [
                {"term": {"is_deleted": 0}},
                {"range": {"time": {"gt": "2025-01-01 00:00:00"}}}
            ]
        }
    }
}
REPORT_SOURCE = ["_id", "title", "time", "stock", "full_content"]

# 公告索引配置
ANNOUNCEMENT_INDEX = "rabyte_saas_reading_stock_announcement_index"
ANNOUNCEMENT_QUERY = {
    "query": {
        "bool": {
            "must": [
                {"term": {"is_deleted": 0}},
                {"range": {"end_date": {"gt": "2024-01-01 00:00:00"}}}
            ]
        }
    }
}
ANNOUNCEMENT_SOURCE = ["_id", "title", "end_date", "sec", "content"]

# 点评索引配置
COMMENT_INDEX = "rabyte_saas_reading_comment_index"
COMMENT_QUERY = {
    "query": {
        "bool": {
            "must": [
                {"term": {"is_deleted": 0}},
                {"range": {"time": {"gt": "2025-01-01 00:00:00"}}},
                {"term": {"cmnt_category": "txt"}}
            ]
        }
    }
}
COMMENT_SOURCE = ["_id", "title", "time", "sec", "content"] 