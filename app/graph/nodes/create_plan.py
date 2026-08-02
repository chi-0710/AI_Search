from datetime import date
from typing import Any

from langgraph.runtime import Runtime

from app.agents.planner import (
    PlannerExecution,
    PlannerProtocol,
)
from app.graph.context import ResearchContext
from app.graph.state import ResearchState
from app.models.research import ResearchRequest

def parse_state_date(
    value:str|None,
)->date|None:
    if not value:
        return None
    return date.fromisoformat(value)


def build_request_from_state(
    state: ResearchState,
) -> ResearchRequest:
    """
    从规范化后的 State 构造 ResearchRequest。
    """

    return ResearchRequest(
        topic=state["topic"],
        research_type=state["research_type"],
        language=state["language"],
        time_start=parse_state_date(
            state.get("time_start"),
        ),
        time_end=parse_state_date(
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


async def create_plan_with_planner(
    state: ResearchState,
    planner: PlannerProtocol,
) -> dict[str, Any]:
    """
    可独立测试的 Planner 节点核心逻辑。

    该函数不依赖 LangGraph Runtime，
    因此单元测试可以直接传入 FakePlanner。
    """

    request = build_request_from_state(state)

    execution: PlannerExecution = (
        await planner.create_plan(request)
    )

    update: dict[str, Any] = {
        "research_questions": execution.plan.questions,
        "status": "plan_completed",
    }

    if execution.warnings:
        update["errors"] = [
            *state.get("errors", []),
            *execution.warnings,
        ]

    return update


async def create_plan(
    state: ResearchState,
    runtime: Runtime[ResearchContext],
) -> dict[str, Any]:
    """
    正式注册到 LangGraph 的节点。
    """

    return await create_plan_with_planner(
        state=state,
        planner=runtime.context.planner,
    )