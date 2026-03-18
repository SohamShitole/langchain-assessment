"""Routing logic for the research graph."""

from deep_research.research_logger import log_route
from deep_research.state import ResearchState, SectionWorkerState

# Phase 1 (legacy)
PREPARE_WRITER = "prepare_writer_context"
CONTINUE_RESEARCH = "plan_and_generate_queries"

# Phase 2: section-level
SECTION_COMPLETE = "section_complete"
SECTION_NEEDS_MORE = "section_needs_more"

# Phase 2: global
CONFLICT_RESOLUTION = "conflict_resolution_research"
READY_TO_WRITE = "prepare_writer_context"


def route(state: ResearchState) -> str:
    """Route based on coverage: prepare writer or loop back to planner (Phase 1)."""
    coverage = state.get("coverage_status") or "insufficient"
    iteration = state.get("iteration") or 0
    max_iterations = state.get("max_iterations") or 3

    if coverage == "sufficient":
        log_route("assess_coverage", PREPARE_WRITER, "coverage sufficient")
        return PREPARE_WRITER
    if iteration < max_iterations:
        log_route("assess_coverage", CONTINUE_RESEARCH, f"iteration {iteration}/{max_iterations}, need more")
        return CONTINUE_RESEARCH
    log_route("assess_coverage", PREPARE_WRITER, "iteration budget exhausted")
    return PREPARE_WRITER


def section_route(state: SectionWorkerState) -> str:
    """Route section worker: complete -> summary, or needs more -> loop."""
    section_complete = state.get("section_complete", False)
    iteration = state.get("section_iteration") or 0
    max_iterations = state.get("section_max_iterations") or 3
    section_id = (state.get("section_task") or {}).get("id", "?")

    if section_complete:
        log_route(f"section_assess_coverage[{section_id}]", SECTION_COMPLETE, "section complete")
        return SECTION_COMPLETE
    if iteration < max_iterations:
        log_route(f"section_assess_coverage[{section_id}]", SECTION_NEEDS_MORE, f"iteration {iteration}/{max_iterations}")
        return SECTION_NEEDS_MORE
    log_route(f"section_assess_coverage[{section_id}]", SECTION_COMPLETE, "budget exhausted")
    return SECTION_COMPLETE  # Budget exhausted, summarize what we have


def conflict_route(state: ResearchState) -> str:
    """Route after conflict detection: resolve or ready to write."""
    conflict_resolution_needed = state.get("conflict_resolution_needed", False)
    resolution_enabled = state.get("conflict_resolution_enabled", True)

    if conflict_resolution_needed and resolution_enabled:
        log_route("detect_global_gaps_and_conflicts", CONFLICT_RESOLUTION, "conflicts need resolution")
        return CONFLICT_RESOLUTION
    reason = "no conflicts" if not conflict_resolution_needed else "resolution disabled"
    log_route("detect_global_gaps_and_conflicts", READY_TO_WRITE, reason)
    return READY_TO_WRITE


def stop_eval_route(state: ResearchState) -> str:
    """Route after eval_stop_gate: more research or proceed to writer."""
    if not state.get("research_sufficient") and (state.get("research_retry_count") or 0) <= 1:
        log_route("eval_stop_gate", CONFLICT_RESOLUTION, "research insufficient, retry")
        return CONFLICT_RESOLUTION
    log_route("eval_stop_gate", READY_TO_WRITE, "research sufficient or budget exhausted")
    return READY_TO_WRITE
