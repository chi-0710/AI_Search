from dataclasses import dataclass

from app.agents.planner import PlannerProtocol
from app.agents.writer import WriterProtocol
from app.models.source import SourceDocument
from app.tools.base import ToolProtocol


@dataclass(frozen=True)
class ResearchContext:
    planner: PlannerProtocol
    search_tool: (
        ToolProtocol[SourceDocument]
        | None
    ) = None
    writer: WriterProtocol | None = None
    max_concurrency: int = 5