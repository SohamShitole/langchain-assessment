"""detect_global_gaps_and_conflicts and conflict_resolution_research nodes."""

import json
import os

from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from deep_research.configuration import get_config
from deep_research.nodes.search import _gensee_search, _tavily_search
from deep_research.prompts import CONFLICT_DETECT_PROMPT, CONFLICT_RESOLVE_PROMPT
from deep_research.research_logger import log_decision, log_node_end, log_node_start, log_prompt
from deep_research.state import ResearchState


class ConflictOutput(BaseModel):
    """Output from conflict detection."""

    conflicts: list[dict] = Field(default_factory=list)
    conflict_resolution_needed: bool = Field(default=False)
    reasoning: str = Field(default="")


def detect_global_gaps_and_conflicts(
    state: ResearchState,
    config: RunnableConfig | None = None,
) -> dict:
    """Detect conflicting claims in merged evidence. Route to resolve or write."""
    log_node_start("detect_global_gaps_and_conflicts", config)
    merged = state.get("merged_evidence") or []
    cfg = get_config(config)
    model_name = cfg.get("conflict_detect_model") or "gpt-4o-mini"
    resolution_enabled = cfg.get("conflict_resolution_enabled", True)

    # Build summary for prompt (avoid token overflow)
    summary: list[dict] = []
    for m in merged[:80]:
        summary.append({
            "url": m.get("url", ""),
            "snippet": (m.get("snippet") or "")[:300],
            "supporting_sections": m.get("supporting_sections", []),
        })
    summary_str = json.dumps(summary, indent=2)

    prompt = CONFLICT_DETECT_PROMPT.format(merged_evidence_summary=summary_str)
    log_prompt("detect_global_gaps_and_conflicts", prompt, model=model_name)

    llm = ChatOpenAI(model=model_name, temperature=0)
    structured = llm.with_structured_output(ConflictOutput, method="function_calling")
    result = structured.invoke([{"role": "user", "content": prompt}])

    conflicts = result.conflicts or []
    conflict_resolution_needed = result.conflict_resolution_needed and bool(conflicts)

    log_decision("detect_global_gaps_and_conflicts", f"conflicts={len(conflicts)}, resolution_needed={conflict_resolution_needed}", {"reasoning": result.reasoning})
    log_node_end("detect_global_gaps_and_conflicts", {"conflicts_count": len(conflicts), "conflict_resolution_needed": conflict_resolution_needed})

    trace = dict(state.get("research_trace") or {})
    trace["conflicts_detected"] = len(conflicts)
    trace["conflict_resolution_needed"] = conflict_resolution_needed

    return {
        "global_conflicts": conflicts,
        "conflict_resolution_needed": conflict_resolution_needed,
        "conflict_resolution_enabled": resolution_enabled,
        "research_trace": trace,
    }


def conflict_resolution_research(
    state: ResearchState,
    config: RunnableConfig | None = None,
) -> dict:
    """Run targeted search to resolve conflicts. Update merged_evidence."""
    log_node_start("conflict_resolution_research", config)
    conflicts = state.get("global_conflicts") or []
    merged = list(state.get("merged_evidence") or [])
    cfg = get_config(config)
    model_name = cfg.get("conflict_resolver_model") or "gpt-4o-mini"

    conflicts_str = json.dumps(conflicts, indent=2)
    prompt = CONFLICT_RESOLVE_PROMPT.format(conflicts=conflicts_str)
    log_prompt("conflict_resolution_research", prompt, model=model_name)

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
        data = {"search_queries": []}

    queries = data.get("search_queries") or []
    if not isinstance(queries, list):
        queries = [str(queries)] if queries else []
    queries = [str(q).strip() for q in queries if q][:4]

    if not queries:
        return {"global_conflicts": conflicts}

    from dotenv import load_dotenv
    load_dotenv()

    gensee_key = (os.environ.get("GENSEE_API_KEY") or "").strip()
    tavily_key = (os.environ.get("TAVILY_API_KEY") or "").strip()
    provider = (cfg.get("search_provider") or "gensee").lower()
    max_results = cfg.get("results_per_query") or 5
    search_depth = cfg.get("search_depth") or "advanced"
    include_raw_content = cfg.get("include_raw_content", True)

    if provider == "tavily" and tavily_key:
        use_tavily = True
    elif gensee_key:
        use_tavily = False
    elif tavily_key:
        use_tavily = True
    else:
        return {"global_conflicts": conflicts}

    seen_urls = {m.get("url") for m in merged if m.get("url")}
    new_items: list[dict] = []

    for q in queries:
        try:
            if use_tavily:
                results = _tavily_search(
                    q, max_results,
                    search_depth=search_depth,
                    include_raw_content=include_raw_content,
                )
            else:
                results = _gensee_search(q, gensee_key, max_results=max_results)
        except Exception:
            continue
        for r in results:
            if not isinstance(r, dict):
                continue
            url = r.get("url") or ""
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            snippet = r.get("raw_content") or r.get("content") or ""
            if len(snippet) > 2000:
                snippet = snippet[:2000] + "..."
            new_items.append({
                "url": url,
                "title": r.get("title", ""),
                "snippet": snippet,
                "supporting_sections": [],
                "cross_cutting": True,
                "evidence_meta": {"source": "conflict_resolution", "is_primary": True},
            })

    merged = merged + new_items

    log_node_end("conflict_resolution_research", {"queries_run": len(queries), "new_items_added": len(new_items)})

    # Mark conflicts as resolved (simplified - full resolution would need LLM)
    updated_conflicts = []
    for c in conflicts:
        c = dict(c) if isinstance(c, dict) else {}
        c["resolved"] = True
        c["resolution_note"] = "Additional research conducted; prioritize primary sources in report."
        updated_conflicts.append(c)

    return {
        "merged_evidence": merged,
        "global_conflicts": updated_conflicts,
        "global_seen_urls": seen_urls,
    }
