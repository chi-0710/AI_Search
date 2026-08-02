import re
from collections.abc import Sequence

from pydantic import HttpUrl
from app.models.report import ReportSchema
from app.models.source import SourceDocument

class CitationValidationError(ValueError):
    """报告引用无法被真实检索来源支持。"""

NARRATIVE_URL_PATTERN = re.compile(
    r"https?://",
    re.IGNORECASE,
)

MARKDOWN_LINK_PATTERN = re.compile(
    r"\[[^\]]+\]\([^)]+\)"
)

def normalize_url_for_comparison(
    value: HttpUrl | str,
) -> str:
    """
    处理 Pydantic 对根路径自动补 `/` 的差异。

    例如：
    https://example.com
    https://example.com/

    比较时认为相同。
    """

    return str(value).strip().rstrip("/")

def normalize_evidence_text(
    value:str,
)->str:
    """用于验证 excerpt 是否来自真实来源。"""
    return "".join(value.split())

def validate_narrative_fields(
    report:ReportSchema,
)->None:
    """
    禁止 Writer 在普通正文里直接加入链接。

    最终 Markdown 中的所有链接必须由 Renderer
    从已验证的 Citation.source_url 生成。
    """
    fields:list[tuple[str,str]]=[
        ("report.title", report.title),
        ("report.summary", report.summary),
    ]

    fields.extend(
        (
            f"section:{section.heading}",
            section.content,
        )
        for section in report.sections
    )

    fields.extend(
        (
            "finding",
            finding.text,
        )
        for finding in report.key_findings
    )

    fields.extend(
        (
            f"claim:{citation.citation_id}",
            citation.claim_text,
        )
        for citation in report.citations
    )

    fields.extend(
        (
            f"excerpt:{citation.citation_id}",
            citation.excerpt or "",
        )
        for citation in report.citations
    )

    for field_name, value in fields:
        if NARRATIVE_URL_PATTERN.search(value):
            raise CitationValidationError(
                "narrative field must not contain "
                f"a URL: {field_name}"
            )

        if MARKDOWN_LINK_PATTERN.search(value):
            raise CitationValidationError(
                "narrative field must not contain "
                f"a Markdown link: {field_name}"
            )


def validate_report_citations(
    report: ReportSchema,
    sources: Sequence[SourceDocument],
) -> ReportSchema:
    """
    将 Writer 报告与工具真实返回的来源交叉验证。

    验证内容：
    1. source_id 真实存在；
    2. URL 与 source_id 对应；
    3. 标题与 source_id 对应；
    4. 发布日期没有被改写；
    5. excerpt 确实来自来源正文或摘要；
    6. 每个 section/finding 至少有一个引用；
    7. 不允许存在未被使用的 Citation；
    8. 正文不能绕过 Citation 直接输出链接。
    """

    if not sources:
        raise CitationValidationError(
            "cannot validate report without sources"
        )

    validate_narrative_fields(report)

    source_by_id: dict[str, SourceDocument] = {}

    for source in sources:
        if source.source_id in source_by_id:
            raise CitationValidationError(
                "duplicate source_id in retrieval "
                f"context: {source.source_id}"
            )

        source_by_id[source.source_id] = source

    citation_ids: set[str] = set()

    for citation in report.citations:
        citation_ids.add(citation.citation_id)

        source = source_by_id.get(
            citation.source_id
        )

        if source is None:
            raise CitationValidationError(
                f"unknown source_id: "
                f"{citation.source_id}"
            )

        expected_url = normalize_url_for_comparison(
            source.url
        )
        actual_url = normalize_url_for_comparison(
            citation.source_url
        )

        if actual_url != expected_url:
            raise CitationValidationError(
                "source_url does not match "
                f"source_id: {citation.citation_id}"
            )

        if (
            citation.source_title.strip()
            != source.title.strip()
        ):
            raise CitationValidationError(
                "source_title does not match "
                f"source_id: {citation.citation_id}"
            )

        source_date = (
            source.published_at.date()
            if source.published_at is not None
            else None
        )

        if citation.published_at != source_date:
            raise CitationValidationError(
                "published_at does not match "
                f"source_id: {citation.citation_id}"
            )

        if citation.excerpt:
            source_evidence = (
                source.clean_content.strip()
                or source.summary.strip()
            )

            normalized_excerpt = (
                normalize_evidence_text(
                    citation.excerpt
                )
            )
            normalized_source = (
                normalize_evidence_text(
                    source_evidence
                )
            )

            if (
                not normalized_source
                or normalized_excerpt
                not in normalized_source
            ):
                raise CitationValidationError(
                    "excerpt does not exist in "
                    f"source: {citation.citation_id}"
                )

    used_ids: set[str] = set()

    for section in report.sections:
        if not section.citation_ids:
            raise CitationValidationError(
                "section has no citation: "
                f"{section.heading}"
            )

        used_ids.update(
            section.citation_ids
        )

    for finding in report.key_findings:
        if not finding.citation_ids:
            raise CitationValidationError(
                "finding has no citation: "
                f"{finding.text}"
            )

        used_ids.update(
            finding.citation_ids
        )

    unused_ids = citation_ids - used_ids

    if unused_ids:
        raise CitationValidationError(
            f"unused citations: {sorted(unused_ids)}"
        )

    return report