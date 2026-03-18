"""Citation relevance eval: each [n] citation should support the specific claim it annotates."""

import re

from deep_research.evals.judge import judge_call, async_judge_call

RUBRIC = """Score 0-10: For each citation [n] in the report, does evidence item n actually support the specific claim or sentence it is attached to?
- This is per-citation relevance: the cited source should substantiate that exact claim, not just be topically related.
- Penalise: citations that don't support the adjacent claim, wrong evidence for the claim, vague/irrelevant citations.
- 10 = all sampled citations clearly support their claims; 0 = many citations irrelevant or mismatched."""


def _extract_citation_contexts(report: str, evidence: list[dict], max_samples: int = 15) -> str:
    """Extract up to max_samples sentences/phrases that contain [n] and pair with evidence n."""
    # Find all [1], [2], ... citation markers
    pattern = re.compile(r"\[(\d+)\]")
    parts = []
    pos = 0
    samples = []
    while len(samples) < max_samples and pos < len(report):
        m = pattern.search(report, pos)
        if not m:
            break
        num_str = m.group(1)
        try:
            idx = int(num_str)
        except ValueError:
            pos = m.end()
            continue
        # Get surrounding sentence or clause (approx 80 chars before, 120 after)
        start = max(0, m.start() - 80)
        end = min(len(report), m.end() + 120)
        snippet = report[start:end].replace("\n", " ")
        if len(snippet) > 200:
            snippet = snippet[:200] + "..."
        ev = evidence[idx - 1] if 1 <= idx <= len(evidence) else {}
        title = ev.get("title", "")
        ev_snippet = (ev.get("snippet") or "")[:300].strip()
        samples.append(
            f"Claim context: \"{snippet}\"\n  Cited [{idx}] -> {title}\n  Evidence excerpt: {ev_snippet or '(none)'}"
        )
        pos = m.end()
    return "\n\n---\n\n".join(samples) if samples else "No [n] citations found in report."


def eval_citation_relevance(report_markdown: str, writer_evidence: list[dict]) -> tuple[float, str]:
    """Check whether each citation supports the claim it annotates (LLM-as-judge)."""
    if not report_markdown:
        return 0.0, "Empty report"
    if not writer_evidence:
        return 0.5, "No evidence to check citations against"

    citation_contexts = _extract_citation_contexts(report_markdown, writer_evidence, max_samples=15)
    context = f"CITATION SAMPLES (claim context + cited evidence):\n\n{citation_contexts}"
    return judge_call(RUBRIC, context)


async def async_eval_citation_relevance(report_markdown: str, writer_evidence: list[dict]) -> tuple[float, str]:
    """Async: check whether each citation supports the claim it annotates (LLM-as-judge)."""
    if not report_markdown:
        return 0.0, "Empty report"
    if not writer_evidence:
        return 0.5, "No evidence to check citations against"

    citation_contexts = _extract_citation_contexts(report_markdown, writer_evidence, max_samples=15)
    context = f"CITATION SAMPLES (claim context + cited evidence):\n\n{citation_contexts}"
    return await async_judge_call(RUBRIC, context)
