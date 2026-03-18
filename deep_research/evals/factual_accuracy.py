"""Factual accuracy eval: report claims should match the content of cited evidence snippets."""

from deep_research.evals.judge import judge_call, async_judge_call

RUBRIC = """Score 0-10: Do the specific factual claims in the report match the content of the cited evidence snippets?
- Check that claims are not contradicted or misrepresented by the evidence they cite.
- Penalise: invented facts, numbers or dates not in evidence, claims that contradict the snippet.
- 10 = claims align with evidence; 0 = many claims contradict or go beyond the evidence."""


def eval_factual_accuracy(report_markdown: str, writer_evidence: list[dict]) -> tuple[float, str]:
    """Check whether report claims match cited evidence content (LLM-as-judge)."""
    if not report_markdown:
        return 0.0, "Empty report"
    if not writer_evidence:
        return 0.5, "No evidence to verify against"

    report_trunc = report_markdown[:4000] + ("..." if len(report_markdown) > 4000 else "")
    lines = []
    for i, e in enumerate(writer_evidence[:25]):
        url = e.get("url", "")
        title = e.get("title", "")
        snippet = (e.get("snippet") or "")[:400].strip()
        if snippet:
            snippet = snippet + "..." if len(e.get("snippet") or "") > 400 else snippet
        line = f"[{i+1}] {url} | {title}\n  snippet: {snippet or '(none)'}"
        lines.append(line)
    evidence_block = "\n\n".join(lines)
    if len(evidence_block) > 3500:
        evidence_block = evidence_block[:3500] + "\n..."
    context = f"REPORT:\n{report_trunc}\n\nEVIDENCE (numbered; snippets for verification):\n{evidence_block}"
    return judge_call(RUBRIC, context)


async def async_eval_factual_accuracy(report_markdown: str, writer_evidence: list[dict]) -> tuple[float, str]:
    """Async: check whether report claims match cited evidence content (LLM-as-judge)."""
    if not report_markdown:
        return 0.0, "Empty report"
    if not writer_evidence:
        return 0.5, "No evidence to verify against"

    report_trunc = report_markdown[:4000] + ("..." if len(report_markdown) > 4000 else "")
    lines = []
    for i, e in enumerate(writer_evidence[:25]):
        url = e.get("url", "")
        title = e.get("title", "")
        snippet = (e.get("snippet") or "")[:400].strip()
        if snippet:
            snippet = snippet + "..." if len(e.get("snippet") or "") > 400 else snippet
        line = f"[{i+1}] {url} | {title}\n  snippet: {snippet or '(none)'}"
        lines.append(line)
    evidence_block = "\n\n".join(lines)
    if len(evidence_block) > 3500:
        evidence_block = evidence_block[:3500] + "\n..."
    context = f"REPORT:\n{report_trunc}\n\nEVIDENCE (numbered; snippets for verification):\n{evidence_block}"
    return await async_judge_call(RUBRIC, context)
