"""generate_section_summary node - produce section summary artifact."""

import json

from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig

from deep_research.configuration import get_config
from deep_research.prompts import SECTION_SUMMARY_PROMPT, get_prompt
from deep_research.research_logger import log_node_end, log_node_start, log_prompt
from deep_research.state import SectionWorkerState


def generate_section_summary(
    state: SectionWorkerState,
    config: RunnableConfig | None = None,
) -> dict:
    """Produce section summary: findings, strongest sources, unresolved questions, confidence."""
    section_task = state.get("section_task") or {}
    section_id = section_task.get("id", "")
    log_node_start("generate_section_summary", config, section_id=section_id)
    evidence = list(state.get("section_evidence") or [])

    cfg = get_config(config)
    model_name = cfg.get("section_summary_model") or "gpt-4o-mini"

    section_title = section_task.get("title", "")
    section_goal = section_task.get("goal", "")

    # Build evidence for the summary: either budget-based (full body up to N chars) or top-N with per-snippet cap
    top_n = cfg.get("section_summary_top_n", 25)
    snippet_chars = cfg.get("section_summary_snippet_chars", 1200)
    evidence_max_chars = cfg.get("section_summary_evidence_max_chars", 0) or 0

    sorted_evidence = sorted(
        evidence, key=lambda e: e.get("relevance_score", 0), reverse=True
    )

    if evidence_max_chars > 0:
        # Full evidence body: include as many items as fit within the character budget
        lines: list[str] = []
        used = 0
        sep_len = 2  # "\n\n"
        for i, e in enumerate(sorted_evidence):
            snip = (e.get("snippet") or "").strip()
            if not snip:
                continue
            prefix = f"[{i+1}] ({e.get('url', 'N/A')}): "
            need = (sep_len if lines else 0) + len(prefix) + len(snip)
            if used + need > evidence_max_chars:
                remaining = evidence_max_chars - used - (sep_len if lines else 0) - len(prefix) - 3  # 3 for "..."
                if remaining > 100:
                    snip = snip[:remaining] + "..."
                else:
                    break
            line = prefix + snip
            lines.append(line)
            used += (sep_len if lines else 0) + len(line)
            if used >= evidence_max_chars:
                break
        top_evidence = "\n\n".join(lines) if lines else "(No evidence text)"
    else:
        # Top-N with per-snippet character cap
        selected = sorted_evidence[:top_n]
        top_evidence = "\n\n".join(
            f"[{i+1}] ({e.get('url', 'N/A')}): {(e.get('snippet') or '')[:snippet_chars]}"
            for i, e in enumerate(selected)
        )

    prompt = get_prompt("section_summary", cfg, SECTION_SUMMARY_PROMPT).format(
        section_id=section_id,
        section_title=section_title,
        section_goal=section_goal,
        evidence_count=len(evidence),
        top_evidence=top_evidence,
    )
    log_prompt("generate_section_summary", prompt, model=model_name)

    llm = ChatOpenAI(model=model_name, temperature=0)
    raw = llm.invoke([{"role": "user", "content": prompt}])
    text = raw.content if hasattr(raw, "content") else str(raw)

    text = text.strip()
    if "```" in text:
        for block in ("json", ""):
            start = f"```{block}"
            if start in text:
                i = text.find(start) + len(start)
                j = text.find("```", i)
                if j > i:
                    text = text[i:j].strip()
                    break

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {
            "summary_text": "No summary generated.",
            "strongest_sources": [],
            "unresolved_questions": [],
            "confidence": 0.5,
        }

    summary = {
        "section_id": section_id,
        "summary_text": data.get("summary_text", ""),
        "strongest_sources": data.get("strongest_sources") or [],
        "unresolved_questions": data.get("unresolved_questions") or [],
        "confidence": float(data.get("confidence", 0.5)),
    }

    log_node_end("generate_section_summary", {"confidence": summary.get("confidence"), "evidence_count": len(evidence)})

    # Build SectionResult for parent graph (section_results has operator.add reducer)
    section_result = {
        "section_id": section_id,
        "section_title": section_title,
        "evidence": evidence,
        "coverage_score": state.get("section_coverage") or 0.0,
        "gaps": state.get("section_gaps") or [],
        "summary": summary,
        "confidence": summary.get("confidence", 0.5),
    }

    return {
        "section_summary": summary,
        "section_results": [section_result],
    }
