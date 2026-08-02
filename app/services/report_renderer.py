from html import escape as escape_html
from app.models.report import ReportSchema

def compact_inline_text(value:str,)->str:
    """
    标题只能使用单行文本。

    同时转义 HTML，避免模型输出 <script> 等标签。
    """
    compacted=" ".join(value.split())
    return escape_html(
        compacted,
        quote=False
    )

def escape_link_text(
    value:str,
)->str:
    """
    转义 Markdown 链接标题中的特殊字符。
    """
    value=compact_inline_text(value)

    return (
        value
        .replace("\\", "\\\\")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )

def render_report_markdown(
    report:ReportSchema,
)->str:
    """
    将 ReportSchema 确定性渲染为 Markdown。

    这个函数：
    - 不访问网络；
    - 不调用 LLM；
    - 不读取环境变量；
    - 不使用当前时间；
    - 相同输入始终产生相同输出。
    """
    lines:list[str]=[
        f"# {compact_inline_text(report.title)}",
        "",
        escape_html(
            report.summary.strip(),
            quote=False,
        ),
    ]
    if report.key_findings:
        lines.extend(
            [
                "",
                "## 关键发现",
                "",
            ]
        )

    for finding in report.key_findings:
        references="".join(
            f"[{citation_id}](#citation-{citation_id})"
            for citation_id in finding.citation_ids
        )
        finding_text=escape_html(
            finding.text.strip(),
            quote=False,
        )
        lines.append(
            f"- {finding_text} {references}"
        )

    for section in report.sections:
        references = " ".join(
            (
                f"[{citation_id}]"
                f"(#citation-{citation_id})"
            )
            for citation_id
            in section.citation_ids
        )

        content = escape_html(
            section.content.strip(),
            quote=False,
        )

        lines.extend(
            [
                "",
                (
                    "## "
                    f"{compact_inline_text(section.heading)}"
                ),
                "",
                content,
                "",
                f"引用：{references}",
            ]
        )

    if report.confidence is not None:
        lines.extend(
            [
                "",
                f"置信度：{report.confidence:.0%}",
            ]
        )

    lines.extend(
        [
            "",
            "## 参考资料",
            "",
        ]
    )

    for citation in report.citations:
        published = (
            f"，{citation.published_at.isoformat()}"
            if citation.published_at is not None
            else ""
        )

        lines.extend(
            [
                (
                    f'<a id="citation-'
                    f'{citation.citation_id}"></a>'
                ),
                (
                    f"- **[{citation.citation_id}]** "
                    f"[{escape_link_text(citation.source_title)}]"
                    f"({citation.source_url})"
                    f"{published}"
                ),
            ]
        )

        if citation.excerpt:
            excerpt = escape_html(
                citation.excerpt.strip(),
                quote=False,
            )

            for excerpt_line in excerpt.splitlines():
                lines.append(
                    f"> {excerpt_line}"
                )

    return "\n".join(lines).strip() + "\n"