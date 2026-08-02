from typing import Any

from langgraph.runtime import Runtime

from app.agents.writer import WriterProtocol
from app.graph.context import ResearchContext
from app.graph.nodes.create_plan import build_request_from_state
from app.graph.state import ResearchState
from app.models.source import SourceDocument
from app.services.citation_service import validate_report_citations

from app.services.report_renderer import render_report_markdown


async def write_report_with_writer(
    state: ResearchState,
    writer: WriterProtocol,
) -> dict[str, Any]:
    """
    可独立测试的 Writer 节点核心逻辑。

    不依赖 LangGraph Runtime，
    测试时可以直接传入 FakeWriter。
    """

    raw_sources = state.get(
        "processed_sources",
        [],
    )

    if not raw_sources:
        return {
            "status": "write_failed",
            "errors": [
                *state.get("errors", []),
                (
                    "Cannot write report without processed sources."
                ),
            ],
        }

    try:
        sources = [
            SourceDocument.model_validate(
                source
            )
            for source in raw_sources
        ]

        request = build_request_from_state(
            state
        )

        execution = await writer.write_report(
            request=request,
            questions=state.get(
                "research_questions",
                [],
            ),
            sources=sources,
        )

        # 即使 Writer 内部已经校验，
        # 节点仍然做一次防御性校验。
        # 这样 FakeWriter 或其他 Writer
        # 也无法绕过来源真实性检查。
        validate_report_citations(
            execution.report,
            sources,
        )

        markdown = render_report_markdown(
            execution.report
        )

    except ValueError as exc:
        return {
            "status": "write_failed",
            "errors": [
                *state.get("errors", []),
                (
                    "Writer failed: "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            ],
        }

    report_payload = (
        execution.report.model_dump(
            mode="json"
        )
    )

    update: dict[str, Any] = {
        "draft_report": report_payload,
        "final_report": report_payload,
        "report_markdown": markdown,
        "status": "report_completed",
    }

    if execution.warnings:
        # 你当前的 State 没有 warnings 字段，
        # 暂时沿用 errors 保存降级信息。
        # 后续建议拆分 warnings/errors。
        update["errors"] = [
            *state.get("errors", []),
            *execution.warnings,
        ]

    return update


async def write_report(
    state: ResearchState,
    runtime: Runtime[ResearchContext],
) -> dict[str, Any]:
    """正式注册到 LangGraph 的 Writer 节点。"""

    writer = runtime.context.writer

    if writer is None:
        return {
            "status": "write_failed",
            "errors": [
                *state.get("errors", []),
                (
                    "ResearchContext.writer is not configured."
                ),
            ],
        }

    return await write_report_with_writer(
        state=state,
        writer=writer,
    )