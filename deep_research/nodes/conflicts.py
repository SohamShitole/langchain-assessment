"""detect_global_gaps_and_conflicts and conflict_resolution_research nodes."""

import asyncio
import json
import os

from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from deep_research.configuration import get_config
from deep_research.nodes.search import _run_one_query_async
from deep_research.prompts import CONFLICT_ADJUDICATE_PROMPT, CONFLICT_DETECT_PROMPT, CONFLICT_RESOLVE_PROMPT, get_prompt
from deep_research.research_logger import log_decision, log_node_end, log_node_start, log_prompt
from deep_research.state import ResearchState


class ConflictOutput(BaseModel):
    """Output from conflict detection."""

    conflicts: list[dict] = Field(default_factory=list)
    conflict_resolution_needed: bool = Field(default=False)
    reasoning: str = Field(default="")


class ResolvedConflict(BaseModel):
    """A single conflict after adjudication."""

    conflicting_claims: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    section_ids: list[str] = Field(default_factory=list)
    severity: str = ""
    resolved: bool = False
    resolution_verdict: str = ""
    winning_claim: str = ""
    confidence: float = 0.5


class AdjudicationOutput(BaseModel):
    """Output from conflict adjudication."""

    resolved_conflicts: list[ResolvedConflict] = Field(default_factory=list)


async def detect_global_gaps_and_conflicts(
    state: ResearchState,
    config: RunnableConfig | None = None,
) -> dict:
    """Detect conflicting claims in merged evidence. Route to resolve or write."""
    log_node_start("detect_global_gaps_and_conflicts", config)
    merged = state.get("merged_evidence") or []
    cfg = get_config(config)
    model_name = cfg.get("conflict_detect_model") or "gpt-4o-mini"
    resolution_enabled = cfg.get("conflict_resolution_enabled", True)

    # Build summary for prompt (avoid token overflow; include evidence_meta for credibility/source_type)
    summary: list[dict] = []
    snippet_chars = 500  # slightly more context than 300 for better conflict detection
    for m in merged[:80]:
        meta = m.get("evidence_meta") or {}
        summary.append({
            "url": m.get("url", ""),
            "snippet": (m.get("snippet") or "")[:snippet_chars],
            "supporting_sections": m.get("supporting_sections", []),
            "credibility": meta.get("credibility"),
            "source_type": meta.get("source_type"),
            "credibility_score": meta.get("credibility_score"),
        })
    summary_str = json.dumps(summary, indent=2)

    prompt = get_prompt("conflict_detect", cfg, CONFLICT_DETECT_PROMPT).format(merged_evidence_summary=summary_str)
    log_prompt("detect_global_gaps_and_conflicts", prompt, model=model_name)

    llm = ChatOpenAI(model=model_name, temperature=0)
    structured = llm.with_structured_output(ConflictOutput, method="function_calling")
    result = await structured.ainvoke([{"role": "user", "content": prompt}])

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


async def conflict_resolution_research(
    state: ResearchState,
    config: RunnableConfig | None = None,
) -> dict:
    """Run targeted search to resolve conflicts, then adjudicate with LLM."""
    log_node_start("conflict_resolution_research", config)
    conflicts = state.get("global_conflicts") or []
    merged = list(state.get("merged_evidence") or [])
    cfg = get_config(config)
    model_name = cfg.get("conflict_resolver_model") or "gpt-4o-mini"

    conflicts_str = json.dumps(conflicts, indent=2)
    prompt = get_prompt("conflict_resolve", cfg, CONFLICT_RESOLVE_PROMPT).format(conflicts=conflicts_str)
    log_prompt("conflict_resolution_research", prompt, model=model_name)

    llm = ChatOpenAI(model=model_name, temperature=0)
    raw = await llm.ainvoke([{"role": "user", "content": prompt}])
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
    exa_key = (os.environ.get("EXA_API_KEY") or "").strip()
    provider = (cfg.get("search_provider") or "gensee").lower()
    max_results = cfg.get("results_per_query") or 5
    search_depth = cfg.get("search_depth") or "advanced"
    include_raw_content = cfg.get("include_raw_content", True)
    full_page_max_chars = cfg.get("full_page_max_chars", 20000)

    use_exa = provider == "exa" and exa_key
    use_tavily = provider == "tavily" and tavily_key
    use_gensee = bool(gensee_key)
    if use_exa:
        use_tavily = use_gensee = False
    elif use_tavily:
        use_gensee = False
    elif use_gensee:
        pass
    elif exa_key:
        use_exa = True
    elif tavily_key:
        use_tavily = True
    else:
        return {"global_conflicts": conflicts}

    seen_urls = {m.get("url") for m in merged if m.get("url")}
    gensee_key = (os.environ.get("GENSEE_API_KEY") or "").strip()
    use_gensee_deep = False

    tasks = [
        _run_one_query_async(
            q,
            use_gensee_deep=use_gensee_deep,
            use_exa=use_exa,
            use_tavily=use_tavily,
            use_gensee=use_gensee,
            gensee_key=gensee_key,
            max_results=max_results,
            search_depth=search_depth,
            include_raw_content=include_raw_content,
            full_page_max_chars=full_page_max_chars,
            config=config,
        )
        for q in queries
    ]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    new_items: list[dict] = []
    for res in results_list:
        if isinstance(res, Exception):
            continue
        for r in res:
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

    # --- LLM adjudication: weigh credibility, recency, primary-source status ---
    # Include both original conflicting evidence (from merged) and new disambiguation evidence with metadata when available
    orig_urls = {u for c in conflicts for u in (c.get("source_urls") or [])}
    orig_snippets = [m for m in merged if (m.get("url") or "") in orig_urls]
    new_evidence_summary = json.dumps(
        [{"url": item.get("url", ""), "snippet": (item.get("snippet") or "")[:500], "source": "disambiguation_search"} for item in new_items],
        indent=2,
    )
    orig_evidence_summary = json.dumps(
        [
            {
                "url": m.get("url", ""),
                "snippet": (m.get("snippet") or "")[:400],
                "evidence_meta": m.get("evidence_meta") or {},
            }
            for m in orig_snippets[:20]
        ],
        indent=2,
    )
    adjudication_prompt = get_prompt("conflict_adjudicate", cfg, CONFLICT_ADJUDICATE_PROMPT).format(
        conflicts=conflicts_str,
        new_evidence=new_evidence_summary,
        original_evidence=orig_evidence_summary,
    )
    log_prompt("conflict_adjudication", adjudication_prompt, model=model_name)

    try:
        adj_llm = ChatOpenAI(model=model_name, temperature=0)
        adj_structured = adj_llm.with_structured_output(AdjudicationOutput, method="function_calling")
        adj_result = await adj_structured.ainvoke([{"role": "user", "content": adjudication_prompt}])
        updated_conflicts = [rc.model_dump() for rc in adj_result.resolved_conflicts]
    except Exception:
        # Fallback: mark as unresolved with note
        updated_conflicts = []
        for c in conflicts:
            c = dict(c) if isinstance(c, dict) else {}
            c["resolved"] = False
            c["resolution_verdict"] = "Adjudication failed; additional research was gathered."
            updated_conflicts.append(c)

    log_node_end("conflict_resolution_research", {"queries_run": len(queries), "new_items_added": len(new_items), "adjudicated": len(updated_conflicts)})

    return {
        "merged_evidence": merged,
        "global_conflicts": updated_conflicts,
        "global_seen_urls": seen_urls,
    }


async def eval_stop_gate(
    state: ResearchState,
    config: RunnableConfig | None = None,
) -> dict:
    """Decision gate: run eval_stop_decision; route to more research or to prepare_writer_context."""
    log_node_start("eval_stop_gate", config)
    research_trace = state.get("research_trace") or {}
    knowledge_gaps = state.get("knowledge_gaps") or []
    retry_count = state.get("research_retry_count") or 0

    from deep_research.evals.stop_decision import async_eval_stop_decision

    score, reason = await async_eval_stop_decision(research_trace, knowledge_gaps)
    research_sufficient = score >= 0.6 or retry_count >= 1
    retry_count += 1

    log_decision("eval_stop_gate", f"score={score:.2f}, sufficient={research_sufficient}", {"reasoning": reason})
    log_node_end("eval_stop_gate", {"stop_eval_score": score, "research_sufficient": research_sufficient})

    return {
        "stop_eval_score": score,
        "research_sufficient": research_sufficient,
        "research_retry_count": retry_count,
    }
