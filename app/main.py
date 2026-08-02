import argparse
import asyncio
import json
import logging
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from app.agents.planner import build_deepseek_planner, build_fallback_plan
from app.config import get_settings
from app.models.research import ResearchRequest
from app.tools.search import TavilySearchParams, build_tavily_search_tool
from app.agents.writer import build_deepseek_writer
from pathlib import Path


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    message: str


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )


def print_json(payload: Any) -> None:
    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


def check_configuration() -> CheckResult:
    try:
        settings = get_settings()
    except ValidationError as exc:
        return CheckResult(
            name="configuration",
            ok=False,
            message=f"配置校验失败: {exc}",
        )

    return CheckResult(
        name="configuration",
        ok=True,
        message=f"{settings.app_name} 已加载，环境为 {settings.app_env}",
    )


def check_fallback_planner() -> CheckResult:
    request = ResearchRequest(
        topic="AI Agent 在线搜索能力验证",
        research_type="deep_report",
    )
    plan = build_fallback_plan(request)

    return CheckResult(
        name="fallback_planner",
        ok=len(plan.questions) >= 3,
        message=f"规则 Planner 可用，生成 {len(plan.questions)} 个研究问题",
    )


async def run_health_check() -> int:
    results = [
        check_configuration(),
        check_fallback_planner(),
    ]

    print_json(
        {
            "ok": all(result.ok for result in results),
            "checks": [asdict(result) for result in results],
        }
    )

    return 0 if all(result.ok for result in results) else 1


async def run_plan(args: argparse.Namespace) -> int:
    request = ResearchRequest(
        topic=args.topic,
        research_type=args.research_type,
        language=args.language,
    )

    if args.online:
        planner = build_deepseek_planner()
        execution = await planner.create_plan(request)
        payload: dict[str, Any] = {
            "ok": True,
            "mode": "online",
            "plan": execution.plan.model_dump(),
            "warnings": execution.warnings,
        }
    else:
        plan = build_fallback_plan(request)
        payload = {
            "ok": True,
            "mode": "local_fallback",
            "plan": plan.model_dump(),
            "warnings": [],
        }

    print_json(payload)
    return 0


async def run_search(args: argparse.Namespace) -> int:
    tool = build_tavily_search_tool()
    try:
        result = await tool.search(
            TavilySearchParams(
                query=args.query,
                max_results=args.max_results,
                search_depth=args.search_depth,
                topic=args.topic,
            )
        )
    finally:
        await tool.aclose()

    print_json(result.model_dump())
    return 0 if result.success else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-search-agent",
        description="AI Search Agent 项目入口",
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser(
        "health",
        help="检查配置和本地核心功能是否可用",
    )

    plan_parser = subparsers.add_parser(
        "plan",
        help="生成研究计划；默认使用本地降级规则，--online 调用真实模型",
    )
    plan_parser.add_argument("topic", help="研究主题")
    plan_parser.add_argument(
        "--research-type",
        default="deep_report",
        choices=["daily_brief", "deep_report", "learning_guide", "github_analysis"],
    )
    plan_parser.add_argument("--language", default="zh-CN")
    plan_parser.add_argument(
        "--online",
        action="store_true",
        help="调用真实 LLM Planner，需要配置 DEEPSEEK_API_KEY",
    )

    search_parser = subparsers.add_parser(
        "search",
        help="发起一次真实在线搜索，需要配置 WEB_SEARCH_PROVIDER=tavily 和 WEB_SEARCH_API_KEY",
    )
    search_parser.add_argument("query", help="搜索关键词")
    search_parser.add_argument("--max-results", type=int, default=3)
    search_parser.add_argument(
        "--search-depth",
        default="basic",
        choices=["basic", "advanced", "fast", "ultra-fast"],
    )

    search_parser.add_argument(
        "--topic",
        default="general",
        choices=["general", "news", "finance"],
    )

    research_parser = subparsers.add_parser(
        "research",
        help="执行在线研究：生成计划、搜索资料并汇总来源",
    )

    research_parser.add_argument(
        "topic",
        help="需要研究的主题",
    )
    research_parser.add_argument(
        "--research-type",
        default="deep_report",
        choices=[
            "daily_brief",
            "deep_report",
            "learning_guide",
            "github_analysis",
        ],
        help="研究报告类型",
    )
    research_parser.add_argument(
        "--language",
        default="zh-CN",
        help="输出语言，默认为中文",
    )
    research_parser.add_argument(
        "--max-sources",
        type=int,
        default=15,
        help="最终保留的最大来源数量，至少为 5",
    )

    research_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="可选的 Markdown 输出文件路径",
    )

    return parser


async def async_main(argv: Sequence[str] | None = None) -> int:
    settings = get_settings()
    configure_logging(settings.log_level)

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in {None, "health"}:
        return await run_health_check()

    if args.command == "plan":
        return await run_plan(args)

    if args.command == "search":
        return await run_search(args)

    if args.command == "research":
        return await run_research(args)
    parser.print_help()
    return 2


async def run_research(args: argparse.Namespace) -> int:
    from app.graph.context import ResearchContext
    from app.graph.state import ResearchState
    from app.graph.workflow import build_research_graph

    settings = get_settings()
    planner = build_deepseek_planner(settings)
    writer = build_deepseek_writer(settings)
    search_tool = build_tavily_search_tool(settings)

    initial_state: ResearchState = {
        "thread_id": f"thread_{uuid4().hex}",
        "task_id": f"task_{uuid4().hex}",
        "topic": args.topic,
        "research_type": args.research_type,
        "language": args.language,
        "source_preferences": [],
        "max_sources": args.max_sources,
        "research_questions": [],
        "raw_sources": [],
        "processed_sources": [],
        "revision_count": 0,
        "status": "created",
        "errors": [],
        "token_usage": 0,
        "estimated_cost": 0.0,
    }

    graph = build_research_graph()

    try:
        result = await graph.ainvoke(
            initial_state,
            context=ResearchContext(
                planner=planner,
                search_tool=search_tool,
                writer=writer,
                max_concurrency=(settings.research_max_concurrency),
            ),
        )
    finally:
        await search_tool.aclose()

    markdown = result.get("report_markdown", "")

    ok = result.get("status") == "report_completed" and bool(markdown)

    if args.output is not None and markdown:
        args.output.write_text(
            markdown,
            encoding="utf-8",
        )

    print_json(
        {
            "ok": ok,
            "status": result["status"],
            "questions": [
                question.model_dump() for question in result["research_questions"]
            ],
            "source_count": len(
                result.get(
                    "processed_sources",
                    [],
                )
            ),
            "report": result.get("final_report"),
            "markdown": markdown,
            "output_file": (str(args.output) if args.output is not None else None),
            "errors": result.get(
                "errors",
                [],
            ),
        }
    )

    return 0 if ok else 1


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
