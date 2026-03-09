"""run_search node - execute search queries via Gensee or Tavily."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from langchain_core.runnables import RunnableConfig

from deep_research.configuration import get_config
from deep_research.state import ResearchState

GENSEE_BASE_URL = "https://app.gensee.ai"
GENSEE_SEARCH_ENDPOINT = f"{GENSEE_BASE_URL}/api/search"


def _gensee_search(query: str, api_key: str, max_results: int = 5, mode: str = "evidence") -> list[dict]:
    """Call Gensee Search API. mode: 'evidence' (raw content) or 'digest' (summarized)."""
    body = {
        "query": query,
        "max_results": max_results,
        "mode": mode,
        "timeout_seconds": 60,
    }
    req = Request(
        GENSEE_SEARCH_ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, json.JSONDecodeError):
        return []
    results = data.get("search_response") or []
    return results if isinstance(results, list) else []


def _tavily_search(
    query: str,
    max_results: int,
    search_depth: str = "advanced",
    include_raw_content: bool = True,
) -> list[dict]:
    """Call Tavily Search API. Returns results with content and optionally raw_content."""
    try:
        from langchain_tavily import TavilySearch
    except ImportError:
        return []
    tool = TavilySearch(
        max_results=max_results,
        topic="general",
        search_depth=search_depth,
        include_raw_content=include_raw_content,
    )
    try:
        resp = tool.invoke({"query": query})
    except Exception:
        return []
    return resp.get("results", []) if isinstance(resp, dict) else []


def run_search(state: ResearchState, config: RunnableConfig | None = None) -> dict:
    """Execute search queries via Gensee or Tavily, append raw results, skip seen URLs."""
    from dotenv import load_dotenv
    load_dotenv()

    queries = state.get("search_queries") or []
    seen = state.get("seen_urls") or set()

    cfg = get_config(config)
    max_queries = cfg["queries_per_iteration"]
    max_results = cfg["results_per_query"]
    provider = (cfg.get("search_provider") or "gensee").lower()
    search_depth = cfg.get("search_depth") or "advanced"
    include_raw_content = cfg.get("include_raw_content", True)

    gensee_key = (os.environ.get("GENSEE_API_KEY") or "").strip()
    tavily_key = (os.environ.get("TAVILY_API_KEY") or "").strip()

    # Resolve provider: use config if key exists, else try the other
    if provider == "tavily" and tavily_key:
        use_tavily = True
    elif provider == "gensee" and gensee_key:
        use_tavily = False
    elif tavily_key:
        use_tavily = True
    elif gensee_key:
        use_tavily = False
    else:
        return {"raw_search_results": []}

    new_results: list[dict] = []

    for q in queries[:max_queries]:
        if not q or not str(q).strip():
            continue
        try:
            if use_tavily:
                results = _tavily_search(
                    q,
                    max_results,
                    search_depth=search_depth,
                    include_raw_content=include_raw_content,
                )
            else:
                results = _gensee_search(q, gensee_key, max_results=max_results, mode="evidence")
        except Exception:
            continue
        for r in results:
            if not isinstance(r, dict):
                continue
            url = r.get("url") or ""
            if not url or url in seen:
                continue
            new_results.append({"query": q, **r})

    return {"raw_search_results": new_results}
