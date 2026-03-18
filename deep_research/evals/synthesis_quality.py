"""Synthesis quality eval: analytical depth, narrative flow, and cross-source synthesis."""

from deep_research.evals.judge import judge_call, async_judge_call

RUBRIC = """Score 0-10: Assess long-form reasoning and synthesis quality of the report.
- Analytical depth: does it analyze and reason, or merely list/summarise sources?
- Logical narrative flow: do sections connect coherently?
- Synthesis: does it integrate corroborating or conflicting evidence into a clear narrative?
- Executive summary or conclusion: is there a clear takeaway or synthesis at the end?
- If the topic is very short or simple (e.g. one factual question), score 8 and note "N/A - simple topic".
- 10 = strong analysis, clear flow, good synthesis; 0 = shallow list of facts, no narrative or conclusion."""


def eval_synthesis_quality(
    report_markdown: str,
    query: str,
    report_outline: list[dict],
) -> tuple[float, str]:
    """Check analytical depth, flow, and synthesis (LLM-as-judge)."""
    if not report_markdown:
        return 0.0, "Empty report"

    report_trunc = report_markdown[:4500] + ("..." if len(report_markdown) > 4500 else "")
    outline_str = "\n".join(
        f"- {s.get('id', '')}: {s.get('title', '')}"
        for s in (report_outline or [])[:20]
    )
    context = f"QUERY:\n{query}\n\nPLANNED SECTIONS:\n{outline_str or '(none)'}\n\nREPORT:\n{report_trunc}"
    return judge_call(RUBRIC, context)


async def async_eval_synthesis_quality(
    report_markdown: str,
    query: str,
    report_outline: list[dict],
) -> tuple[float, str]:
    """Async: check analytical depth, flow, and synthesis (LLM-as-judge)."""
    if not report_markdown:
        return 0.0, "Empty report"

    report_trunc = report_markdown[:4500] + ("..." if len(report_markdown) > 4500 else "")
    outline_str = "\n".join(
        f"- {s.get('id', '')}: {s.get('title', '')}"
        for s in (report_outline or [])[:20]
    )
    context = f"QUERY:\n{query}\n\nPLANNED SECTIONS:\n{outline_str or '(none)'}\n\nREPORT:\n{report_trunc}"
    return await async_judge_call(RUBRIC, context)
