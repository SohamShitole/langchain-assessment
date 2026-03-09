"""Claim support eval: major claims should be supported by cited evidence."""

import re


def eval_claim_support(report_markdown: str, writer_evidence: list[dict]) -> tuple[float, str]:
    """Check whether major claims appear to be supported by citations.
    Uses heuristics: citation density and presence of [1], [2] style refs."""
    if not report_markdown:
        return 0.0, "Empty report"
    if not writer_evidence:
        return 0.0, "No evidence provided to writer"

    citations = re.findall(r"\[\d+\]", report_markdown)
    num_citations = len(citations)
    words = len(report_markdown.split())
    if words < 10:
        return 0.5, "Report too short to assess"
    citation_density = num_citations / max(1, words / 100)
    max_citations = max(1, len(writer_evidence))
    unique_cited = len(set(int(m.group(1)) for m in re.finditer(r"\[(\d+)\]", report_markdown)))

    score = min(1.0, unique_cited / max_citations * 0.5 + min(1.0, citation_density / 5) * 0.5)
    reason = f"Citations: {num_citations}, unique refs: {unique_cited}/{max_citations}, density: {citation_density:.1f} per 100 words"
    return round(score, 2), reason
