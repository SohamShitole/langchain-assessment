"""Claim support eval: major claims should be supported by cited evidence."""

from deep_research.evals.judge import judge_call

RUBRIC = """Score 0-10: Are major factual claims in the report supported by an inline citation linking to provided evidence?
- Penalise unsupported assertions.
- Consider citation density and coverage of evidence items.
- 10 = almost all substantive claims cited; 0 = many unsupported claims."""


def eval_claim_support(report_markdown: str, writer_evidence: list[dict]) -> tuple[float, str]:
    """Check whether major claims are supported by cited evidence (LLM-as-judge)."""
    if not report_markdown:
        return 0.0, "Empty report"
    if not writer_evidence:
        return 0.0, "No evidence provided to writer"

    report_trunc = report_markdown[:4000] + ("..." if len(report_markdown) > 4000 else "")
    evidence_list = "\n".join(
        f"[{i+1}] {e.get('url', '')} | {e.get('title', '')}"
        for i, e in enumerate(writer_evidence[:30])
    )
    context = f"REPORT:\n{report_trunc}\n\nEVIDENCE (numbered for citation):\n{evidence_list}"
    return judge_call(RUBRIC, context)
