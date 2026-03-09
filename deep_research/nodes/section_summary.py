"""generate_section_summary node - produce section summary artifact."""

import json

from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig

from deep_research.configuration import get_config
from deep_research.prompts import SECTION_SUMMARY_PROMPT
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

    prompt = SECTION_SUMMARY_PROMPT.format(
        section_id=section_id,
        section_title=section_title,
        section_goal=section_goal,
        evidence_count=len(evidence),
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
