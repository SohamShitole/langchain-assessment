"""LangGraph research workflow definition.

Phase 2: Orchestrated research with section decomposition and parallel workers.
Phase 1: create_research_graph_phase1() for legacy single-agent loop.
"""

from typing import TYPE_CHECKING

from langgraph.graph import START, StateGraph

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

try:
    from langgraph.checkpoint.memory import MemorySaver
except ImportError:
    MemorySaver = None  # type: ignore[misc, assignment]

from deep_research.nodes.classify import classify_complexity
from deep_research.nodes.conflicts import (
    conflict_resolution_research,
    detect_global_gaps_and_conflicts,
    eval_stop_gate,
)
from deep_research.nodes.coverage import assess_coverage
from deep_research.nodes.decompose import decompose_into_sections, dispatch_sections
from deep_research.nodes.finalize import finalize_messages
from deep_research.nodes.ingest import ingest_request
from deep_research.nodes.merge import merge_section_evidence
from deep_research.nodes.normalize import normalize_and_map_evidence
from deep_research.nodes.planner import create_research_plan, plan_and_generate_queries
from deep_research.nodes.search import run_search
from deep_research.nodes.section_writer import write_sections
from deep_research.nodes.writer import write_report
from deep_research.nodes.writer_context import prepare_writer_context
from deep_research.routing import conflict_route, route, stop_eval_route
from deep_research.section_graph import create_section_worker_graph
from deep_research.state import ResearchState


def _report_search_error(state: ResearchState, config=None) -> dict:
    """No-op node: error_message is already in state; flow ends so UI can show it."""
    return {}


def create_research_graph(
    checkpointer=None,
    interrupt_after: list[str] | None = None,
):
    """Build and compile the Phase 2 orchestrated research graph.

    Flow: ingest -> classify -> create_research_plan -> decompose
          -> [Send section_worker per section] -> merge -> detect_conflicts
          -> [optional conflict_resolution] -> prepare_writer -> write -> finalize

    If checkpointer and interrupt_after are provided, the graph pauses after
    the given node(s) for human-in-the-loop (e.g. plan approval).
    """
    builder = StateGraph(ResearchState)

    section_subgraph = create_section_worker_graph()

    builder.add_node("ingest_request", ingest_request)
    builder.add_node("classify_complexity", classify_complexity)
    builder.add_node("create_research_plan", create_research_plan)
    builder.add_node("decompose_into_sections", decompose_into_sections)
    builder.add_node("section_worker", section_subgraph)
    builder.add_node("report_search_error", _report_search_error)
    builder.add_node("merge_section_evidence", merge_section_evidence)
    builder.add_node("detect_global_gaps_and_conflicts", detect_global_gaps_and_conflicts)
    builder.add_node("conflict_resolution_research", conflict_resolution_research)
    builder.add_node("eval_stop_gate", eval_stop_gate)
    builder.add_node("prepare_writer_context", prepare_writer_context)
    builder.add_node("write_sections", write_sections)
    builder.add_node("write_report", write_report)
    builder.add_node("finalize_messages", finalize_messages)

    builder.add_edge(START, "ingest_request")
    builder.add_edge("ingest_request", "classify_complexity")
    builder.add_edge("classify_complexity", "create_research_plan")
    builder.add_edge("create_research_plan", "decompose_into_sections")
    builder.add_conditional_edges("decompose_into_sections", dispatch_sections)

    def after_section_worker_route(state: ResearchState):
        return "report_search_error" if state.get("error_message") else "merge_section_evidence"

    builder.add_conditional_edges(
        "section_worker",
        after_section_worker_route,
        {"report_search_error": "report_search_error", "merge_section_evidence": "merge_section_evidence"},
    )
    builder.add_edge("report_search_error", "__end__")
    builder.add_edge("merge_section_evidence", "detect_global_gaps_and_conflicts")
    builder.add_conditional_edges(
        "detect_global_gaps_and_conflicts",
        conflict_route,
        {
            "conflict_resolution_research": "conflict_resolution_research",
            "prepare_writer_context": "eval_stop_gate",
        },
    )
    builder.add_edge("conflict_resolution_research", "eval_stop_gate")
    builder.add_conditional_edges(
        "eval_stop_gate",
        stop_eval_route,
        {
            "conflict_resolution_research": "conflict_resolution_research",
            "prepare_writer_context": "prepare_writer_context",
        },
    )
    builder.add_edge("prepare_writer_context", "write_sections")
    builder.add_edge("write_sections", "write_report")
    builder.add_edge("write_report", "finalize_messages")
    builder.add_edge("finalize_messages", "__end__")

    compile_kwargs: dict = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer
    if interrupt_after is not None:
        compile_kwargs["interrupt_after"] = interrupt_after
    return builder.compile(**compile_kwargs)


def create_research_graph_phase1():
    """Build and compile the Phase 1 single-agent iterative graph (legacy)."""
    builder = StateGraph(ResearchState)

    builder.add_node("ingest_request", ingest_request)
    builder.add_node("classify_complexity", classify_complexity)
    builder.add_node("plan_and_generate_queries", plan_and_generate_queries)
    builder.add_node("run_search", run_search)
    builder.add_node("report_search_error", _report_search_error)
    builder.add_node("normalize_and_map_evidence", normalize_and_map_evidence)
    builder.add_node("assess_coverage", assess_coverage)
    builder.add_node("prepare_writer_context", prepare_writer_context)
    builder.add_node("write_report", write_report)
    builder.add_node("finalize_messages", finalize_messages)

    builder.add_edge(START, "ingest_request")
    builder.add_edge("ingest_request", "classify_complexity")
    builder.add_edge("classify_complexity", "plan_and_generate_queries")
    builder.add_edge("plan_and_generate_queries", "run_search")
    builder.add_conditional_edges(
        "run_search",
        lambda s: "report_search_error" if s.get("error_message") else "normalize_and_map_evidence",
        {"report_search_error": "report_search_error", "normalize_and_map_evidence": "normalize_and_map_evidence"},
    )
    builder.add_edge("report_search_error", "__end__")
    builder.add_edge("normalize_and_map_evidence", "assess_coverage")
    builder.add_conditional_edges(
        "assess_coverage",
        route,
        {
            "prepare_writer_context": "prepare_writer_context",
            "plan_and_generate_queries": "plan_and_generate_queries",
        },
    )
    builder.add_edge("prepare_writer_context", "write_report")
    builder.add_edge("write_report", "finalize_messages")
    builder.add_edge("finalize_messages", "__end__")

    return builder.compile()


def make_graph(config: "RunnableConfig | None" = None):
    """Build the research graph for LangGraph CLI / LangSmith Studio.

    Used by langgraph.json as the graph entry point. Accepts RunnableConfig
    for optional runtime customization; nodes already read config via get_config().
    Returns a compiled graph with in-memory checkpointer so Studio can manage
    threads and visualize the flow.
    """
    del config  # Unused; nodes use get_config() from invocation config
    checkpointer = MemorySaver() if MemorySaver else None
    return create_research_graph(checkpointer=checkpointer, interrupt_after=None)
