"""Conflict handling eval: contradictory evidence should be surfaced honestly."""

def eval_conflict_handling(report_markdown: str) -> tuple[float, str]:
    """Check if report mentions caveats, conflicts, or uncertainty."""
    if not report_markdown:
        return 0.0, "Empty report"

    lower = report_markdown.lower()
    indicators = [
        "caveat", "however", "conflict", "disagree", "unclear",
        "uncertain", "limited", "inconclusive", "varies", "differ",
        "contradict", "contrast", "alternative view", "on the other hand",
    ]
    found = sum(1 for i in indicators if i in lower)
    score = min(1.0, found / 3 * 0.5 + 0.5)
    reason = f"Found {found} conflict/caveat indicators"
    return round(score, 2), reason
