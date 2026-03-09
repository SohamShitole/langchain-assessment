"""section_normalize node - convert raw results to enriched evidence with source quality."""

import json

from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from deep_research.configuration import get_config
from deep_research.prompts import SECTION_NORMALIZE_PROMPT
from deep_research.research_logger import log_node_end, log_node_start, log_prompt
from deep_research.state import SectionWorkerState


class SectionEvidenceItem(BaseModel):
    """Single evidence item with enriched source metadata."""

    url: str = Field(description="Source URL")
    title: str = Field(default="", description="Source title")
    snippet: str = Field(default="", description="Best passage from content")
    relevance_score: int = Field(default=5, description="1-10")
    credibility: str = Field(default="medium", description="high|medium|low")
    credibility_score: int = Field(default=5, description="1-10 numeric")
    source_type: str = Field(
        default="unknown",
        description="official|government|press|blog|aggregator|unknown",
    )
    recency: str = Field(default="unknown", description="recent|dated|unknown")
    novelty_flag: bool = Field(default=True, description="Adds new info")
    is_primary: bool = Field(default=False, description="Primary source")
    is_redundant: bool = Field(default=False, description="Redundant")


class SectionNormalizeOutput(BaseModel):
    """Output from section evidence extraction."""

    items: list[SectionEvidenceItem] = Field(default_factory=list)


def section_normalize(
    state: SectionWorkerState,
    config: RunnableConfig | None = None,
) -> dict:
    """Convert raw search results to enriched evidence with source quality metadata."""
    section_task = state.get("section_task") or {}
    section_id = section_task.get("id", "")
    log_node_start("section_normalize", config, section_id=section_id)

    raw = list(state.get("section_raw_results") or [])
    section_goal = section_task.get("goal", "")

    cfg = get_config(config)
    model_name = cfg.get("normalizer_model") or "gpt-4o-mini"

    _TRUNCATE = 2000
    raw_str = json.dumps(
        [
            {
                "url": r.get("url"),
                "title": r.get("title"),
                "content": (
                    (r.get("raw_content") or r.get("content") or "")[:_TRUNCATE]
                ),
            }
            for r in raw
        ],
        indent=2,
    )

    prompt = SECTION_NORMALIZE_PROMPT.format(
        section_id=section_id,
        section_goal=section_goal,
        raw_results=raw_str,
    )
    log_prompt("section_normalize", prompt, model=model_name)

    llm = ChatOpenAI(model=model_name, temperature=0)
    structured = llm.with_structured_output(
        SectionNormalizeOutput, method="function_calling"
    )
    result = structured.invoke([{"role": "user", "content": prompt}])

    url_to_raw: dict[str, str] = {
        (r.get("url") or ""): (r.get("raw_content") or r.get("content") or "")
        for r in raw
        if r.get("raw_content") or r.get("content")
    }

    new_items: list[dict] = []
    new_seen: set[str] = set()

    for item in result.items or []:
        if item.relevance_score < 5:
            continue
        snippet = item.snippet or url_to_raw.get(item.url, "")[:500] or item.title
        obj = {
            "url": item.url,
            "title": item.title or "Untitled",
            "snippet": snippet,
            "section_ids": [section_id],
            "relevance_score": item.relevance_score,
            "credibility": item.credibility,
            "credibility_score": item.credibility_score,
            "source_type": item.source_type,
            "recency": item.recency,
            "novelty_flag": item.novelty_flag,
            "is_primary": item.is_primary,
            "is_redundant": item.is_redundant,
            "found_by_section_id": section_id,
        }
        if item.url and url_to_raw.get(item.url):
            obj["raw_content"] = url_to_raw[item.url]
        new_items.append(obj)
        new_seen.add(item.url)

    log_node_end("section_normalize", {"raw_count": len(raw), "evidence_count": len(new_items)})
    return {
        "section_evidence": new_items,
        "section_seen_urls": new_seen,
    }
