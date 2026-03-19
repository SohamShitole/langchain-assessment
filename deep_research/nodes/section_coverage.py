"""section_assess_coverage node - assess single-section coverage."""

import json

from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field, model_validator

from deep_research.configuration import get_config
from deep_research.prompts import SECTION_COVERAGE_PROMPT, get_prompt
from deep_research.research_logger import log_decision, log_node_end, log_node_start, log_prompt
from deep_research.state import SectionWorkerState


class SectionGap(BaseModel):
    """A gap in section coverage."""

    description: str = Field(description="What is missing")
    critical: bool = Field(default=True, description="Whether critical")


class SectionCoverageOutput(BaseModel):
    """Output from section coverage assessment."""

    coverage_score: float = Field(description="0-10")
    gaps: list[SectionGap] = Field(default_factory=list, description="Identified gaps")
    section_complete: bool = Field(description="Whether section has enough evidence")
    reasoning: str = Field(default="", description="Brief explanation")

    @model_validator(mode="before")
    @classmethod
    def infer_section_complete(cls, data):
        if isinstance(data, dict) and "section_complete" not in data:
            data["section_complete"] = data.get("coverage_score", 0) >= 6
        return data


async def section_assess_coverage(
    state: SectionWorkerState,
    config: RunnableConfig | None = None,
) -> dict:
    """Assess whether this section has sufficient evidence."""
    section_task = state.get("section_task") or {}
    section_id = section_task.get("id", "")
    log_node_start("section_assess_coverage", config, section_id=section_id)
    evidence = list(state.get("section_evidence") or [])

    cfg = get_config(config)
    model_name = cfg.get("section_coverage_model") or "gpt-4o-mini"

    task_str = json.dumps(section_task, indent=2)
    success_criteria = section_task.get("success_criteria", [])
    criteria_str = json.dumps(success_criteria) if success_criteria else "N/A"

    evidence_summary = json.dumps(
        [{"url": e.get("url"), "relevance": e.get("relevance_score", 0)} for e in evidence],
        indent=2,
    )

    prompt = get_prompt("section_coverage", cfg, SECTION_COVERAGE_PROMPT).format(
        section_task=task_str,
        success_criteria=criteria_str,
        count=len(evidence),
        evidence_summary=evidence_summary,
    )
    log_prompt("section_assess_coverage", prompt, model=model_name)

    llm = ChatOpenAI(model=model_name, temperature=0)
    structured = llm.with_structured_output(
        SectionCoverageOutput, method="function_calling"
    )
    result = await structured.ainvoke([{"role": "user", "content": prompt}])

    gaps = [
        {"description": g.description, "critical": g.critical}
        for g in (result.gaps or [])
    ]
    log_decision(
        "section_assess_coverage",
        f"complete={result.section_complete}, score={result.coverage_score}",
        {"gaps": len(gaps), "reasoning": result.reasoning},
    )
    log_node_end("section_assess_coverage", {"section_complete": result.section_complete, "coverage_score": result.coverage_score})

    return {
        "section_coverage": result.coverage_score,
        "section_gaps": gaps,
        "section_complete": result.section_complete,
    }
