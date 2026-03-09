"""section_search node - run search for one section's queries."""

import os

from langchain_core.runnables import RunnableConfig

from deep_research.configuration import get_config
from deep_research.nodes.search import _exa_search, _gensee_deep_search, _gensee_search, _tavily_search
from deep_research.research_logger import log_node_end, log_node_start
from deep_research.state import SectionWorkerState


def section_search(
    state: SectionWorkerState,
    config: RunnableConfig | None = None,
) -> dict:
    """Execute search for section-specific queries, skip global_seen_urls."""
    from dotenv import load_dotenv

    load_dotenv()

    section_id = (state.get("section_task") or {}).get("id", "")
    log_node_start("section_search", config, section_id=section_id)

    queries = state.get("section_queries") or []
    global_seen = state.get("global_seen_urls") or set()
    section_id = (state.get("section_task") or {}).get("id", "")

    cfg = get_config(config)
    max_queries = cfg.get("section_queries_per_iteration") or 3
    max_results = cfg.get("results_per_query") or 5
    provider = (cfg.get("search_provider") or "gensee").lower()
    search_depth = cfg.get("search_depth") or "advanced"
    include_raw_content = cfg.get("include_raw_content", True)
    full_page_max_chars = cfg.get("full_page_max_chars", 20000)

    gensee_key = (os.environ.get("GENSEE_API_KEY") or "").strip()
    tavily_key = (os.environ.get("TAVILY_API_KEY") or "").strip()
    exa_key = (os.environ.get("EXA_API_KEY") or "").strip()

    use_gensee_deep = provider == "gensee_deep" and gensee_key
    use_exa = provider == "exa" and exa_key
    use_tavily = provider == "tavily" and tavily_key
    use_gensee = provider == "gensee" and gensee_key
    if use_gensee_deep:
        use_exa = use_tavily = use_gensee = False
    elif use_exa:
        use_tavily = use_gensee = False
    elif use_tavily:
        use_gensee = False
    elif use_gensee:
        pass
    elif exa_key:
        use_exa = True
    elif tavily_key:
        use_tavily = True
    elif gensee_key:
        use_gensee = True
    else:
        return {"section_raw_results": [], "section_seen_urls": set()}

    new_results: list[dict] = []
    new_seen: set[str] = set()

    for q in queries[:max_queries]:
        if not q or not str(q).strip():
            continue
        try:
            if use_gensee_deep:
                results = _gensee_deep_search(q, gensee_key)
            elif use_exa:
                results = _exa_search(q, max_results, search_type="auto", max_chars=full_page_max_chars)
            elif use_tavily:
                results = _tavily_search(
                    q,
                    max_results,
                    search_depth=search_depth,
                    include_raw_content=include_raw_content,
                )
            else:
                results = _gensee_search(
                    q, gensee_key, max_results=max_results, mode="evidence"
                )
        except Exception:
            continue
        for r in results:
            if not isinstance(r, dict):
                continue
            url = r.get("url") or ""
            if not url or url in global_seen:
                continue
            new_results.append({"query": q, "section_id": section_id, **r})
            new_seen.add(url)

    log_node_end("section_search", {"queries_run": len(queries), "results_count": len(new_results), "new_urls": len(new_seen)})
    return {
        "section_raw_results": new_results,
        "section_seen_urls": new_seen,
    }
