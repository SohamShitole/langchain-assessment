"""write_sections node - write each section independently with its own evidence.

Avoids context-window overflow by splitting writing into per-section LLM calls.
Each call receives only that section's evidence with globally-consistent citation
indices, so the final assembly can concatenate without renumbering.
"""

import asyncio
import json

from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig

from deep_research.configuration import get_config
from deep_research.prompts import SECTION_DRAFT_PROMPT, get_prompt
from deep_research.research_logger import log_node_end, log_node_start, log_prompt
from deep_research.state import ResearchState

_SNIPPET_CAP = 8000


async def write_sections(
    state: ResearchState,
    config: RunnableConfig | None = None,
) -> dict:
    """Write each report section independently with only its relevant evidence.
    Section drafts are generated in parallel with asyncio.gather.
    """
    log_node_start("write_sections", config)

    outline = state.get("report_outline") or []
    evidence = state.get("writer_evidence_subset") or []
    section_summaries = state.get("section_summaries") or []
    cfg = get_config(config)
    model_name = cfg.get("writer_model") or "gpt-4o"

    # Build lookup: section_id -> summary
    summary_map: dict[str, dict] = {}
    for s in section_summaries:
        sid = s.get("section_id")
        if sid:
            summary_map[sid] = s

    # Assign stable global citation indices (1-based) used across all sections
    for i, e in enumerate(evidence):
        e["_cite_idx"] = i + 1

    # Bucket evidence by section_id
    section_evidence: dict[str, list[dict]] = {}
    for e in evidence:
        sids = e.get("section_ids") or e.get("supporting_sections") or []
        for sid in sids:
            section_evidence.setdefault(sid, []).append(e)

    llm = ChatOpenAI(model=model_name, temperature=0)

    async def write_one_section(section: dict) -> dict:
        sid = section.get("id", "")
        title = section.get("title", "")
        description = section.get("description", "")

        sec_ev = section_evidence.get(sid, [])
        summary = summary_map.get(sid, {})
        summary_text = summary.get("summary_text", "No summary available.")
        unresolved = summary.get("unresolved_questions", [])

        evidence_items = [
            {
                "citation_index": e["_cite_idx"],
                "url": e.get("url"),
                "title": e.get("title"),
                "snippet": (e.get("snippet") or "")[:_SNIPPET_CAP],
            }
            for e in sec_ev
        ]
        evidence_str = json.dumps(evidence_items, indent=2)

        prompt = get_prompt("section_draft", cfg, SECTION_DRAFT_PROMPT).format(
            section_title=title,
            section_description=description,
            section_summary=summary_text,
            unresolved_questions=json.dumps(unresolved),
            section_evidence=evidence_str,
            evidence_count=len(sec_ev),
        )

        log_prompt(f"write_section_{sid}", prompt, model=model_name)
        raw = await llm.ainvoke([{"role": "user", "content": prompt}])
        draft = raw.content if hasattr(raw, "content") else str(raw)

        return {
            "section_id": sid,
            "title": title,
            "draft": draft.strip(),
            "evidence_count": len(sec_ev),
        }

    section_drafts = await asyncio.gather(
        *[write_one_section(section) for section in outline],
        return_exceptions=True,
    )

    # Preserve order; replace exceptions with a placeholder draft
    out: list[dict] = []
    for i, section in enumerate(outline):
        res = section_drafts[i] if i < len(section_drafts) else None
        if isinstance(res, Exception):
            out.append({
                "section_id": section.get("id", ""),
                "title": section.get("title", ""),
                "draft": f"(Error writing section: {res})",
                "evidence_count": 0,
            })
        elif isinstance(res, dict):
            out.append(res)

    log_node_end("write_sections", {
        "sections_written": len(out),
        "total_evidence": len(evidence),
    })

    return {"section_drafts": out}
