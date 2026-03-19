"""write_report node - generate grounded markdown report."""

import json

from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig

from deep_research.configuration import DEFAULT_REPORT_STRUCTURE, get_config
from deep_research.prompts import (
    ENHANCED_WRITER_PROMPT,
    REPORT_ASSEMBLY_PROMPT,
    WRITER_PROMPT,
    get_prompt,
)
from deep_research.research_logger import log_node_end, log_node_start, log_prompt
from deep_research.state import ResearchState


def _format_conflict_resolutions(global_conflicts: list[dict]) -> str:
    """Build writer-facing summary of adjudicated conflicts (winning claim, verdict, caveats)."""
    if not global_conflicts:
        return "None."
    lines = []
    for i, c in enumerate(global_conflicts, 1):
        if not isinstance(c, dict):
            continue
        claims = c.get("conflicting_claims") or []
        verdict = (c.get("resolution_verdict") or "").strip()
        winning = (c.get("winning_claim") or "").strip()
        resolved = c.get("resolved", False)
        severity = c.get("severity", "medium")
        sections = c.get("section_ids") or []
        parts = [f"[Conflict {i}] (severity: {severity})"]
        if claims:
            parts.append("Conflicting claims: " + "; ".join(claims[:2]))
        if resolved and winning:
            parts.append(f"Winning claim: {winning}")
        if verdict:
            parts.append(f"Verdict: {verdict}")
        if not resolved:
            parts.append("(Unresolved — surface uncertainty in the report.)")
        if sections:
            parts.append(f"Relevant sections: {', '.join(sections)}")
        lines.append(" ".join(parts))
    return "\n\n".join(lines) if lines else "None."


async def write_report(state: ResearchState, config: RunnableConfig | None = None) -> dict:
    """Generate final markdown report.

    Three modes (checked in order):
    1. Assembly mode — section_drafts exist (Phase 2 with section-by-section writing).
       Assembles pre-written section drafts into a coherent report. No raw evidence
       in the prompt, so it always fits in context.
    2. Enhanced mode — section_summaries exist but no section_drafts (legacy Phase 2).
       Uses ENHANCED_WRITER_PROMPT with full evidence (may hit context limits).
    3. Basic mode — Phase 1 single-agent loop.
    """
    log_node_start("write_report", config)
    outline = state.get("report_outline") or []
    evidence = state.get("writer_evidence_subset") or []
    # Fallback: if writer got no evidence (e.g. state merge quirk with checkpointer), use merged_evidence
    if not evidence:
        merged = state.get("merged_evidence") or []
        evidence = [
            {
                "url": m.get("url", ""),
                "title": m.get("title", ""),
                "snippet": m.get("snippet", ""),
            }
            for m in merged
        ]
    gaps = state.get("knowledge_gaps") or []
    coverage_status = state.get("coverage_status") or "insufficient"
    max_iterations = state.get("max_iterations") or 3
    iteration = state.get("iteration") or 1
    section_summaries = state.get("section_summaries") or []
    section_drafts = state.get("section_drafts") or []
    global_conflicts = state.get("global_conflicts") or []
    cfg = get_config(config)
    model_name = cfg.get("writer_model") or "gpt-4o"
    report_structure = " > ".join(
        cfg.get("report_structure") or DEFAULT_REPORT_STRUCTURE
    )

    outline_str = json.dumps(outline, indent=2)
    conflict_resolutions = _format_conflict_resolutions(global_conflicts)

    if section_drafts:
        # ── Assembly mode: stitch pre-written section drafts ──
        drafts_str = "\n\n---\n\n".join(
            f"### Section: {d['title']}\n\n{d['draft']}" for d in section_drafts
        )
        sources_str = "\n".join(
            f"[{i + 1}] {e.get('url', '')} — *{e.get('title', 'Untitled')}*"
            for i, e in enumerate(evidence)
        )
        template = get_prompt("report_assembly", cfg, REPORT_ASSEMBLY_PROMPT)
        prompt = template.format(
            report_outline=outline_str,
            section_drafts=drafts_str,
            sources_list=sources_str,
            report_structure=report_structure,
            conflict_resolutions=conflict_resolutions,
        )
    elif section_summaries:
        # ── Enhanced mode (legacy Phase 2, no section drafts) ──
        writer_evidence_str = json.dumps(
            [{"url": e.get("url"), "title": e.get("title"), "snippet": e.get("snippet")} for e in evidence],
            indent=2,
        )
        summaries_str = json.dumps(section_summaries, indent=2)
        template = get_prompt("enhanced_writer", cfg, ENHANCED_WRITER_PROMPT)
        prompt = template.format(
            report_outline=outline_str,
            section_summaries=summaries_str,
            writer_evidence=writer_evidence_str,
            report_structure=report_structure,
            conflict_resolutions=conflict_resolutions,
        )
    else:
        # ── Basic mode (Phase 1) ──
        writer_evidence_str = json.dumps(
            [{"url": e.get("url"), "title": e.get("title"), "snippet": e.get("snippet")} for e in evidence],
            indent=2,
        )
        gaps_str = json.dumps(gaps, indent=2)
        template = get_prompt("writer", cfg, WRITER_PROMPT)
        prompt = template.format(
            report_outline=outline_str,
            writer_evidence=writer_evidence_str,
            knowledge_gaps=gaps_str,
            coverage_status=coverage_status,
            report_structure=report_structure,
            conflict_resolutions=conflict_resolutions,
        )

    log_prompt("write_report", prompt, model=model_name)
    llm = ChatOpenAI(model=model_name, temperature=0)
    raw = await llm.ainvoke([{"role": "user", "content": prompt}])
    report = raw.content if hasattr(raw, "content") else str(raw)
    report = report.strip()
    if report.startswith("```"):
        lines = report.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        report = "\n".join(lines)

    log_node_end("write_report", {"report_length": len(report), "evidence_count": len(evidence)})

    sources = []
    for i, e in enumerate(evidence, 1):
        sources.append({
            "index": i,
            "url": e.get("url", ""),
            "title": e.get("title", ""),
        })

    return {
        "report_markdown": report,
        "sources": sources,
    }
