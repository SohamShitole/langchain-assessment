"""Comparative breadth eval: for comparison prompts, all entities get adequate treatment."""

import re


def eval_comparative_breadth(report_markdown: str, query: str) -> tuple[float, str]:
    """For queries mentioning compare/X vs Y, check all entities appear."""
    if not report_markdown or not query:
        return 0.5, "No report or query"

    query_lower = query.lower()
    report_lower = report_markdown.lower()

    # Simple entity extraction: look for "X, Y, and Z" or "X vs Y" patterns
    compare_markers = ["compare", "versus", " vs ", "between", "and"]
    if not any(m in query_lower for m in compare_markers):
        return 0.8, "Not a comparison query; N/A"

    words = re.findall(r"\b[A-Z][a-z]+\b", query)
    entities = [w for w in words if len(w) > 2][:6]
    if not entities:
        return 0.6, "Could not extract entities from query"

    found = sum(1 for e in entities if e.lower() in report_lower)
    score = found / max(1, len(entities))
    reason = f"Entities {entities}: {found}/{len(entities)} found in report"
    return round(min(1.0, score), 2), reason
