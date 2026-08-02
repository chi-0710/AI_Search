from typing import Any
import pytest

from app.agents.planner import PlannerAgent,build_deepseek_planner,build_fallback_plan
from app.config import Settings
from app.models.research import ResearchRequest,ResearchType

class FakeStructuredModel:
    """
    按顺序返回预设响应的假结构化模型。

    它不会访问网络,用于验证:
    - 正常输出;
    - 重试;
    - 非法输出;
    - 模型异常;
    - fallback。
    """   
    def __init__(self, responses: list[dict]):
        self._responses = responses
        self.call_count = 0
        self.last_input:Any=None

    async def ainvoke(
        self,
        input:Any,
        config:Any|None=None,
        **kwargs:Any,
    )->Any:
        del config,kwargs

        self.call_count +=1
        self.last_input = input
        
        if not self._responses:
            raise AssertionError(
                "FakeStructuredModel 没有剩余响应"
            )

        response = self._responses.pop(0)
        
        if isinstance(response,Exception):
            raise response
        return response

def build_request(
    research_type:ResearchType="deep_report",
)->ResearchRequest:
    return ResearchRequest(
        topic="分析 LangGraph 最近三个月的重要更新",
        research_type=research_type,
        language="zh-CN",
        source_preferences=["Official_Docs"],
    )

def build_valid_plan_payload()->dict[str,Any]:
    return {
        "questions": [
            {
                "question": "LangGraph 当前的核心能力是什么?",
                "goal": "整理核心概念和主要能力",
                "preferred_sources": [
                    " Official_Docs ",
                    "official_docs",
                    "GitHub_Release",
                ],
            },
            {
                "question": "LangGraph 最近有哪些重要版本变化?",
                "goal": "整理主要版本及其变化",
                "preferred_sources": [
                    "github_release",
                    "official_blog",
                ],
            },
            {
                "question": "LangGraph 在工程实践中有哪些限制?",
                "goal": "分析适用范围、风险和限制",
                "preferred_sources": [
                    "official_docs",
                    "github_issue",
                ],
            },
        ]
    }

@pytest.mark.unit
async def test_create_valid_plan()->None:
    model=FakeStructuredModel([
        build_valid_plan_payload(),
    ])
    planner = PlannerAgent(
        model=model,
        output_retries=1,
    )

    execution=await planner.create_plan(
        build_request(),
    )
    assert model.call_count==1
    assert execution.warnings==()
    assert len(execution.plan.questions)==3

    first_question=execution.plan.questions[0]
    assert first_question.preferred_sources==[
        "official_docs",
        "github_release",
    ]

@pytest.mark.unit
async def test_retry_then_return_valid_plan()->None:
    model=FakeStructuredModel([
        {
            "questions":[],
        },
        build_valid_plan_payload(),
    ])
    planner=PlannerAgent(
        model=model,
        output_retries=1,
    )

    execution=await planner.create_plan(
        build_request(),
    )
    assert model.call_count==2
    assert execution.warnings==()
    assert len(execution.plan.questions)==3
    

@pytest.mark.unit
async def test_use_fallback_after_all_attempts_fail() -> None:
    model = FakeStructuredModel([
        ValueError("第一次模型输出失败"),
        ValueError("第二次模型输出失败"),
    ])
    planner = PlannerAgent(
        model=model,
        output_retries=1,
    )

    execution = await planner.create_plan(
        build_request()
    )

    assert model.call_count == 2
    assert len(execution.plan.questions) == 3
    assert execution.warnings == (
        "Planner 模型连续输出无效,已使用规则计划降级。",
    )

@pytest.mark.unit
async def test_duplicate_questions_trigger_fallback() -> None:
    payload = build_valid_plan_payload()

    first_question = payload["questions"][0]
    payload["questions"][2] = first_question.copy()

    model = FakeStructuredModel([payload])
    planner = PlannerAgent(
        model=model,
        output_retries=0,
    )

    execution = await planner.create_plan(
        build_request()
    )

    assert model.call_count == 1
    assert execution.warnings
    assert len(execution.plan.questions) == 3


@pytest.mark.unit
async def test_empty_preferred_sources_trigger_fallback() -> None:
    payload = build_valid_plan_payload()
    payload["questions"][0]["preferred_sources"] = []

    model = FakeStructuredModel([payload])
    planner = PlannerAgent(
        model=model,
        output_retries=0,
    )

    execution = await planner.create_plan(
        build_request()
    )

    assert model.call_count == 1
    assert execution.warnings


@pytest.mark.unit
@pytest.mark.parametrize(
    "research_type",
    [
        "daily_brief",
        "deep_report",
        "learning_guide",
        "github_analysis",
    ],
)
def test_build_fallback_for_every_research_type(
    research_type: ResearchType,
) -> None:
    request = build_request(research_type)

    plan = build_fallback_plan(request)

    assert len(plan.questions) == 3

    for question in plan.questions:
        assert question.question
        assert question.goal
        assert question.preferred_sources


@pytest.mark.unit
def test_fallback_merges_user_source_preferences() -> None:
    request = ResearchRequest(
        topic="分析 LangGraph 最近三个月的重要更新",
        research_type="deep_report",
        source_preferences=[
            "CUSTOM_SOURCE",
            "official_docs",
        ],
    )

    plan = build_fallback_plan(request)

    for question in plan.questions:
        assert question.preferred_sources[0] == (
            "custom_source"
        )
        assert len(question.preferred_sources) == len(
            set(question.preferred_sources)
        )


@pytest.mark.unit
def test_reject_invalid_planner_configuration() -> None:
    model = FakeStructuredModel([
        build_valid_plan_payload(),
    ])

    with pytest.raises(ValueError):
        PlannerAgent(
            model=model,
            min_questions=0,
        )

    with pytest.raises(ValueError):
        PlannerAgent(
            model=model,
            min_questions=5,
            max_questions=3,
        )

    with pytest.raises(ValueError):
        PlannerAgent(
            model=model,
            duplicate_threshold=1.1,
        )


@pytest.mark.unit
def test_reject_missing_deepseek_api_key() -> None:
    settings = Settings(
        _env_file=None,
        deepseek_api_key=None,
    )

    with pytest.raises(
        RuntimeError,
        match="DEEPSEEK_API_KEY is not configured",
    ):
        build_deepseek_planner(settings)