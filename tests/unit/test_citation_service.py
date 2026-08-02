from datetime import date,datetime,timezone

import pytest

from app.models.report import (
    Citation,
    ReportFinding,
    ReportSchema,
    ReportSection,
)
from app.models.source import (
    SourceDocument,
)
from app.services.citation_service import (
    CitationValidationError,
    validate_report_citations,
)


def build_source() -> SourceDocument:
    return SourceDocument(
        source_id="source-1",
        title="Official documentation",
        url="https://example.com/docs",
        source_type="official_docs",
        published_at=datetime(2026,7,20,tzinfo=timezone.utc,),
        summary=(
            "The project supports durable execution."
        ),
    )


def build_report(
    url: str = "https://example.com/docs",
) -> ReportSchema:
    return ReportSchema(
        title="Test report",
        summary=(
            "Summary supported by the source."
        ),
        sections=[
            ReportSection(
                heading="技术背景",
                content=(
                    "The project supports durable execution."
                ),
                citation_ids=["cite-1"],
            )
        ],
        key_findings=[
            ReportFinding(
                text=(
                    "Durable execution is supported."
                ),
                citation_ids=["cite-1"],
            )
        ],
        citations=[
            Citation(
                citation_id="cite-1",
                source_id="source-1",
                claim_text=(
                    "Durable execution is supported."
                ),
                source_title=(
                    "Official documentation"
                ),
                source_url=url,
                published_at=date(2026,7,20,),
                excerpt=(
                    "The project supports durable execution."
                ),
            )
        ],
        confidence=0.9,
    )


def test_accept_valid_citations() -> None:
    report = build_report()

    result = validate_report_citations(
        report,
        [build_source()],
    )

    assert result is report


def test_reject_fabricated_url() -> None:
    report = build_report(
        "https://fabricated.example.com"
    )

    with pytest.raises(
        CitationValidationError,
        match="source_url does not match",
    ):
        validate_report_citations(
            report,
            [build_source()],
        )


def test_reject_unknown_source_id() -> None:
    report = build_report()

    report.citations[0].source_id = (
        "unknown-source"
    )

    with pytest.raises(
        CitationValidationError,
        match="unknown source_id",
    ):
        validate_report_citations(
            report,
            [build_source()],
        )


def test_reject_url_in_content() -> None:
    report = build_report()

    report.sections[0].content = (
        "See https://fabricated.example.com"
    )

    with pytest.raises(
        CitationValidationError,
        match=(
            "narrative field must not contain a URL"
        ),
    ):
        validate_report_citations(
            report,
            [build_source()],
        )


def test_reject_fake_excerpt() -> None:
    report = build_report()

    report.citations[0].excerpt = (
        "This sentence is not in source."
    )

    with pytest.raises(
        CitationValidationError,
        match=(
            "excerpt does not exist in source"
        ),
    ):
        validate_report_citations(
            report,
            [build_source()],
        )