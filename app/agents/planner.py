import logging
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Protocol, Any, cast

from app.models.research import ResearchQuestion, ResearchPlan, ResearchRequest
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class PlannerOutputError(ValueError):
    """
    Planner 输出不符合业务要求。

    与网络错误不同，这类错误表示：
    - 问题数量不正确；
    - 问题重复；
    - 来源列表为空；
    - 输出无法通过 Pydantic 校验。
    """


@dataclass
class PlannerExecution:
    """
    一次planner执行的完整结果
    """

    plan: ResearchPlan
    warnings: tuple[str, ...] = ()


class PlannerProtocol(Protocol):
    """
    create_plan节点依赖的Planner接口

    测试时可以哦注意fakePlanner
    生产环境是注入PlannerAgent
    """

    async def create_plan(
        self,
        request: ResearchRequest,
    ) -> PlannerExecution: ...


class StructuredPlannerModel(Protocol):
    """
    PlannerAgent所依赖的结构化模型接口
    """

    async def ainvoke(
        self,
        input: Any,
        config: Any | None = None,
        **kwargs: Any,
    ) -> Any: ...


PLANNER_PROMPT_MESSAGES = [
        (
            "system",
            """
你是 AI 技术调研系统中的研究规划器 Planner。

你的唯一职责是：
把用户提交的研究主题拆分成结构清晰、相互补充的研究问题。

你不能：
1. 直接回答研究主题；
2. 搜索网页；
3. 编造研究结果；
4. 编写最终报告；
5. 输出 Markdown 代码块。

输出要求：
1. 必须输出严格合法的 JSON；
2. JSON 必须符合给定的 ResearchPlan 数据结构；
3. 必须生成 {min_questions} 到 {max_questions} 个问题；
4. 每个问题必须包含 question、goal、preferred_sources；
5. 不同问题必须覆盖不同研究角度；
6. 不允许生成相同或近似重复的问题；
7. preferred_sources 应使用简短的英文来源类型标识；
8. 需要考虑研究类型、时间范围和用户来源偏好；
9. 输出语言为 {language}。
            """.strip(),
        ),
        (
            "human",
            """
请为下面的研究任务制定计划。

研究主题：
{topic}

研究类型：
{research_type}

开始时间：
{time_start}

结束时间：
{time_end}

用户偏好的来源：
{source_preferences}

输出 JSON 结构示例：

{{
  "questions": [
    {{
      "question": "需要研究的具体问题",
      "goal": "这个问题希望获得什么结果",
      "preferred_sources": [
        "official_docs",
        "github_release"
      ]
    }}
  ]
}}

注意：
这里只制定研究计划，不要直接回答研究问题。
            """.strip(),
        ),
]


class PlannerAgent:
    """
    使用结构化 LLM 输出生成研究计划。
    """

    def __init__(
        self,
        model: StructuredPlannerModel,
        *,
        min_questions: int = 3,
        max_questions: int = 5,
        output_retries: int = 1,
        duplicate_threshold: float = 0.95,
    ) -> None:
        if min_questions < 1:
            raise ValueError("min_questions must be at least 1")

        if min_questions > max_questions:
            raise ValueError("min_questions must not be greater than max_questions")

        if output_retries < 0:
            raise ValueError("output_retries must be non-negative")

        if not 0 <= duplicate_threshold <= 1:
            raise ValueError("duplicate_threshold must be between 0 and 1")

        self._model = model
        self._min_questions = min_questions
        self._max_questions = max_questions
        self._output_retries = output_retries
        self._duplicate_threshold = duplicate_threshold

    async def create_plan(
        self,
        request: ResearchRequest,
    ) -> PlannerExecution:
        """
        创建研究计划。

        流程：
        1. 构造 Prompt；
        2. 调用结构化模型；
        3. 使用 ResearchPlan 校验；
        4. 清理来源字段；
        5. 检查重复问题；
        6. 输出失败时有限重试；
        7. 连续失败时使用规则计划降级。
        """

        attempts = self._output_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                plan = await self._invoke_model(request)
                validated_plan = self._validate_plan(plan)
                return PlannerExecution(
                    plan=validated_plan,
                )
            except Exception:
                logger.warning(
                    "Planner output validation failed on attempt %s/%s",
                    attempt,
                    attempts,
                    exc_info=True,
                )
        fallback_plan = build_fallback_plan(request)
        return PlannerExecution(
            plan=fallback_plan,
            warnings=("Planner 模型连续输出无效，已使用规则计划降级。",),
        )

    async def _invoke_model(
        self,
        request: ResearchRequest,
    ) -> ResearchPlan:
        """
        调用模型并将结果转换成 ResearchPlan
        """

        try:
            from langchain_core.prompts import ChatPromptTemplate
        except ImportError as exc:
            raise RuntimeError(
                "LangChain dependencies are required for online planner execution"
            ) from exc

        planner_prompt = ChatPromptTemplate.from_messages(PLANNER_PROMPT_MESSAGES)
        messages = planner_prompt.format_messages(
            min_questions=self._min_questions,
            max_questions=self._max_questions,
            language=request.language,
            topic=request.topic,
            research_type=request.research_type,
            time_start=(
                request.time_start.isoformat() if request.time_start is not None else "未指定"
            ),
            time_end=(request.time_end.isoformat() if request.time_end is not None else "未指定"),
            source_preferences=(
                ", ".join(request.source_preferences) if request.source_preferences else "未指定"
            ),
        )

        raw_plan = await self._model.ainvoke(messages)
        if isinstance(raw_plan, ResearchPlan):
            return raw_plan

        return ResearchPlan.model_validate(raw_plan)

    def _validate_plan(
        self,
        plan: ResearchPlan,
    ) -> ResearchPlan:
        """
        执行业务层校验。

        Pydantic 负责字段格式，
        本方法负责重复问题等业务规则。
        """
        normalized_questions: list[ResearchQuestion] = []

        for question in plan.questions:
            normalized_sources = self._normalize_sources(question.preferred_sources)
            if not normalized_sources:
                raise PlannerOutputError("preferred_sources must not be empty")
            normalized_question = question.model_copy(
                update={
                    "preferred_sources": normalized_sources,
                }
            )

            if self._is_duplicate(
                normalized_question,
                normalized_questions,
            ):
                continue
            normalized_questions.append(normalized_question)
        question_count = len(normalized_questions)

        if not (self._min_questions <= question_count <= self._max_questions):
            raise PlannerOutputError(
                "Planner must return "
                f"{self._min_questions} to "
                f"{self._max_questions} unique questions, "
                f"but received {question_count}"
            )
        return ResearchPlan(
            questions=normalized_questions,
        )

    def _is_duplicate(
        self,
        candidate: ResearchQuestion,
        existing_questions: list[ResearchQuestion],
    ) -> bool:
        """
        判断问题是否近似重复。

        第一阶段使用确定性字符串相似度，
        后续可以替换为 embedding 相似度。
        """
        candidate_text = normalize_question_text(candidate.question)
        for existing in existing_questions:
            existing_text = normalize_question_text(existing.question)
            similarity = SequenceMatcher(None, candidate_text, existing_text).ratio()
            if similarity >= self._duplicate_threshold:
                return True
        return False

    @staticmethod
    def _normalize_sources(
        sources: list[str],
    ) -> list[str]:
        """
        清理来源类型并保持原顺序去重。
        """
        result: list[str] = []
        seen: set[str] = set()

        for source in sources:
            normalized = source.strip().lower()
            if not normalized:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result


def normalize_question_text(
    text: str,
) -> str:
    """
    删除空格、标点并转成小写。

    中文字符的 isalnum() 返回 True，
    因此中文内容会被保留。
    """

    return "".join(character.lower() for character in text if character.isalnum())


def merge_source_preferences(
    request: ResearchRequest,
    default_sources: list[str],
) -> list[str]:
    """
    合并来源偏好。
    """

    merged: list[str] = []
    seen: set[str] = set()

    for source in [
        *request.source_preferences,
        *default_sources,
    ]:
        normalized = source.strip().lower()

        if not normalized or normalized in seen:
            continue

        seen.add(normalized)
        merged.append(normalized)
    return merged[:8]


def build_fallback_plan(
    request: ResearchRequest,
) -> ResearchPlan:
    """
    模型不可用或输出持续无效时，
    使用规则模板生成最小可用研究计划。
    """

    topic = request.topic

    if request.research_type == "learning_guide":
        templates = [
            (
                f"学习 {topic} 需要掌握哪些前置知识？",
                "明确学习该技术前需要具备的基础概念和能力",
                ["official_docs", "tutorials"],
            ),
            (
                f"{topic} 的核心概念和推荐学习顺序是什么？",
                "建立从基础概念到核心能力的知识路线",
                ["official_docs", "technical_books"],
            ),
            (
                f"学习 {topic} 可以完成哪些实战项目？",
                "设计能够验证学习成果的练习和项目",
                ["github", "official_examples"],
            ),
        ]

    elif request.research_type == "github_analysis":
        templates = [
            (
                f"{topic} 项目的定位和主要功能是什么？",
                "理解项目要解决的问题、目标用户和主要能力",
                ["github_readme", "official_docs"],
            ),
            (
                f"{topic} 的目录结构和核心代码如何组织？",
                "识别核心模块、调用关系和关键入口文件",
                ["github_tree", "source_code"],
            ),
            (
                f"{topic} 的维护状态、优缺点和学习价值如何？",
                "分析项目活跃度、工程质量、限制和阅读建议",
                ["github_commit", "github_issue", "github_release"],
            ),
        ]

    elif request.research_type == "daily_brief":
        templates = [
            (
                f"{topic} 在指定时间范围内有哪些官方发布？",
                "整理官方文档、产品更新和版本发布",
                ["official_blog", "official_docs"],
            ),
            (
                f"{topic} 在指定时间范围内有哪些重要开源更新？",
                "发现值得关注的仓库、Release 和代码变化",
                ["github_release", "github_commit"],
            ),
            (
                f"{topic} 在指定时间范围内有哪些重要研究进展？",
                "整理新论文、技术报告和研究成果",
                ["papers", "research_blog"],
            ),
        ]

    else:
        templates = [
            (
                f"{topic} 的技术背景、核心概念和研究边界是什么?",
                "明确研究对象、关键术语及报告覆盖范围",
                ["official_docs", "papers"],
            ),
            (
                f"{topic} 目前有哪些主要进展和重要变化?",
                "整理重要版本、能力、事件和时间线",
                ["official_docs", "github_release", "papers"],
            ),
            (
                f"{topic} 对实际开发有哪些影响、限制和风险?",
                "分析工程价值、适用场景和潜在问题",
                ["official_docs", "github", "technical_blog"],
            ),
        ]

    questions = [
        ResearchQuestion(
            question=question,
            goal=goal,
            preferred_sources=merge_source_preferences(
                request,
                sources,
            ),
        )
        for question, goal, sources in templates
    ]

    return ResearchPlan(
        questions=questions,
    )


def build_deepseek_planner(
    settings: Settings | None = None,
) -> PlannerAgent:
    """
    根据项目配置创建真实 DeepSeek Planner。
    """

    try:
        from langchain_deepseek import ChatDeepSeek
    except ImportError as exc:
        raise RuntimeError(
            "langchain-deepseek is required for online planner execution"
        ) from exc

    resolved_settings = settings or get_settings()

    if resolved_settings.deepseek_api_key is None:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")

    api_key = resolved_settings.deepseek_api_key.get_secret_value()

    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is empty")

    chat_model = ChatDeepSeek(
        model=resolved_settings.llm_model,
        api_key=api_key,
        api_base=resolved_settings.deepseek_api_base,
        temperature=resolved_settings.llm_temperature,
        max_tokens=resolved_settings.llm_max_tokens,
        timeout=resolved_settings.llm_timeout_seconds,
        max_retries=resolved_settings.llm_max_retries,
        # Planner 主要需要稳定的结构化输出，
        # 第一阶段关闭思考模式，降低延迟和输出波动。
        extra_body={
            "thinking": {
                "type": "disabled",
            }
        },
    )

    structured_model = chat_model.with_structured_output(
        ResearchPlan,
        method="json_mode",
    )

    return PlannerAgent(
        model=cast(
            StructuredPlannerModel,
            structured_model,
        ),
        min_questions=resolved_settings.research_min_questions,
        max_questions=resolved_settings.research_max_questions,
        output_retries=1,
    )
