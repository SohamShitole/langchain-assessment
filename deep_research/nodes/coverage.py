"""assess_coverage node - decide if evidence is sufficient."""

import json

from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from deep_research.configuration import get_config
from deep_research.prompts import COVERAGE_PROMPT, get_prompt
from deep_research.state import ResearchState


class SectionScore(BaseModel):
    section_id: str = Field(description="Outline section ID")
    score: int = Field(description="Coverage score 0-10")
    evidence_count: int = Field(description="Number of evidence items")


class KnowledgeGap(BaseModel):
    section_id: str = Field(description="Outline section ID")
    description: str = Field(description="What is missing")
    critical: bool = Field(description="True if essential to report")


class CoverageOutput(BaseModel):
    section_scores: list[SectionScore] = Field(
        default_factory=list, description="Per-section coverage scores"
    )
    knowledge_gaps: list[KnowledgeGap] = Field(
        default_factory=list, description="Identified gaps"
    )
    coverage_status: str = Field(description="sufficient or insufficient")
    reasoning: str = Field(default="", description="Brief explanation")


def assess_coverage(
    state: ResearchState,
    config: RunnableConfig | None = None,
) -> dict:
    """Assess section-level coverage and set coverage_status."""
    outline = state.get("report_outline") or []
    evidence = state.get("evidence_items") or []
    cfg = get_config(config)
    model_name = cfg.get("coverage_model") or "gpt-4o-mini"

    # Build evidence summary per section
    section_counts: dict[str, int] = {}
    for e in evidence:
        for sid in (e.get("section_ids") or []):
            section_counts[sid] = section_counts.get(sid, 0) + 1
    for s in outline:
        sid = s.get("id") or ""
        if sid and sid not in section_counts:
            section_counts[sid] = 0
    evidence_summary = json.dumps(
        [{"section_id": k, "count": v} for k, v in section_counts.items()],
        indent=2,
    )
    outline_str = json.dumps(outline, indent=2)

    prompt = get_prompt("coverage", cfg, COVERAGE_PROMPT).format(
        report_outline=outline_str,
        evidence_summary=evidence_summary,
    )

    llm = ChatOpenAI(model=model_name, temperature=0)
    structured = llm.with_structured_output(CoverageOutput, method="function_calling")
    result = structured.invoke([{"role": "user", "content": prompt}])

    gaps = [
        {"section_id": g.section_id, "description": g.description, "critical": g.critical}
        for g in (result.knowledge_gaps or [])
    ]
    status = (result.coverage_status or "insufficient").lower()
    if status not in ("sufficient", "insufficient"):
        status = "insufficient"

    # If no critical gaps, force sufficient
    critical_gaps = [g for g in gaps if g.get("critical")]
    if not critical_gaps:
        status = "sufficient"

    return {
        "coverage_status": status,
        "knowledge_gaps": gaps,
    }
