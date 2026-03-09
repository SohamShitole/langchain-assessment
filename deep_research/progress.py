"""Progress display: single-line natural-language messages as the graph runs."""

import sys
from typing import Any

# Node name -> one-line natural-language message (no step counters or brackets)
NODE_MESSAGES: dict[str, str] = {
    "ingest_request": "Reading your query...",
    "classify_complexity": "Figuring out how complex this topic is...",
    "create_research_plan": "Drafting a research plan...",
    "decompose_into_sections": "Breaking the plan into independent research sections...",
    "section_worker": "Finished researching: {section_title}",  # section_title filled from update
    "merge_section_evidence": "Merging evidence from all sections...",
    "detect_global_gaps_and_conflicts": "Checking for gaps and contradictions across sections...",
    "conflict_resolution_research": "Running additional searches to resolve contradictions...",
    "prepare_writer_context": "Selecting the best evidence for the report...",
    "write_sections": "Writing section drafts...",
    "write_report": "Assembling the final report...",
    "finalize_messages": "Done!",
}


def print_progress(node_name: str, data: dict[str, Any] | None = None) -> None:
    """Print a single line of natural language for the given node. Flushes so it appears immediately."""
    data = data or {}
    msg = NODE_MESSAGES.get(node_name)
    if not msg:
        return
    if node_name == "section_worker":
        # One line per section that just completed; data may have section_results
        results = data.get("section_results") or []
        for one in results:
            if isinstance(one, dict):
                title = one.get("section_title") or one.get("section_id") or "a section"
                line = msg.format(section_title=title)
                print(line, flush=True)
        if not results:
            print("Researching sections in parallel...", flush=True)
        return
    if "{section_title}" in msg:
        msg = msg.format(section_title="a section")
    print(msg, flush=True)


def display_plan(plan: dict) -> None:
    """Print the proposed research plan for user approval."""
    sections = plan.get("desired_structure") or plan.get("section_names") or []
    if isinstance(sections, list) and sections and isinstance(sections[0], dict):
        section_list = [(s.get("id", ""), s.get("title", "Section")) for s in sections]
    elif isinstance(sections, list):
        section_list = [(str(i + 1), t) for i, t in enumerate(sections) if isinstance(t, str)]
    else:
        section_list = []

    print(file=sys.stderr)
    print("  Proposed Research Plan", file=sys.stderr)
    print("  " + "─" * 40, file=sys.stderr)
    print("  Sections:", file=sys.stderr)
    for i, (sid, title) in enumerate(section_list, 1):
        print(f"    {i}. {title}", file=sys.stderr)
    print(file=sys.stderr)


def print_section_count(n: int) -> None:
    """Print one line before section workers run (e.g. 'Researching sections in parallel...')."""
    if n > 0:
        print(f"Researching {n} sections in parallel...", flush=True)
