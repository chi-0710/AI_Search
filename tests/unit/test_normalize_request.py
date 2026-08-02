import pytest
from pydantic import ValidationError
from app.graph.nodes.normalize_request import normalize_request
from app.graph.state import ResearchState

def build_state()->ResearchState:
    return {
        "thread_id": "thread_001",
        "task_id": "task_001",
        "topic": "  分析 LangGraph 最近三个月的重要更新  ",
        "research_type": "deep_report",
        "language": "zh-CN",
        "time_start": "2026-04-27",
        "time_end": "2026-07-27",
        "source_preferences": [
            "official_docs",
            "github_release",
        ],
        "max_sources": 15,
        "status": "created",
    }

def test_normalize_request()->None:
    state=build_state()

    update = normalize_request(state)

    assert update["topic"] == "分析 LangGraph 最近三个月的重要更新"
    assert update["research_type"] == "deep_report"
    assert update["time_start"] == "2026-04-27"
    assert update["time_end"] == "2026-07-27"
    assert update["max_sources"] == 15
    assert update["source_preferences"] == [
        "official_docs",
        "github_release",
    ]
    assert update["status"] == "request_normalized"

def test_use_default_optional_values() -> None:
    state: ResearchState = {
        "thread_id": "thread_001",
        "task_id": "task_001",
        "topic": "分析 MCP 对 Agent 开发的作用",
        "research_type": "deep_report",
        "language": "zh-CN",
        "status": "created",
    }

    update = normalize_request(state)

    assert update["time_start"] is None
    assert update["time_end"] is None
    assert update["source_preferences"] == []
    assert update["max_sources"] == 20

def test_reject_invalid_time_range() -> None:
    state = build_state()
    state["time_start"] = "2026-07-27"
    state["time_end"] = "2026-04-27"

    with pytest.raises(ValidationError):
        normalize_request(state)


def test_reject_invalid_date_format() -> None:
    state = build_state()
    state["time_start"] = "2026/04/27"

    with pytest.raises(ValueError):
        normalize_request(state)