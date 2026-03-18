"""Conflict handling eval: contradictory evidence should be surfaced honestly."""

from deep_research.evals.judge import judge_call, async_judge_call

RUBRIC = """Score 0-10: Does the report honestly surface contradictions, uncertainties, or disagreements in the evidence?
- It should NOT present contested facts as settled.
- Penalise confident assertions where evidence conflicts.
- 10 = clearly acknowledges conflicts/uncertainty; 0 = presents contested claims as facts."""


def eval_conflict_handling(
    report_markdown: str,
    research_trace: dict | None = None,
) -> tuple[float, str]:
    """Check if report surfaces conflicts and caveats (LLM-as-judge)."""
    if not report_markdown:
        return 0.0, "Empty report"

    report_trunc = report_markdown[:4000] + ("..." if len(report_markdown) > 4000 else "")
    trace = research_trace or {}
    conflict_info = f"Conflicts detected in research: {trace.get('conflicts_detected', 0)}"
    if trace.get("conflict_records"):
        conflict_info += "\nConflict records: " + str(trace["conflict_records"])[:500]
    context = f"{conflict_info}\n\nREPORT:\n{report_trunc}"
    return judge_call(RUBRIC, context)


async def async_eval_conflict_handling(
    report_markdown: str,
    research_trace: dict | None = None,
) -> tuple[float, str]:
    """Async: check if report surfaces conflicts and caveats (LLM-as-judge)."""
    if not report_markdown:
        return 0.0, "Empty report"

    report_trunc = report_markdown[:4000] + ("..." if len(report_markdown) > 4000 else "")
    trace = research_trace or {}
    conflict_info = f"Conflicts detected in research: {trace.get('conflicts_detected', 0)}"
    if trace.get("conflict_records"):
        conflict_info += "\nConflict records: " + str(trace["conflict_records"])[:500]
    context = f"{conflict_info}\n\nREPORT:\n{report_trunc}"
    return await async_judge_call(RUBRIC, context)
