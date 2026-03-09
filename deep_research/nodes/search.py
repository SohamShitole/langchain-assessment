"""run_search node - execute search queries via Gensee, Tavily, or Exa."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from langchain_core.runnables import RunnableConfig

from deep_research.configuration import get_config
from deep_research.state import ResearchState

GENSEE_BASE_URL = "https://app.gensee.ai"
GENSEE_SEARCH_ENDPOINT = f"{GENSEE_BASE_URL}/api/search"
GENSEE_DEEP_SEARCH_ENDPOINT = f"{GENSEE_BASE_URL}/api/deep-search"


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


def _gensee_deep_search(query: str, api_key: str) -> list[dict]:
    """Call Gensee Deep Search API. Returns references normalized to {title, url, content}."""
    body = {"query": query, "timeout_seconds": 300}
    req = Request(
        GENSEE_DEEP_SEARCH_ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=360) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, json.JSONDecodeError):
        return []
    references = (data.get("result") or {}).get("references") or []
    return [
        {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("snippet", "")}
        for r in references
        if isinstance(r, dict)
    ]


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


def _exa_search(
    query: str,
    max_results: int,
    search_type: str = "auto",
    max_chars: int = 20000,
) -> list[dict]:
    """Call Exa Search API with full text. Returns results normalized to {title, url, content, raw_content}."""
    try:
        from exa_py import Exa
    except ImportError:
        print("[exa] exa-py not installed — run: pip install exa-py")
        return []
    api_key = (os.environ.get("EXA_API_KEY") or "").strip().strip('"').strip("'")
    if not api_key:
        print("[exa] EXA_API_KEY not set")
        return []
    exa = Exa(api_key=api_key)
    try:
        # Use search_and_contents to get text/highlights; search() alone may not return content
        response = exa.search_and_contents(
            query,
            type=search_type,
            num_results=max_results,
            text={"max_characters": max_chars},
        )
    except Exception as e:
        print(f"[exa] search failed: {e}")
        return []
    # Support both object (response.results) and dict (response["results"]) response shapes
    results = getattr(response, "results", None) or (response.get("results", []) if isinstance(response, dict) else [])
    if not isinstance(results, list):
        results = []
    out: list[dict] = []
    for r in results:
        # Support both object (.url, .title) and dict (["url"], ["title"]) result items
        url = r.get("url") if isinstance(r, dict) else getattr(r, "url", "") or ""
        if not url:
            continue
        title = r.get("title", "") if isinstance(r, dict) else getattr(r, "title", "") or ""
        raw = r.get("text", "") if isinstance(r, dict) else getattr(r, "text", None) or ""
        highlights = r.get("highlights") if isinstance(r, dict) else getattr(r, "highlights", None) or []
        if isinstance(highlights, str):
            highlights = [highlights] if highlights else []
        content = (highlights[0] if highlights else "") or (raw[:500] if raw else "")
        out.append({
            "title": title,
            "url": url,
            "content": content,
            "raw_content": raw,
        })
    return out


def run_search(state: ResearchState, config: RunnableConfig | None = None) -> dict:
    """Execute search queries via Gensee, Tavily, or Exa; append raw results, skip seen URLs."""
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
    full_page_max_chars = cfg.get("full_page_max_chars", 20000)

    gensee_key = (os.environ.get("GENSEE_API_KEY") or "").strip()
    tavily_key = (os.environ.get("TAVILY_API_KEY") or "").strip()
    exa_key = (os.environ.get("EXA_API_KEY") or "").strip()

    # Resolve provider: use config if key exists, else fallback exa -> tavily -> gensee
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
        return {"raw_search_results": []}

    new_results: list[dict] = []

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
