from datetime import date

from pydantic import BaseModel, Field, HttpUrl, model_validator


class Citation(BaseModel):
    """
    报告中的研究引用
    """
    

    citation_id: str=Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    source_id: str=Field(min_length=1,max_length=200)

    claim_text: str=Field(min_length=1,max_length=2000)
    source_title: str=Field(min_length=1,max_length=1000)
    source_url: HttpUrl

    published_at: date | None = None
    excerpt: str | None = Field(
        default=None,
        max_length=4000,
    )

    support_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )

class ReportFinding(BaseModel):
    """关键发现及其引用。"""
    text:str=Field(
        min_length=1,
        max_length=2000,
    )
    citation_ids:list[str]=Field(
        min_length=1
    )

class ReportSection(BaseModel):
    heading: str=Field(
        min_length=1,
        max_length=200,
    )
    content: str=Field(min_length=1)
    citation_ids: list[str] = Field(
        min_length=1,
    )


class ReportSchema(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=500,
    )
    summary: str = Field(min_length=1)

    sections: list[ReportSection] = Field(
        min_length=1,
    )
    key_findings: list[ReportFinding] = Field(
        default_factory=list,
    )
    citations: list[Citation] = Field(
        min_length=1,
    )

    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    @model_validator(mode="after")
    def validate_internal_citations(
        self,
    )->"ReportSchema":
        """
        检查报告内部的 citation_id 引用关系。

        这里只能验证：
        - citation_id 是否重复；
        - section/finding 使用的 citation_id 是否存在。

        source_id 和 URL 是否来自真实搜索结果，
        由 CitationService 验证。
        """
        citation_ids = [
            citation.citation_id for citation in self.citations
        ]

        if len(citation_ids) != len(set(citation_ids)):
            raise ValueError(
                "citation_id must be unique within a report"
            )
        known_ids=set(citation_ids)

        for section in self.sections:
            unknown_ids=(
                set(section.citation_ids) - known_ids
            )
            if unknown_ids:
                raise ValueError(
                    f"section {section.heading!r} "
                    f"references unknown citation ids: "
                    f"{sorted(unknown_ids)}"
                )
        for finding in self.key_findings:
            unknown_ids=set(finding.citation_ids) - known_ids
            if unknown_ids:
                raise ValueError(
                    f"finding {finding.text!r} "
                    f"references unknown citation ids: "
                    f"{sorted(unknown_ids)}"
                )
        return self
