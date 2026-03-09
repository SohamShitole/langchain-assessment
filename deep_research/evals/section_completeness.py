"""Section completeness eval: each planned section should be addressed."""

from deep_research.evals.judge import judge_call

RUBRIC = """Score 0-10: Does the report address every planned section from the outline?
- For each section check: is the topic present, is it substantive (>2 sentences), or is it missing/superficial?
- 10 = all sections covered substantively; 0 = most sections missing or trivial."""


def eval_section_completeness(
    report_markdown: str, report_outline: list[dict]
) -> tuple[float, str]:
    """Check whether each planned section is addressed in the report (LLM-as-judge)."""
    if not report_markdown:
        return 0.5, "No report to compare"
    if not report_outline:
        return 0.5, "No outline to compare"

    outline_str = "\n".join(
        f"- {s.get('id', '')}: {s.get('title', '')}"
        for s in report_outline[:20]
    )
    report_trunc = report_markdown[:4000] + ("..." if len(report_markdown) > 4000 else "")
    context = f"PLANNED SECTIONS:\n{outline_str}\n\nREPORT:\n{report_trunc}"
    return judge_call(RUBRIC, context)
