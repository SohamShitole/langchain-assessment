"""section_search node - run search for one section's queries."""

import asyncio
import os

from langchain_core.runnables import RunnableConfig

from deep_research.configuration import get_config
from deep_research.nodes.search import _run_one_query_async
from deep_research.research_logger import log_node_end, log_node_start
from deep_research.state import SectionWorkerState


async def section_search(
    state: SectionWorkerState,
    config: RunnableConfig | None = None,
) -> dict:
    """Execute search for section-specific queries, skip global_seen_urls.
    Queries are run in parallel with asyncio.gather.
    """
    from dotenv import load_dotenv

    load_dotenv()

    section_id = (state.get("section_task") or {}).get("id", "")
    log_node_start("section_search", config, section_id=section_id)

    queries = state.get("section_queries") or []
    global_seen = state.get("global_seen_urls") or set()

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
        return {
            "section_raw_results": [],
            "section_seen_urls": set(),
            "error_message": "Search API failed: No search provider configured or API key missing. Set GENSEE_API_KEY, TAVILY_API_KEY, or EXA_API_KEY.",
        }

    to_run = [q for q in queries[:max_queries] if q and str(q).strip()]
    if not to_run:
        log_node_end("section_search", {"queries_run": 0, "results_count": 0, "new_urls": 0})
        return {"section_raw_results": [], "section_seen_urls": set()}

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
        for q in to_run
    ]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    # If any query failed (e.g. rate limit, insufficient credits), stop the flow
    for q, res in zip(to_run, results_list):
        if isinstance(res, Exception):
            log_node_end("section_search", {"error": str(res)})
            return {
                "section_raw_results": [],
                "section_seen_urls": set(),
                "error_message": f"Search API failed: {res!s}",
            }
    new_results: list[dict] = []
    new_seen: set[str] = set()
    for q, res in zip(to_run, results_list):
        for r in res:
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
