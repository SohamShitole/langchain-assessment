"""merge_section_evidence node - combine section results with dedup and provenance."""


from deep_research.state import ResearchState


def merge_section_evidence(
    state: ResearchState,
) -> dict:
    """Merge section_results into merged_evidence with dedup and provenance."""
    section_results = state.get("section_results") or []
    urls_seen: set[str] = set()
    merged: list[dict] = []
    urls_deduped = 0

    for sr in section_results:
        if not isinstance(sr, dict):
            continue
        section_id = sr.get("section_id", "")
        evidence = sr.get("evidence") or []

        for item in evidence:
            url = (item.get("url") or "").strip()
            if not url:
                continue
            if url in urls_seen:
                urls_deduped += 1
                # Find existing and add this section to supporting_sections
                for m in merged:
                    if m.get("url") == url:
                        sections = set(m.get("supporting_sections", []))
                        sections.add(section_id)
                        m["supporting_sections"] = list(sections)
                        m["cross_cutting"] = len(sections) > 1
                        break
                continue
            urls_seen.add(url)

            merged_item = {
                "url": url,
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "supporting_sections": [section_id],
                "cross_cutting": False,
                "evidence_meta": {
                    k: v
                    for k, v in item.items()
                    if k not in ("url", "title", "snippet")
                },
            }
            merged.append(merged_item)

    # Section summaries for writer (SectionSummary dicts)
    section_summaries = []
    for sr in section_results:
        if not isinstance(sr, dict):
            continue
        summary = sr.get("summary") or {}
        summary["section_id"] = sr.get("section_id", "")
        section_summaries.append(summary)

    trace = dict(state.get("research_trace") or {})
    trace["urls_found"] = len(urls_seen) + urls_deduped
    trace["urls_deduped"] = urls_deduped
    trace["section_coverage_scores"] = {
        sr.get("section_id", ""): sr.get("coverage_score", 0)
        for sr in section_results
        if isinstance(sr, dict)
    }

    return {
        "merged_evidence": merged,
        "section_summaries": section_summaries,
        "global_seen_urls": urls_seen,
        "research_trace": trace,
    }
