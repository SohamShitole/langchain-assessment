"""Comparative breadth eval: for comparison prompts, all entities get adequate treatment."""

from deep_research.evals.judge import judge_call

RUBRIC = """Score 0-10: For comparison queries (e.g. X vs Y, compare A and B), does the report give proportionate treatment to every entity being compared?
- Penalise: one entity dominates, others get only a sentence.
- If this is NOT a comparison query, score 8 (N/A)."""


def eval_comparative_breadth(report_markdown: str, query: str) -> tuple[float, str]:
    """For comparison queries, check all entities get adequate treatment (LLM-as-judge)."""
    if not report_markdown or not query:
        return 0.5, "No report or query"

    report_trunc = report_markdown[:4000] + ("..." if len(report_markdown) > 4000 else "")
    context = f"QUERY:\n{query}\n\nREPORT:\n{report_trunc}"
    return judge_call(RUBRIC, context)
