"""Tool trajectory eval: efficiency and effectiveness of search/coverage across sections."""

import json

from deep_research.evals.judge import judge_call

RUBRIC = """Score 0-10: Evaluate the efficiency and effectiveness of the research trajectory (tool use).
- Section coverage: did section workers achieve good coverage scores (e.g. >= 6/10)? Low scores = insufficient evidence gathered.
- Deduplication: is the ratio of urls_deduped to urls_found reasonable? Very high dedup % may indicate redundant or repetitive queries.
- Critical gaps: were critical gaps in section_results resolved (or acknowledged) before finalising?
- Evidence yield: is writer_evidence_count proportionate to sections (enough sources per section)?
- 10 = efficient trajectory, good coverage, reasonable dedup; 0 = poor coverage, excessive redundancy, or critical gaps ignored."""


def eval_tool_trajectory(
    research_trace: dict,
    section_results: list[dict] | None = None,
) -> tuple[float, str]:
    """Check tool use efficiency from research_trace and section_results (LLM-as-judge)."""
    trace = research_trace or {}
    section_results = section_results or []

    sections = trace.get("sections_created", 0)
    if not sections and not section_results:
        return 0.5, "No trajectory data"

    trace_summary = {
        "sections_created": trace.get("sections_created"),
        "urls_found": trace.get("urls_found"),
        "urls_deduped": trace.get("urls_deduped"),
        "writer_evidence_count": trace.get("writer_evidence_count"),
        "section_coverage_scores": trace.get("section_coverage_scores"),
    }
    section_summary = []
    for sr in section_results[:20]:
        if not isinstance(sr, dict):
            continue
        section_summary.append({
            "section_id": sr.get("section_id"),
            "coverage_score": sr.get("coverage_score"),
            "gaps_count": len(sr.get("gaps") or []),
            "critical_gaps": [g for g in (sr.get("gaps") or []) if g.get("critical")],
            "confidence": sr.get("confidence"),
        })

    trace_str = json.dumps(trace_summary, default=str)[:1200]
    section_str = json.dumps(section_summary, default=str)[:1200]
    context = f"RESEARCH TRACE SUMMARY:\n{trace_str}\n\nPER-SECTION COVERAGE/GAPS:\n{section_str}"
    return judge_call(RUBRIC, context)
