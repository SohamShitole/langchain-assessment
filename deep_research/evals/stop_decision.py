"""Stop decision eval: did the agent stop appropriately vs loop unnecessarily."""

def eval_stop_decision(
    research_trace: dict, knowledge_gaps: list[dict]
) -> tuple[float, str]:
    """Check iteration counts and coverage vs gaps."""
    per_section = research_trace.get("per_section_iterations") or {}
    coverage = research_trace.get("section_coverage_scores") or {}
    sections = research_trace.get("sections_created", 0)

    if not sections:
        return 0.5, "No section trace data"

    total_iters = sum(per_section.values()) or 1
    avg_coverage = sum(coverage.values()) / max(1, len(coverage)) if coverage else 5.0
    critical_gaps = sum(1 for g in knowledge_gaps if g.get("critical"))

    # Prefer: moderate iterations, good coverage, few critical gaps
    iter_ok = 1.0 if total_iters <= sections * 3 else max(0, 1 - (total_iters - sections * 3) / 10)
    coverage_ok = min(1.0, avg_coverage / 7)
    gaps_ok = 1.0 if critical_gaps == 0 else max(0, 1 - critical_gaps * 0.2)

    score = (iter_ok * 0.3 + coverage_ok * 0.5 + gaps_ok * 0.2)
    reason = f"Iterations: {total_iters}, avg coverage: {avg_coverage:.1f}, critical gaps: {critical_gaps}"
    return round(min(1.0, score), 2), reason
