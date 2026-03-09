"""ingest_request node - read user request and initialize state."""

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from deep_research.configuration import get_config
from deep_research.state import ResearchState


def ingest_request(
    state: ResearchState,
    config: RunnableConfig | None = None,
) -> dict:
    """Read latest user request from messages and initialize state fields."""
    messages = state.get("messages") or []
    query = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            content = getattr(msg, "content", None)
            if isinstance(content, str):
                query = content.strip()
                break
            if isinstance(content, list):
                texts = [
                    p.get("text", "") for p in content
                    if isinstance(p, dict) and "text" in p
                ]
                query = " ".join(texts).strip()
                break

    if not query:
        query = "No query provided"

    cfg = get_config(config)
    max_iterations = cfg["max_iterations"]
    conflict_resolution_enabled = cfg.get("conflict_resolution_enabled", True)

    return {
        "query": query,
        "iteration": 0,
        "max_iterations": max_iterations,
        "report_outline": [],
        "search_queries": [],
        "raw_search_results": [],
        "evidence_items": [],
        "coverage_status": "",
        "knowledge_gaps": [],
        "seen_urls": set(),
        "writer_evidence_subset": [],
        "report_markdown": "",
        "sources": [],
        # Phase 2
        "research_plan": {},
        "section_tasks": [],
        "section_results": [],
        "merged_evidence": [],
        "global_conflicts": [],
        "section_summaries": [],
        "global_seen_urls": set(),
        "research_trace": {},
        "conflict_resolution_enabled": conflict_resolution_enabled,
    }
