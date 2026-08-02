from datetime import date

import pytest
from langgraph.runtime import Runtime

from app.agents.planner import (
    PlannerExecution,
)
from app.graph.context import ResearchContext
from app.graph.nodes.create_plan import (
    build_request_from_state,
    create_plan,
    create_plan_with_planner,
)
from app.graph.state import ResearchState
from app.models.research import (
    ResearchPlan,
    ResearchQuestion,
    ResearchRequest,
)


class FakePlanner:
    """
    节点测试只关心节点是否正确调用 Planner,
    不关心 LLM、Prompt 和重试逻辑。F
    """

    def __init__(
        self,
        execution: PlannerExecution,
    ) -> None:
        self._execution = execution
        self.received_request: ResearchRequest | None = None

    async def create_plan(
        self,
        request: ResearchRequest,
    ) -> PlannerExecution:
        self.received_request = request
        return self._execution


def build_state() -> ResearchState:
    return {
        "thread_id": "thread_001",
        "task_id": "task_001",
        "topic": "分析 LangGraph 最近三个月的重要更新",
        "research_type": "deep_report",
        "language": "zh-CN",
        "time_start": "2026-04-27",
        "time_end": "2026-07-27",
        "source_preferences": [
            "official_docs",
            "github_release",
        ],
        "max_sources": 15,
        "research_questions": [],
        "raw_sources": [],
        "processed_sources": [],
        "revision_count": 0,
        "status": "request_normalized",
        "errors": [],
        "token_usage": 0,
        "estimated_cost": 0.0,
    }


def build_plan() -> ResearchPlan:
    return ResearchPlan(
        questions=[
            ResearchQuestion(
                question="LangGraph 的核心能力是什么?",
                goal="整理核心能力",
                preferred_sources=["official_docs"],
            ),
            ResearchQuestion(
                question="LangGraph 最近有哪些版本变化?",
                goal="整理版本变化",
                preferred_sources=["github_release"],
            ),
            ResearchQuestion(
                question="LangGraph 有哪些工程限制?",
                goal="整理限制和风险",
                preferred_sources=["github_issue"],
            ),
        ]
    )


@pytest.mark.unit
def test_build_request_from_state() -> None:
    request = build_request_from_state(
        build_state()
    )

    assert request.topic == (
        "分析 LangGraph 最近三个月的重要更新"
    )
    assert request.time_start == date(2026, 4, 27)
    assert request.time_end == date(2026, 7, 27)
    assert request.max_sources == 15
    assert request.source_preferences == [
        "official_docs",
        "github_release",
    ]


@pytest.mark.unit
async def test_create_plan_with_fake_planner() -> None:
    execution = PlannerExecution(
        plan=build_plan(),
    )
    planner = FakePlanner(execution)
    state = build_state()

    update = await create_plan_with_planner(
        state=state,
        planner=planner,
    )

    assert planner.received_request is not None
    assert planner.received_request.topic == state["topic"]

    assert update["status"] == "plan_completed"
    assert update["research_questions"] == (
        execution.plan.questions
    )
    assert "errors" not in update

    # 节点应返回增量,不直接修改原 State。
    assert state["status"] == "request_normalized"
    assert state["research_questions"] == []


@pytest.mark.unit
async def test_preserve_existing_errors_when_fallback_used() -> None:
    execution = PlannerExecution(
        plan=build_plan(),
        warnings=("Planner 已使用 fallback",),
    )
    planner = FakePlanner(execution)
    state = build_state()
    state["errors"] = ["已有错误"]

    update = await create_plan_with_planner(
        state=state,
        planner=planner,
    )

    assert update["errors"] == [
        "已有错误",
        "Planner 已使用 fallback",
    ]


@pytest.mark.unit
async def test_create_plan_uses_runtime_context() -> None:
    execution = PlannerExecution(
        plan=build_plan(),
    )
    planner = FakePlanner(execution)

    runtime = Runtime(
        context=ResearchContext(
            planner=planner,
        )
    )

    update = await create_plan(
        state=build_state(),
        runtime=runtime,
    )

    assert update["status"] == "plan_completed"
    assert planner.received_request is not None


@pytest.mark.unit
def test_reject_invalid_state_date() -> None:
    state = build_state()
    state["time_start"] = "2026/04/27"

    with pytest.raises(ValueError):
        build_request_from_state(state)