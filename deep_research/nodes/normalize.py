"""normalize_and_map_evidence node - convert raw results to structured evidence."""

import json

from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from deep_research.configuration import get_config
from deep_research.prompts import NORMALIZE_PROMPT, get_prompt
from deep_research.state import ResearchState


class EvidenceItem(BaseModel):
    """Single evidence item."""

    url: str = Field(description="Source URL")
    title: str = Field(description="Source title")
    snippet: str = Field(description="Grounded excerpt")
    section_ids: list[str] = Field(default_factory=list, description="Outline section IDs")
    relevance_score: int = Field(description="1-10")
    credibility: str = Field(description="high, medium, or low")
    iteration: int = Field(description="Iteration found")


class NormalizeOutput(BaseModel):
    """Structured output for evidence extraction."""

    items: list[EvidenceItem] = Field(default_factory=list)


def normalize_and_map_evidence(
    state: ResearchState,
    config: RunnableConfig | None = None,
) -> dict:
    """Convert raw search results to structured evidence, dedupe, update seen_urls."""
    raw = list(state.get("raw_search_results") or [])
    outline = state.get("report_outline") or []
    iteration = state.get("iteration") or 1
    seen = set(state.get("seen_urls") or [])
    cfg = get_config(config)
    model_name = cfg.get("normalizer_model") or "gpt-4o-mini"

    # Use only the latest raw results (from this iteration)
    raw_for_prompt = raw[-50:] if len(raw) > 50 else raw
    # Prefer raw_content (full page) over content (snippet); use up to 2000 chars for LLM context
    _CONTENT_TRUNCATE = 2000
    raw_str = json.dumps(
        [
            {
                "url": r.get("url"),
                "title": r.get("title"),
                "content": (
                    (r.get("raw_content") or r.get("content") or "")[: _CONTENT_TRUNCATE]
                ),
            }
            for r in raw_for_prompt
        ],
        indent=2,
    )
    outline_str = json.dumps(outline, indent=2)

    prompt = get_prompt("normalize", cfg, NORMALIZE_PROMPT).format(
        report_outline=outline_str,
        raw_results=raw_str,
        iteration=iteration,
    )

    llm = ChatOpenAI(model=model_name, temperature=0)
    structured = llm.with_structured_output(NormalizeOutput, method="function_calling")
    result = structured.invoke([{"role": "user", "content": prompt}])

    url_to_raw: dict[str, str] = {
        (r.get("url") or ""): (r.get("raw_content") or "")
        for r in raw_for_prompt
        if r.get("raw_content")
    }
    new_items: list[dict] = []
    new_seen: set[str] = set()
    for item in result.items or []:
        if item.relevance_score < 5:
            continue
        if item.url in seen:
            continue
        obj = {
            "url": item.url,
            "title": item.title,
            "snippet": item.snippet,
            "section_ids": list(item.section_ids) if item.section_ids else [],
            "relevance_score": item.relevance_score,
            "credibility": item.credibility,
            "iteration": item.iteration,
        }
        if item.url and url_to_raw.get(item.url):
            obj["raw_content"] = url_to_raw[item.url]
        new_items.append(obj)
        new_seen.add(item.url)

    return {
        "evidence_items": new_items,
        "seen_urls": new_seen,
    }
