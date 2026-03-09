"""Section completeness eval: each planned section should be addressed."""

import re


def eval_section_completeness(
    report_markdown: str, report_outline: list[dict]
) -> tuple[float, str]:
    """Check whether each planned section is addressed in the report."""
    if not report_markdown or not report_outline:
        return 0.5, "No outline or report to compare"

    report_lower = report_markdown.lower()
    section_ids = [s.get("id", "") for s in report_outline if s.get("id")]
    section_titles = [s.get("title", "").lower() for s in report_outline if s.get("title")]

    found = 0
    for sid, title in zip(section_ids, section_titles):
        if title and title in report_lower:
            found += 1
        elif sid and sid in report_lower:
            found += 1
        elif title and any(w in report_lower for w in title.split() if len(w) > 3):
            found += 0.5

    total = max(1, len(section_titles))
    score = found / total
    reason = f"Found {found}/{total} sections by title or ID"
    return round(min(1.0, score), 2), reason
