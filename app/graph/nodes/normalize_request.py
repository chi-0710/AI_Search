from datetime import date
from typing import Any
from app.graph.state import ResearchState
from app.models.research import ResearchRequest

def parse_optional_date(value:str|None)->date|None:
    """
        解析可选的日期字符串为 date 对象
        例如：
            2026-07-27 -> date(2026, 7, 27)
    """
    if value is None:
        return None
    return date.fromisoformat(value)

def normalize_request(state:ResearchState)->dict[str,Any]:
    """
        归一化用户提交的研究任务

        1 清理主体
        2 转换日期
        3 补充默认值
        4 使用ResearchRequest校验
        5 返回本节点负责更新的字段
    """
    request=ResearchRequest(
        topic=state["topic"].strip(),
        research_type=state.get(
            "research_type",
            "deep_report",
        ),
        language=state.get(
            "language",
            "zh-CN",
        ),
        time_start=parse_optional_date(
            state.get("time_start"),
        ),
        time_end=parse_optional_date(
            state.get("time_end"),
        ),
        source_preferences=state.get(
            "source_preferences",
            [],
        ),
        max_sources=state.get(
            "max_sources",
            20,
        ),
    )

    return {
        "topic":request.topic,
        "research_type":request.research_type,
        "time_start":(
            request.time_start.isoformat()
            if request.time_start is not None
            else None
        ),
        "time_end":(
            request.time_end.isoformat()
            if request.time_end is not None
            else None
        ),
        "language": request.language,
        "source_preferences": request.source_preferences,
        "max_sources": request.max_sources,
        "status": "request_normalized",
    }