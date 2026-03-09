"""Routing logic for the research graph."""

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
        return PREPARE_WRITER
    if iteration < max_iterations:
        return CONTINUE_RESEARCH
    return PREPARE_WRITER


def section_route(state: SectionWorkerState) -> str:
    """Route section worker: complete -> summary, or needs more -> loop."""
    section_complete = state.get("section_complete", False)
    iteration = state.get("section_iteration") or 0
    max_iterations = state.get("section_max_iterations") or 3

    if section_complete:
        return SECTION_COMPLETE
    if iteration < max_iterations:
        return SECTION_NEEDS_MORE
    return SECTION_COMPLETE  # Budget exhausted, summarize what we have


def conflict_route(state: ResearchState) -> str:
    """Route after conflict detection: resolve or ready to write."""
    conflict_resolution_needed = state.get("conflict_resolution_needed", False)
    resolution_enabled = state.get("conflict_resolution_enabled", True)

    if conflict_resolution_needed and resolution_enabled:
        return CONFLICT_RESOLUTION
    return READY_TO_WRITE
