"""Source quality eval: avoid over-reliance on weak or redundant sources."""

from deep_research.evals.judge import judge_call

RUBRIC = """Score 0-10: Assess the quality of sources used.
- Penalise: over-reliance on aggregator/blog sources, redundant sources, low-credibility sources.
- Reward: primary sources, recent publication, diverse source types.
- 10 = high-quality diverse primary sources; 0 = mostly weak or redundant sources."""


def eval_source_quality(writer_evidence: list[dict]) -> tuple[float, str]:
    """Check source type distribution and quality (LLM-as-judge)."""
    if not writer_evidence:
        return 0.0, "No evidence"

    lines = []
    for i, e in enumerate(writer_evidence[:40]):
        url = e.get("url", "")
        title = e.get("title", "")
        stype = e.get("source_type", "unknown")
        cred = e.get("credibility", "") or str(e.get("credibility_score", ""))
        primary = "primary" if e.get("is_primary") else ""
        redundant = "redundant" if e.get("is_redundant") else ""
        recency = e.get("recency", "")
        line = f"[{i+1}] {url} | {title} | type={stype} cred={cred} {primary} {redundant} recency={recency}".strip()
        lines.append(line)
    context = "\n".join(lines)
    if len(context) > 2000:
        context = context[:2000] + "\n..."
    return judge_call(RUBRIC, context)
