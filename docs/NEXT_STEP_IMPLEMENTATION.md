# 下一步实施方案：先稳定搜索闭环，再接 Writer

> 基线日期：2026-08-01  
> 目标：把当前 `normalize_request → create_plan → search_sources` 从“代码可见”推进到“可重复验收”，然后再增加 Writer 和 Markdown。

## 1. 为什么先不直接开发数据库或 Reviewer

当前最短路径已经到达搜索节点，但全量测试仍无法收集，Tavily 没有 Mock 测试，去重逻辑仍位于 Tool/Graph Node 中。此时直接增加数据库、RAG 或 Reviewer，会把环境、搜索、数据处理和写作问题叠在一起，故障很难定位。

建议顺序：

1. 修复环境和现有质量门禁。
2. 给 Tavily 与去重补稳定测试。
3. 将 URL/哈希/去重下沉到 Services。
4. 实现确定性的 Citation 校验和 Markdown Renderer。
5. 最后接 Writer，并把 write_report 加入 LangGraph。

## 2. P0：让现有代码可重复验收

### 2.1 安装项目环境

已有 `ai-search` Conda 环境，但其中没有项目依赖。进入项目根目录后执行：

```powershell
conda activate ai-search
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest -p no:cacheprovider -q
python -m ruff check app tests
python -m ruff format --check app tests
python -m mypy app
```

验收点：上述四条质量命令都必须成功，才能勾选 T01/T05 的质量项。

### 2.2 修复三个已确认的小问题

`tests/unit/test_planner.py` 的期望值应与实现统一使用中文标点：

```python
assert execution.warnings == (
    "Planner 模型连续输出无效，已使用规则计划降级。",
)
```

`app/tools/base.py` 删除未使用的导入：

```python
# 删除这一行
from email.policy import default
```

`app/tools/search.py` 明确构造 `HttpUrl`，关闭当前已知的 mypy 类型错误：

```python
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

# TavilySearchTool._build_document 内
return SourceDocument(
    source_id=build_source_id(canonical_url),
    title=title,
    url=HttpUrl(canonical_url),
    source_type="web",
    published_at=parse_published_at(raw_published_date),
    summary=summary,
    clean_content=raw_content,
    content_hash=build_content_hash(content_for_hash),
    metadata=metadata,
)
```

## 3. T07：补 Tavily 的稳定 Mock 测试

新增 `tests/unit/test_search_tool.py`。测试使用 `httpx.MockTransport`，不会访问真实网络，也不会消耗 Tavily 配额。

```python
import asyncio
from datetime import date

import httpx

from app.tools.search import (
    TavilySearchParams,
    TavilySearchTool,
    canonicalize_url,
)


def run(coro):
    return asyncio.run(coro)


def test_normalize_search_params() -> None:
    params = TavilySearchParams(
        query="  LangGraph   persistence  ",
        max_results=5,
        include_domains=[
            "https://docs.langchain.com/oss/python/langgraph/",
            "DOCS.LANGCHAIN.COM",
        ],
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
    )

    assert params.query == "LangGraph persistence"
    assert params.include_domains == ["docs.langchain.com"]
    assert params.to_payload()["start_date"] == "2026-07-01"
    assert params.to_payload()["end_date"] == "2026-07-31"


def test_canonicalize_url_removes_tracking_data() -> None:
    value = canonicalize_url(
        "HTTPS://Example.COM:443/docs/?utm_source=test&b=2&a=1#section"
    )

    assert value == "https://example.com/docs?a=1&b=2"


def test_search_maps_successful_response() -> None:
    async def scenario():
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["Authorization"] == "Bearer test-key"
            return httpx.Response(
                200,
                json={
                    "request_id": "request-1",
                    "results": [
                        {
                            "title": "LangGraph docs",
                            "url": "https://example.com/docs?utm_source=test",
                            "content": "StateGraph documentation",
                            "score": 0.92,
                            "published_date": "2026-07-20T08:00:00Z",
                        }
                    ],
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            tool = TavilySearchTool(
                api_key="test-key",
                client=client,
                retry_delay_seconds=0,
            )
            return await tool.search(
                TavilySearchParams(query="LangGraph docs")
            )

    result = run(scenario())

    assert result.success is True
    assert result.error is None
    assert len(result.items) == 1
    assert str(result.items[0].url) == "https://example.com/docs"
    assert result.items[0].metadata["score"] == 0.92


def test_empty_results_are_successful() -> None:
    async def scenario():
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"results": []})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            tool = TavilySearchTool(api_key="test-key", client=client)
            return await tool.run("no result query")

    result = run(scenario())

    assert result.success is True
    assert result.items == []


def test_timeout_is_retried_and_sanitized() -> None:
    calls = 0

    async def scenario():
        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            raise httpx.ReadTimeout("secret upstream detail", request=request)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            tool = TavilySearchTool(
                api_key="do-not-leak",
                client=client,
                max_retries=1,
                retry_delay_seconds=0,
            )
            return await tool.run("timeout query")

    result = run(scenario())

    assert calls == 2
    assert result.success is False
    assert result.error == "tavily request timed out"
    assert "do-not-leak" not in result.error
    assert "secret upstream detail" not in result.error
```

这组测试覆盖：参数规范化、URL 标准化、正常映射、空结果、超时、有限重试和错误脱敏。完成后再增加一个 `@pytest.mark.external` 的真实 Provider 冒烟测试，默认测试套件不运行它。

## 4. T08：把确定性处理从 Tool/Node 下沉到 Services

建议新增：

```text
app/services/
├── __init__.py
├── source_normalizer.py
└── source_deduplicator.py
```

职责边界：

- `TavilySearchTool`：只负责 HTTP、重试、Provider 响应解析。
- `source_normalizer`：负责 canonical URL、source_id、日期与哈希。
- `source_deduplicator`：负责 URL/哈希去重、问题关联合并、稳定排序和数量统计。
- `search_sources`：只做并发调度和 State 增量更新。

推荐让去重服务返回统计信息，而不是只返回列表：

```python
from dataclasses import dataclass

from app.models.source import SourceDocument


@dataclass(frozen=True)
class DeduplicationResult:
    sources: tuple[SourceDocument, ...]
    input_count: int
    duplicate_count: int
    retained_count: int


def deduplicate_sources(
    sources: list[SourceDocument],
    *,
    max_sources: int,
) -> DeduplicationResult:
    # 1. canonical_url 相同：合并
    # 2. content_hash 相同：合并
    # 3. 保留分数更高的主体数据
    # 4. research_questions/research_goals 取有序并集
    # 5. 按 score、published_at、source_id 稳定排序
    ...
```

这里额外加入 `source_id` 作为最终排序键，可以避免 Provider 返回顺序变化导致 Markdown 引用顺序漂移。

## 5. T09：先实现确定性引用校验和 Markdown Renderer

在接 LLM Writer 前，先完成两个普通 Python 模块。这样即使 Writer 输出错误，也能在进入 State 前拒绝伪造 URL 或无效 citation_id。

### 5.1 引用校验

新增 `app/services/citation_service.py`：

```python
from app.models.report import ReportSchema
from app.models.source import SourceDocument


class CitationValidationError(ValueError):
    pass


def validate_report_citations(
    report: ReportSchema,
    sources: list[SourceDocument],
) -> None:
    source_urls = {
        source.source_id: str(source.url).rstrip("/")
        for source in sources
    }
    citation_ids: set[str] = set()

    for citation in report.citations:
        if citation.citation_id in citation_ids:
            raise CitationValidationError(
                f"duplicate citation_id: {citation.citation_id}"
            )
        citation_ids.add(citation.citation_id)

        expected_url = source_urls.get(citation.source_id)
        if expected_url is None:
            raise CitationValidationError(
                f"unknown source_id: {citation.source_id}"
            )

        actual_url = str(citation.source_url).rstrip("/")
        if actual_url != expected_url:
            raise CitationValidationError(
                f"source_url does not match source_id: {citation.citation_id}"
            )

    for section in report.sections:
        unknown_ids = set(section.citation_ids) - citation_ids
        if unknown_ids:
            raise CitationValidationError(
                f"section {section.heading!r} uses unknown citations: "
                f"{sorted(unknown_ids)}"
            )
```

### 5.2 Markdown 渲染

新增 `app/services/report_renderer.py`：

```python
from app.models.report import ReportSchema


def compact_text(value: str) -> str:
    return " ".join(value.split())


def render_report_markdown(report: ReportSchema) -> str:
    lines = [f"# {compact_text(report.title)}", "", report.summary.strip()]

    if report.key_findings:
        lines.extend(["", "## 关键发现", ""])
        lines.extend(
            f"- {finding.strip()}"
            for finding in report.key_findings
            if finding.strip()
        )

    for section in report.sections:
        lines.extend(
            [
                "",
                f"## {compact_text(section.heading)}",
                "",
                section.content.strip(),
            ]
        )

    if report.citations:
        lines.extend(["", "## 参考资料", ""])
        for citation in report.citations:
            published = (
                f"，{citation.published_at.isoformat()}"
                if citation.published_at is not None
                else ""
            )
            lines.append(
                f"- [{citation.citation_id}] "
                f"[{compact_text(citation.source_title)}]"
                f"({citation.source_url}){published}"
            )

    return "\n".join(lines).strip() + "\n"
```

Renderer 必须是纯函数：相同 `ReportSchema` 永远得到相同 Markdown，不读取时间、环境变量、网络或全局状态。

## 6. Writer 与 LangGraph 的接口

Writer 不应直接接触 LangGraph Runtime。先定义 Protocol，再由节点注入：

```python
from typing import Protocol

from app.models.report import ReportSchema
from app.models.research import ResearchQuestion, ResearchRequest
from app.models.source import SourceDocument


class WriterProtocol(Protocol):
    async def write_report(
        self,
        request: ResearchRequest,
        questions: list[ResearchQuestion],
        sources: list[SourceDocument],
    ) -> ReportSchema:
        ...
```

`write_report` 节点的固定执行顺序应为：

```text
State → 构造 ResearchRequest/SourceDocument
      → writer.write_report(...)
      → validate_report_citations(...)
      → render_report_markdown(...)
      → 增量更新 draft_report/final_report/report_markdown/status
```

需要在 `ResearchState` 增加：

```python
report_markdown: NotRequired[str]
```

最终工作流变为：

```text
START
  → normalize_request
  → create_plan
  → search_sources
  → process_sources
  → write_report
  → END
```

## 7. 完成下一阶段的硬验收条件

- 项目依赖能在 `ai-search` 环境一次安装。
- 当前全部测试完成收集并通过。
- Ruff check、Ruff format、mypy 全部通过。
- Tavily Mock 测试不访问真实网络。
- URL 与 content_hash 去重不丢失研究问题关联。
- Writer 生成的每个 URL 都能反查到输入 SourceDocument。
- 同一 ReportSchema 连续渲染两次得到完全相同 Markdown。
- LangGraph 连续运行两个不同主题，不产生跨任务状态污染。

