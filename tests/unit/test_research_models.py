from datetime import date
import pytest
from pydantic import ValidationError
from app.models.research import ResearchRequest,ResearchQuestion

def test_create_valid_research_request()->None:
    request=ResearchRequest(
        topic="分析LangGraph最近三个月的重要更新",
        research_type="deep_report",
        language="zh-CN",
        time_start=date(2026, 4, 24),
        time_end=date(2026, 7, 24),
    )
    assert request.research_type=="deep_report"
    assert request.language=="zh-CN"
    assert request.max_sources==20

def test_reject_short_topic()->None:
    with pytest.raises(ValidationError):
        ResearchRequest(
            topic="AI",
            research_type="deep_report",
        )

def test_reject_invalid_time_range()->None:
    with pytest.raises(ValidationError):
        ResearchRequest(
            topic="分析LangGraph最近三个月的重要更新",
            research_type="deep_report",
            time_start=date(2026, 7, 24),
            time_end=date(2026, 4, 24),
        )

def test_create_research_question()->None:
    question=ResearchQuestion(
        question="LangGraph 发布了哪些主要版本？",
        goal="整理版本更新及其主要能力",
        preferred_sources=["official_docs", "github_release"],
    )

    assert len(question.preferred_sources)==2