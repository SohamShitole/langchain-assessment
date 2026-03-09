"""write_report node - generate grounded markdown report."""

import json

from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig

from deep_research.configuration import get_config
from deep_research.prompts import ENHANCED_WRITER_PROMPT, REPORT_ASSEMBLY_PROMPT, WRITER_PROMPT
from deep_research.research_logger import log_node_end, log_node_start, log_prompt
from deep_research.state import ResearchState


def write_report(state: ResearchState, config: RunnableConfig | None = None) -> dict:
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
    gaps = state.get("knowledge_gaps") or []
    coverage_status = state.get("coverage_status") or "insufficient"
    max_iterations = state.get("max_iterations") or 3
    iteration = state.get("iteration") or 1
    section_summaries = state.get("section_summaries") or []
    section_drafts = state.get("section_drafts") or []
    global_conflicts = state.get("global_conflicts") or []
    cfg = get_config(config)
    model_name = cfg.get("writer_model") or "gpt-4o"

    outline_str = json.dumps(outline, indent=2)

    if section_drafts:
        # ── Assembly mode: stitch pre-written section drafts ──
        drafts_str = "\n\n---\n\n".join(
            f"### Section: {d['title']}\n\n{d['draft']}" for d in section_drafts
        )
        conflicts_str = json.dumps(global_conflicts, indent=2)
        conflicts_and_caveats = (
            f"Conflicts: {conflicts_str}\n\nGaps: {json.dumps(gaps, indent=2)}"
        )
        sources_str = "\n".join(
            f"[{i + 1}] {e.get('url', '')} — *{e.get('title', 'Untitled')}*"
            for i, e in enumerate(evidence)
        )
        prompt = REPORT_ASSEMBLY_PROMPT.format(
            report_outline=outline_str,
            section_drafts=drafts_str,
            conflicts_and_caveats=conflicts_and_caveats,
            sources_list=sources_str,
        )
    elif section_summaries:
        # ── Enhanced mode (legacy Phase 2, no section drafts) ──
        writer_evidence_str = json.dumps(
            [{"url": e.get("url"), "title": e.get("title"), "snippet": e.get("snippet")} for e in evidence],
            indent=2,
        )
        summaries_str = json.dumps(section_summaries, indent=2)
        conflicts_str = json.dumps(global_conflicts, indent=2)
        conflicts_and_caveats = (
            f"Conflicts: {conflicts_str}\n\nGaps: {json.dumps(gaps, indent=2)}"
        )
        prompt = ENHANCED_WRITER_PROMPT.format(
            report_outline=outline_str,
            section_summaries=summaries_str,
            writer_evidence=writer_evidence_str,
            conflicts_and_caveats=conflicts_and_caveats,
        )
    else:
        # ── Basic mode (Phase 1) ──
        writer_evidence_str = json.dumps(
            [{"url": e.get("url"), "title": e.get("title"), "snippet": e.get("snippet")} for e in evidence],
            indent=2,
        )
        gaps_str = json.dumps(gaps, indent=2)
        prompt = WRITER_PROMPT.format(
            report_outline=outline_str,
            writer_evidence=writer_evidence_str,
            knowledge_gaps=gaps_str,
            coverage_status=coverage_status,
        )
        if iteration >= max_iterations and coverage_status == "insufficient":
            prompt += "\n\nNote: The iteration budget was exhausted. Include a clear Caveats section noting that coverage may be incomplete."

    log_prompt("write_report", prompt, model=model_name)
    llm = ChatOpenAI(model=model_name, temperature=0)
    raw = llm.invoke([{"role": "user", "content": prompt}])
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
