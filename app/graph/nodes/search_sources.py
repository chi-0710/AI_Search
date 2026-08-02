import asyncio
from typing import Any

from langgraph.runtime import Runtime

from app.graph.context import ResearchContext
from app.graph.state import ResearchState
from app.models.research import ResearchQuestion
from app.models.source import SourceDocument
from app.tools.base import ToolProtocol, ToolResult


async def search_sources_with_tool(
    state: ResearchState,
    search_tool: ToolProtocol[SourceDocument],
    max_concurrency: int = 5,
) -> dict[str, Any]:
    """
    根据研究问题并发搜索来源。

    处理原则：
    1. 单个问题失败不影响其他问题；
    2. 所有搜索失败时才将节点标记为失败；
    3. 同一来源被多个问题命中时合并问题关联；
    4. 先按规范 URL 去重，再按内容哈希去重；
    5. 最终来源数量不超过 max_sources。
    """

    questions = state.get("research_questions", [])

    if not questions:
        return {
            "raw_sources": [],
            "processed_sources": [],
            "status": "search_failed",
            "errors": [
                *state.get("errors", []),
                "No research questions found in the state.",
            ],
        }

    semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def search_one(
        question: ResearchQuestion,
    ) -> tuple[
        ResearchQuestion,
        ToolResult[SourceDocument] | None,
        str | None,
    ]:
        try:
            async with semaphore:
                result = await search_tool.run(question.question)
        except Exception as exc:
            return (
                question,
                None,
                f"{type(exc).__name__}: {exc}",
            )

        if not result.success:
            return (
                question,
                result,
                result.error or "Search failed.",
            )

        if not result.items:
            return (
                question,
                result,
                "No search results found.",
            )

        return question, result, None

    attempts = await asyncio.gather(
        *(search_one(question) for question in questions)
    )

    raw_sources: list[dict[str, Any]] = []
    errors = list(state.get("errors", []))

    for question, result, search_error in attempts:
        if search_error is not None:
            errors.append(
                f"Search failed for question "
                f"{question.question!r}: {search_error}"
            )

        if result is None or not result.success:
            continue

        for source in result.items:
            raw_sources.append(
                annotate_source(
                    source=source,
                    question=question,
                ).model_dump(mode="json")
            )

    processed_sources = deduplicate_sources(
        raw_sources,
        max_sources=state.get("max_sources", 20),
    )

    if not processed_sources:
        status = "search_failed"
    elif errors:
        status = "search_completed_with_warnings"
    else:
        status = "search_completed"

    return {
        "raw_sources": raw_sources,
        "processed_sources": processed_sources,
        "status": status,
        "errors": errors,
    }


def annotate_source(
    source: SourceDocument,
    question: ResearchQuestion,
) -> SourceDocument:
    """
    给来源增加研究问题关联。

    使用列表而不是单个 research_question 字段，
    这样同一来源被多个研究问题命中时可以合并关联。
    """

    metadata = {
        **source.metadata,
        "research_questions": [question.question],
        "research_goals": [question.goal],
    }

    return source.model_copy(
        update={"metadata": metadata}
    )


def deduplicate_sources(
    raw_sources: list[dict[str, Any]],
    *,
    max_sources: int,
) -> list[dict[str, Any]]:
    """
    来源去重、问题关联合并和基础排序。

    去重优先级：
    1. canonical_url；
    2. url；
    3. content_hash。

    同一来源重复出现时：
    - 保留相关性分数更高的版本；
    - 合并其关联的研究问题和研究目标。
    """

    sources_by_url: dict[str, dict[str, Any]] = {}
    hash_to_url: dict[str, str] = {}

    for source in raw_sources:
        source_copy = {
            **source,
            "metadata": dict(source.get("metadata", {})),
        }

        metadata = source_copy["metadata"]

        source_url = str(
            metadata.get("canonical_url")
            or source_copy.get("url")
            or ""
        ).strip()

        content_hash = str(
            source_copy.get("content_hash") or ""
        ).strip()

        existing_key: str | None = None

        if source_url and source_url in sources_by_url:
            existing_key = source_url
        elif content_hash and content_hash in hash_to_url:
            existing_key = hash_to_url[content_hash]

        if existing_key is None:
            # 正常情况下 URL 必须存在。
            # fallback key 只用于防止异常数据覆盖其他来源。
            storage_key = source_url or f"source:{source_copy.get('source_id')}"

            sources_by_url[storage_key] = source_copy

            if content_hash:
                hash_to_url[content_hash] = storage_key

            continue

        existing = sources_by_url[existing_key]

        merged = merge_duplicate_source(
            existing=existing,
            candidate=source_copy,
        )

        sources_by_url[existing_key] = merged

        merged_hash = str(
            merged.get("content_hash") or ""
        ).strip()

        if merged_hash:
            hash_to_url[merged_hash] = existing_key

    processed_sources = list(sources_by_url.values())

    processed_sources.sort(
        key=source_sort_key,
        reverse=True,
    )

    return processed_sources[:max_sources]


def merge_duplicate_source(
    *,
    existing: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """
    合并两个被认为是同一来源的搜索结果。

    内容主体优先保留相关性分数较高的版本，
    但研究问题关联始终取并集。
    """

    existing_metadata = dict(existing.get("metadata", {}))
    candidate_metadata = dict(candidate.get("metadata", {}))

    existing_score = as_float(
        existing_metadata.get("score")
    )
    candidate_score = as_float(
        candidate_metadata.get("score")
    )

    if candidate_score > existing_score:
        preferred = {
            **candidate,
            "metadata": candidate_metadata,
        }
    else:
        preferred = {
            **existing,
            "metadata": existing_metadata,
        }

    preferred_metadata = dict(preferred.get("metadata", {}))

    preferred_metadata["research_questions"] = merge_unique_strings(
        existing_metadata.get("research_questions", []),
        candidate_metadata.get("research_questions", []),
    )

    preferred_metadata["research_goals"] = merge_unique_strings(
        existing_metadata.get("research_goals", []),
        candidate_metadata.get("research_goals", []),
    )

    preferred["metadata"] = preferred_metadata

    return preferred


def merge_unique_strings(
    first: Any,
    second: Any,
) -> list[str]:
    """
    按原始顺序合并字符串列表并去重。
    """

    merged: list[str] = []
    seen: set[str] = set()

    for value in [*as_string_list(first), *as_string_list(second)]:
        normalized = value.strip()

        if not normalized or normalized in seen:
            continue

        seen.add(normalized)
        merged.append(normalized)

    return merged


def as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    return [
        item
        for item in value
        if isinstance(item, str)
    ]


def as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def source_sort_key(
    source: dict[str, Any],
) -> tuple[float, int]:
    """
    第一阶段基础排序：
    1. Provider 返回的相关性分数；
    2. 是否拥有发布日期。

    后续 T08 可以在这里增加：
    - 来源权威度；
    - 新鲜度；
    - 原创性；
    - 内容完整度。
    """

    metadata = source.get("metadata", {})

    if not isinstance(metadata, dict):
        metadata = {}

    score = as_float(metadata.get("score"))
    has_published_at = int(
        source.get("published_at") is not None
    )

    return score, has_published_at


async def search_sources(
    state: ResearchState,
    runtime: Runtime[ResearchContext],
) -> dict[str, Any]:
    """
    注册到 LangGraph 的正式搜索节点。
    """

    search_tool = runtime.context.search_tool

    if search_tool is None:
        return {
            "raw_sources": [],
            "processed_sources": [],
            "status": "search_failed",
            "errors": [
                *state.get("errors", []),
                "ResearchContext.search_tool is not configured.",
            ],
        }

    return await search_sources_with_tool(
        state=state,
        search_tool=search_tool,
        max_concurrency=runtime.context.max_concurrency,
    )