"""State definition for the research graph."""

import operator
from typing import Annotated, TypedDict

from langgraph.graph import add_messages


def _merge_sets(left: set[str] | None, right: set[str] | None) -> set[str]:
    """Reducer that unions two sets."""
    left = left or set()
    right = right or set()
    return left | right


def _keep_first(left, right):
    """Reducer for parallel workers: keep first value to avoid conflicting updates."""
    if left is not None and left != "" and left != 0 and left != {} and left != []:
        return left
    return right


class ResearchState(TypedDict, total=False):
    """State for the deep research workflow (Phase 1 + Phase 2)."""

    messages: Annotated[list, add_messages]
    query: Annotated[str, _keep_first]  # Reducer needed for parallel section workers
    complexity: str  # "simple" | "moderate" | "complex"
    planner_model: str
    report_outline: list[dict]
    search_queries: list[str]
    raw_search_results: Annotated[list[dict], operator.add]
    evidence_items: Annotated[list[dict], operator.add]
    coverage_status: str  # "sufficient" | "insufficient"
    knowledge_gaps: list[dict]
    seen_urls: Annotated[set[str], _merge_sets]
    iteration: int
    max_iterations: int
    writer_evidence_subset: list[dict]
    report_markdown: str
    sources: list[dict]

    # Phase 2: orchestrated research
    research_plan: dict
    section_tasks: list[dict]
    section_results: Annotated[list[dict], operator.add]
    merged_evidence: list[dict]
    global_conflicts: list[dict]
    section_summaries: list[dict]
    global_seen_urls: Annotated[set[str], _merge_sets]
    research_trace: dict
    section_drafts: list[dict]
    conflict_resolution_needed: bool
    conflict_resolution_enabled: bool
    section_max_iterations: Annotated[int, _keep_first]  # Reducer for parallel workers

    # Eval stop gate (decision)
    stop_eval_score: float
    research_sufficient: bool
    research_retry_count: int


class SectionWorkerState(TypedDict, total=False):
    """State for the section worker subgraph."""

    section_task: dict
    query: str
    section_queries: list[str]
    section_raw_results: list[dict]
    section_evidence: Annotated[list[dict], operator.add]
    section_coverage: float
    section_gaps: list[dict]
    section_iteration: int
    section_max_iterations: int
    section_complete: bool
    section_summary: dict
    section_results: list[dict]  # Output for parent: [{section_id, evidence, ...}]
    global_seen_urls: set[str]
    section_seen_urls: Annotated[set[str], _merge_sets]
