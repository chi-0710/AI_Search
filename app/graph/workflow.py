from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.context import ResearchContext
from app.graph.nodes.create_plan import create_plan
from app.graph.nodes.normalize_request import normalize_request
from app.graph.nodes.search_sources import search_sources
from app.graph.state import ResearchState
from app.graph.nodes.write_report import write_report

def route_after_search(
    state:ResearchState,
)->Literal["write_report", "end"]:
    """
    搜索成功才进入 Writer。

    搜索完全失败时直接结束，
    保留 search_failed 状态。
    """
    if state.get("processed_sources"):
        return "write_report"

    return "end"


def build_research_graph() -> CompiledStateGraph:
    builder = StateGraph(
        state_schema=ResearchState,
        context_schema=ResearchContext,
    )

    builder.add_node("normalize_request",normalize_request)
    builder.add_node("create_plan",create_plan)
    builder.add_node("search_sources",search_sources)
    builder.add_node("write_report",write_report)

    builder.add_edge(START,"normalize_request")
    builder.add_edge("normalize_request","create_plan")
    builder.add_edge("create_plan","search_sources")
    builder.add_conditional_edges(
        "search_sources",
        route_after_search,
        {
            "write_report": "write_report",
            "end": END,
        }
    )
    builder.add_edge("write_report",END)

    return builder.compile()