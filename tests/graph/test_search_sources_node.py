from typing import Any

import pytest

from app.graph.nodes.search_sources import (
    deduplicate_sources,
    search_sources_with_tool,
)
from app.graph.state import ResearchState
from app.models.research import ResearchQuestion
from app.models.source import SourceDocument
from app.tools.base import ToolResult


class FakeSearchTool:
    def __init__(
        self,
        results: dict[str, ToolResult[SourceDocument] | Exception],
    ) -> None:
        self.results = results
        self.queries: list[str] = []

    async def run(
        self,
        query: str,
        **kwargs: Any,
    ) -> ToolResult[SourceDocument]:
        self.queries.append(query)

        result = self.results[query]

        if isinstance(result, Exception):
            raise result

        return result


def build_question(
    question: str,
    goal: str,
) -> ResearchQuestion:
    return ResearchQuestion(
        question=question,
        goal=goal,
        preferred_sources=["official_docs"],
    )


def build_source(
    *,
    source_id: str,
    url: str,
    score: float,
    content_hash: str | None = None,
) -> SourceDocument:
    return SourceDocument(
        source_id=source_id,
        title=f"Source {source_id}",
        url=url,
        source_type="web",
        summary="Source summary",
        content_hash=content_hash,
        metadata={
            "canonical_url": url,
            "score": score,
        },
    )


def build_state(
    questions: list[ResearchQuestion],
    *,
    max_sources: int = 10,
) -> ResearchState:
    return {
        "thread_id": "thread-test",
        "task_id": "task-test",
        "topic": "LangGraph research agents",
        "research_type": "deep_report",
        "language": "zh-CN",
        "source_preferences": [],
        "max_sources": max_sources,
        "research_questions": questions,
        "raw_sources": [],
        "processed_sources": [],
        "revision_count": 0,
        "status": "plan_completed",
        "errors": [],
        "token_usage": 0,
        "estimated_cost": 0.0,
    }


def success_result(
    query: str,
    items: list[SourceDocument],
) -> ToolResult[SourceDocument]:
    return ToolResult[SourceDocument](
        tool_name="fake_search",
        query=query,
        success=True,
        items=items,
        duration_ms=1.0,
    )


def failure_result(
    query: str,
    error: str,
) -> ToolResult[SourceDocument]:
    return ToolResult[SourceDocument](
        tool_name="fake_search",
        query=query,
        success=False,
        items=[],
        error=error,
        duration_ms=1.0,
    )


@pytest.mark.asyncio
async def test_search_all_questions_successfully() -> None:
    question_a = build_question(
        "LangGraph 的核心架构是什么？",
        "分析核心架构",
    )
    question_b = build_question(
        "LangGraph 如何实现状态持久化？",
        "分析状态持久化",
    )

    source_a = build_source(
        source_id="source-a",
        url="https://example.com/a",
        score=0.9,
    )
    source_b = build_source(
        source_id="source-b",
        url="https://example.com/b",
        score=0.8,
    )

    tool = FakeSearchTool(
        {
            question_a.question: success_result(
                question_a.question,
                [source_a],
            ),
            question_b.question: success_result(
                question_b.question,
                [source_b],
            ),
        }
    )

    result = await search_sources_with_tool(
        state=build_state([question_a, question_b]),
        search_tool=tool,
        max_concurrency=2,
    )

    assert result["status"] == "search_completed"
    assert result["errors"] == []
    assert len(result["raw_sources"]) == 2
    assert len(result["processed_sources"]) == 2
    assert set(tool.queries) == {
        question_a.question,
        question_b.question,
    }


@pytest.mark.asyncio
async def test_continue_when_one_search_fails() -> None:
    question_a = build_question(
        "问题 A 的技术架构是什么？",
        "分析架构",
    )
    question_b = build_question(
        "问题 B 的风险是什么？",
        "分析风险",
    )

    source = build_source(
        source_id="source-a",
        url="https://example.com/a",
        score=0.9,
    )

    tool = FakeSearchTool(
        {
            question_a.question: success_result(
                question_a.question,
                [source],
            ),
            question_b.question: failure_result(
                question_b.question,
                "provider timeout",
            ),
        }
    )

    result = await search_sources_with_tool(
        state=build_state([question_a, question_b]),
        search_tool=tool,
    )

    assert result["status"] == "search_completed_with_warnings"
    assert len(result["processed_sources"]) == 1
    assert len(result["errors"]) == 1
    assert question_b.question in result["errors"][0]
    assert "provider timeout" in result["errors"][0]


@pytest.mark.asyncio
async def test_capture_search_tool_exception() -> None:
    question = build_question(
        "搜索工具异常时如何处理？",
        "验证异常处理",
    )

    tool = FakeSearchTool(
        {
            question.question: TimeoutError("request timed out"),
        }
    )

    result = await search_sources_with_tool(
        state=build_state([question]),
        search_tool=tool,
    )

    assert result["status"] == "search_failed"
    assert result["processed_sources"] == []
    assert len(result["errors"]) == 1
    assert "TimeoutError" in result["errors"][0]


@pytest.mark.asyncio
async def test_empty_result_becomes_warning_and_failure() -> None:
    question = build_question(
        "不存在的技术主题是什么？",
        "验证空结果",
    )

    tool = FakeSearchTool(
        {
            question.question: success_result(
                question.question,
                [],
            ),
        }
    )

    result = await search_sources_with_tool(
        state=build_state([question]),
        search_tool=tool,
    )

    assert result["status"] == "search_failed"
    assert result["processed_sources"] == []
    assert "No search results found" in result["errors"][0]


@pytest.mark.asyncio
async def test_merge_question_relations_for_duplicate_url() -> None:
    question_a = build_question(
        "项目的核心功能是什么？",
        "分析核心功能",
    )
    question_b = build_question(
        "项目的主要限制是什么？",
        "分析主要限制",
    )

    lower_score_source = build_source(
        source_id="source-a",
        url="https://example.com/shared",
        score=0.5,
    )
    higher_score_source = build_source(
        source_id="source-a",
        url="https://example.com/shared",
        score=0.9,
    )

    tool = FakeSearchTool(
        {
            question_a.question: success_result(
                question_a.question,
                [lower_score_source],
            ),
            question_b.question: success_result(
                question_b.question,
                [higher_score_source],
            ),
        }
    )

    result = await search_sources_with_tool(
        state=build_state([question_a, question_b]),
        search_tool=tool,
    )

    assert result["status"] == "search_completed"
    assert len(result["raw_sources"]) == 2
    assert len(result["processed_sources"]) == 1

    source = result["processed_sources"][0]
    metadata = source["metadata"]

    assert metadata["score"] == 0.9
    assert metadata["research_questions"] == [
        question_a.question,
        question_b.question,
    ]
    assert metadata["research_goals"] == [
        question_a.goal,
        question_b.goal,
    ]


def test_deduplicate_different_urls_by_content_hash() -> None:
    raw_sources = [
        {
            "source_id": "source-a",
            "title": "Original",
            "url": "https://example.com/original",
            "source_type": "web",
            "published_at": None,
            "summary": "summary",
            "clean_content": "same content",
            "content_hash": "same-hash",
            "metadata": {
                "canonical_url": "https://example.com/original",
                "score": 0.9,
                "research_questions": ["问题 A"],
                "research_goals": ["目标 A"],
            },
        },
        {
            "source_id": "source-b",
            "title": "Mirror",
            "url": "https://mirror.example.com/article",
            "source_type": "web",
            "published_at": None,
            "summary": "summary",
            "clean_content": "same content",
            "content_hash": "same-hash",
            "metadata": {
                "canonical_url": "https://mirror.example.com/article",
                "score": 0.7,
                "research_questions": ["问题 B"],
                "research_goals": ["目标 B"],
            },
        },
    ]

    result = deduplicate_sources(
        raw_sources,
        max_sources=10,
    )

    assert len(result) == 1
    assert result[0]["source_id"] == "source-a"
    assert result[0]["metadata"]["research_questions"] == [
        "问题 A",
        "问题 B",
    ]


def test_sort_and_limit_sources() -> None:
    raw_sources = [
        {
            "source_id": f"source-{index}",
            "title": f"Source {index}",
            "url": f"https://example.com/{index}",
            "source_type": "web",
            "published_at": None,
            "summary": "",
            "clean_content": "",
            "content_hash": None,
            "metadata": {
                "canonical_url": f"https://example.com/{index}",
                "score": score,
                "research_questions": [],
                "research_goals": [],
            },
        }
        for index, score in enumerate([0.3, 0.9, 0.6])
    ]

    result = deduplicate_sources(
        raw_sources,
        max_sources=2,
    )

    assert len(result) == 2
    assert [
        item["metadata"]["score"]
        for item in result
    ] == [0.9, 0.6]