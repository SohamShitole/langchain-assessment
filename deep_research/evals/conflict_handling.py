"""Conflict handling eval: contradictory evidence should be surfaced honestly."""

from deep_research.evals.judge import judge_call, async_judge_call

RUBRIC = """Score 0-10: Does the report handle contradictions and uncertainty in a way that matches the research state given in CONTEXT?

Use the line "Conflicts detected in research: N" and any "Conflict records" summary:

1) If N is 0 and conflict records are empty or absent: the pipeline did not flag cross-source contradictions. Do NOT demand fake disagreements. Score 8–10 for a clear, coherent synthesis; 9–10 if it briefly notes limitations, versioning, or that views evolve where appropriate. Reserve scores below 5 only for brazen false certainty on topics that are obviously disputed in general knowledge, or for ignoring non-empty conflict records below.

2) If N > 0 or conflict records describe specific clashing claims: the report must acknowledge those tensions or the stated resolution (winning claim / verdict). Score 10 when contradictions or residual uncertainty are surfaced honestly; score low if it silently picks one side or treats disputed claims as settled facts.

Do not punish a technical overview for omitting a generic "limitations" section when no conflicts were detected."""


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
