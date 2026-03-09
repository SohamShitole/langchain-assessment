"""Source quality eval: avoid over-reliance on weak or redundant sources."""

def eval_source_quality(writer_evidence: list[dict]) -> tuple[float, str]:
    """Check source type distribution. Prefer primary, high-credibility."""
    if not writer_evidence:
        return 0.0, "No evidence"

    primary = sum(1 for e in writer_evidence if e.get("is_primary"))
    redundant = sum(1 for e in writer_evidence if e.get("is_redundant"))
    high_cred = sum(1 for e in writer_evidence if (e.get("credibility") or "").lower() == "high")
    high_score = sum(1 for e in writer_evidence if (e.get("credibility_score") or 0) >= 7)

    n = len(writer_evidence)
    primary_ratio = primary / n if n else 0
    redundant_ratio = redundant / n if n else 0
    cred_ratio = max(high_cred, high_score) / n if n else 0

    score = (1 - redundant_ratio) * 0.4 + min(1.0, primary_ratio * 2) * 0.3 + min(1.0, cred_ratio * 1.5) * 0.3
    reason = f"Primary: {primary}/{n}, redundant: {redundant}/{n}, high-cred: {max(high_cred, high_score)}/{n}"
    return round(min(1.0, score), 2), reason
