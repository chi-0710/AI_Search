from typing import Any,Literal,NotRequired,TypedDict
from app.models.research import ResearchQuestion, ResearchType


class ResearchState(TypedDict):
    """
        langGraph 研究状态
    """
    thread_id: str
    task_id: str

    topic: str
    research_type: ResearchType
    language: str

    time_start: NotRequired[str]
    time_end: NotRequired[str]

    source_preferences: list[str]
    max_sources: int

    research_questions: list[ResearchQuestion]
    raw_sources: list[dict[str, Any]]
    processed_sources: list[dict[str, Any]]

    draft_report: NotRequired[dict[str, Any]]
    final_report: NotRequired[dict[str, Any]]
    report_markdown: NotRequired[str]

    revision_count: int
    status: str
    errors: list[str]

    token_usage: int
    estimated_cost: float