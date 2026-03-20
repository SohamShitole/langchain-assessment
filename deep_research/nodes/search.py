"""run_search node - execute search queries via Gensee, Tavily, or Exa."""

import asyncio
import json
import logging
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from langchain_core.runnables import RunnableConfig

from deep_research.cache import SQLiteTTLCache, append_cache_write_log, stable_cache_key
from deep_research.configuration import (
    DEFAULT_CACHE_DB_PATH,
    DEFAULT_CACHE_ENABLED,
    DEFAULT_CACHE_LOG_VERBOSE,
    DEFAULT_SEARCH_CACHE_TTL_SECONDS,
    get_config,
)
from deep_research.research_logger import log_cache_event
from deep_research.state import ResearchState

GENSEE_BASE_URL = "https://app.gensee.ai"
GENSEE_SEARCH_ENDPOINT = f"{GENSEE_BASE_URL}/api/search"
GENSEE_DEEP_SEARCH_ENDPOINT = f"{GENSEE_BASE_URL}/api/deep-search"
logger = logging.getLogger(__name__)


def _cache_query_preview(q: str, max_len: int = 72) -> str:
    s = (q or "").strip().replace("\n", " ")
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _unwrap_langchain_tool_response(resp: object) -> dict:
    """Normalize Tavily tool output to a dict.

    ``ainvoke`` may return:
    - a plain ``dict`` (direct call, tool_call_id=None);
    - a ``ToolMessage`` whose ``content`` is JSON (when wrapped for tracing);
    - a dict with an ``error`` key on some failure paths;
    - an error **string** when Tavily raises ``ToolException`` and ``handle_tool_error=True``.
    """
    if isinstance(resp, dict):
        return resp
    # ToolMessage: full payload often in artifact, else JSON in content
    if hasattr(resp, "artifact"):
        art = getattr(resp, "artifact", None)
        if isinstance(art, dict) and ("results" in art or "query" in art):
            return art
    if hasattr(resp, "content"):
        c = getattr(resp, "content", None)
        if isinstance(c, dict):
            return c
        if isinstance(c, str):
            try:
                parsed = json.loads(c)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                # e.g. "No search results found for '...'" — not JSON
                return {"_tool_error_text": c[:500]}
    return {}


def _result_item_to_dict(x: object) -> dict | None:
    if isinstance(x, dict):
        return x
    md = getattr(x, "model_dump", None)
    if callable(md):
        try:
            out = md()
            return out if isinstance(out, dict) else None
        except Exception:
            pass
    d = getattr(x, "dict", None)
    if callable(d):
        try:
            out = d()
            return out if isinstance(out, dict) else None
        except Exception:
            pass
    return None


def _tavily_results_list(resp: object) -> list[dict]:
    """Extract Tavily ``results`` list; handles wrapped ToolMessage and Pydantic result rows."""
    d = _unwrap_langchain_tool_response(resp)
    if d.get("_tool_error_text"):
        logger.info(
            "[search] tavily tool reported no/error results: %s",
            (d["_tool_error_text"][:200] + "…")
            if len(d["_tool_error_text"]) > 200
            else d["_tool_error_text"],
        )
        return []
    if "error" in d and "results" not in d:
        logger.warning("[search] tavily tool error payload: %s", d.get("error"))
        return []
    raw = d.get("results")
    if raw is None:
        return []
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for x in raw:
        item = _result_item_to_dict(x)
        if item is not None:
            out.append(item)
    return out


def _normalize_search_results(raw: object) -> list[dict]:
    """Ensure list[dict]; APIs sometimes return None, Pydantic models, or mixed types."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for x in raw:
        item = _result_item_to_dict(x)
        if item is not None:
            out.append(item)
    return out


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


async def _gensee_search_async(query: str, api_key: str, max_results: int = 5, mode: str = "evidence") -> list[dict]:
    """Async Gensee Search API via httpx."""
    try:
        import httpx
    except ImportError:
        return await asyncio.to_thread(_gensee_search, query, api_key, max_results, mode)
    body = {
        "query": query,
        "max_results": max_results,
        "mode": mode,
        "timeout_seconds": 60,
    }
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                GENSEE_SEARCH_ENDPOINT,
                json=body,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []
    results = data.get("search_response") or []
    return results if isinstance(results, list) else []


async def _gensee_deep_search_async(query: str, api_key: str) -> list[dict]:
    """Async Gensee Deep Search API via httpx."""
    try:
        import httpx
    except ImportError:
        return await asyncio.to_thread(_gensee_deep_search, query, api_key)
    body = {"query": query, "timeout_seconds": 300}
    try:
        async with httpx.AsyncClient(timeout=360.0) as client:
            resp = await client.post(
                GENSEE_DEEP_SEARCH_ENDPOINT,
                json=body,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
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
    config: RunnableConfig | None = None,
) -> list[dict]:
    """Call Tavily Search API. Returns results with content and optionally raw_content.
    Pass config so the tool's LangSmith span uses the redacting client (avoids tracing raw data).
    """
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
        if config is not None:
            resp = tool.invoke({"query": query}, config=config)
        else:
            resp = tool.invoke({"query": query})
    except Exception:
        return []
    return _tavily_results_list(resp)


async def _tavily_search_async(
    query: str,
    max_results: int,
    search_depth: str = "advanced",
    include_raw_content: bool = True,
    config: RunnableConfig | None = None,
) -> list[dict]:
    """Async Tavily Search API."""
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
        if config is not None:
            resp = await tool.ainvoke({"query": query}, config=config)
        else:
            resp = await tool.ainvoke({"query": query})
    except Exception:
        return []
    return _tavily_results_list(resp)


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


async def _exa_search_async(
    query: str,
    max_results: int,
    search_type: str = "auto",
    max_chars: int = 20000,
) -> list[dict]:
    """Exa search run in thread to avoid blocking (exa-py is sync)."""
    return await asyncio.to_thread(_exa_search, query, max_results, search_type, max_chars)


async def _run_one_query_async(
    q: str,
    *,
    use_gensee_deep: bool,
    use_exa: bool,
    use_tavily: bool,
    use_gensee: bool,
    gensee_key: str,
    max_results: int,
    search_depth: str,
    include_raw_content: bool,
    full_page_max_chars: int,
    cache_enabled: bool = DEFAULT_CACHE_ENABLED,
    cache_db_path: str = DEFAULT_CACHE_DB_PATH,
    search_cache_ttl_seconds: int = DEFAULT_SEARCH_CACHE_TTL_SECONDS,
    cache_log_verbose: bool = DEFAULT_CACHE_LOG_VERBOSE,
    config: RunnableConfig | None = None,
) -> tuple[list[dict], dict[str, bool]]:
    """Run a single search query with the configured provider (async).

    Returns (results, cache_stats) where cache_stats has hit/miss/store flags.
    """
    cstat: dict[str, bool] = {"hit": False, "miss": False, "store": False}
    if not q or not str(q).strip():
        return [], cstat
    cache = None
    cache_key = ""
    provider_name = (
        "gensee_deep" if use_gensee_deep else
        "exa" if use_exa else
        "tavily" if use_tavily else
        "gensee" if use_gensee else
        "unknown"
    )
    if cache_enabled:
        cache_key = stable_cache_key(
            "search",
            {
                "provider": provider_name,
                "query": q.strip(),
                "max_results": max_results,
                "search_depth": search_depth,
                "include_raw_content": include_raw_content,
                "full_page_max_chars": full_page_max_chars,
            },
        )
        try:
            cache = SQLiteTTLCache(cache_db_path)
        except Exception as e:
            logger.warning(
                "[cache] SQLite open/ init failed path=%s (stores will be 0): %s",
                cache_db_path,
                e,
            )
            cache = None
        if cache is not None:
            try:
                cached = cache.get(cache_key)
                if isinstance(cached, list):
                    cstat["hit"] = True
                    if cache_log_verbose:
                        logger.info(
                            "[cache] search HIT provider=%s query=%r key_suffix=%s",
                            provider_name,
                            _cache_query_preview(q),
                            cache_key[-16:],
                        )
                    return cached, cstat
            except Exception as e:
                logger.warning(
                    "[cache] SQLite read failed path=%s (continuing without read): %s",
                    cache_db_path,
                    e,
                )
    try:
        results: list[dict] = []
        if cache_enabled:
            cstat["miss"] = True
            if cache_log_verbose:
                logger.info(
                    "[cache] search MISS provider=%s query=%r",
                    provider_name,
                    _cache_query_preview(q),
                )
        if use_gensee_deep:
            results = await _gensee_deep_search_async(q, gensee_key)
        elif use_exa:
            results = await _exa_search_async(q, max_results, search_type="auto", max_chars=full_page_max_chars)
        elif use_tavily:
            results = await _tavily_search_async(
                q, max_results, search_depth=search_depth,
                include_raw_content=include_raw_content, config=config,
            )
        elif use_gensee:
            results = await _gensee_search_async(q, gensee_key, max_results=max_results, mode="evidence")
        results = _normalize_search_results(results)
        if cache_enabled and cache_key and results and cache is None:
            logger.warning(
                "[cache] search SKIP STORE (no DB client) path=%s — check permissions or path",
                cache_db_path,
            )
        if cache and cache_key and results:
            try:
                cache.set(cache_key, results, int(search_cache_ttl_seconds))
                cstat["store"] = True
                n = len(results)
                _wmsg = (
                    f"[cache] wrote to SQLite | kind=search provider={provider_name} "
                    f"num_results={n} query={_cache_query_preview(q)!r} db={cache_db_path}"
                )
                logger.info(_wmsg)
                logging.getLogger().info(_wmsg)
                print(_wmsg, file=sys.stderr, flush=True)
                append_cache_write_log(_wmsg, db_path=cache_db_path)
                if cache_log_verbose:
                    logger.info(
                        "[cache] search STORE detail key_suffix=%s",
                        cache_key[-16:],
                    )
            except Exception as e:
                logger.warning(
                    "[cache] search STORE failed path=%s: %s",
                    cache_db_path,
                    e,
                )
        elif cache_enabled and cache_key and not results:
            _diag = (
                f"[cache] diagnostic | no STORE: 0 results from API | provider={provider_name} "
                f"query={_cache_query_preview(q)!r} sqlite_open={'ok' if cache is not None else 'FAILED'} "
                f"db={cache_db_path}"
            )
            logger.info(_diag)
            append_cache_write_log(_diag, db_path=cache_db_path)
            if cache_log_verbose:
                logger.info(
                    "[cache] search no STORE (empty results) provider=%s query=%r",
                    provider_name,
                    _cache_query_preview(q),
                )
        return results, cstat
    except Exception as e:
        logger.warning(
            "[cache] search query failed before cache store | query=%r: %s",
            _cache_query_preview(q),
            e,
            exc_info=True,
        )
    return [], cstat


async def run_search(state: ResearchState, config: RunnableConfig | None = None) -> dict:
    """Execute search queries via Gensee, Tavily, or Exa; append raw results, skip seen URLs.
    Queries are run in parallel with asyncio.gather.
    """
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
    cache_enabled = bool(cfg.get("cache_enabled", True))
    cache_db_path = str(cfg.get("cache_db_path", ".cache/research_cache.sqlite"))
    search_cache_ttl_seconds = int(cfg.get("search_cache_ttl_seconds", 21600))
    cache_log = bool(cfg.get("cache_log", True))
    cache_log_verbose = bool(cfg.get("cache_log_verbose", False))
    logger.info(
        "[search] using config | provider=%s max_queries=%s results_per_query=%s depth=%s include_raw=%s cache=%s ttl=%s",
        provider,
        max_queries,
        max_results,
        search_depth,
        include_raw_content,
        cache_enabled,
        search_cache_ttl_seconds,
    )

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
            "raw_search_results": [],
            "error_message": "Search API failed: No search provider configured or API key missing. Set GENSEE_API_KEY, TAVILY_API_KEY, or EXA_API_KEY.",
        }

    to_run = [q for q in queries[:max_queries] if q and str(q).strip()]
    if not to_run:
        return {"raw_search_results": []}

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
            cache_enabled=cache_enabled,
            cache_db_path=cache_db_path,
            search_cache_ttl_seconds=search_cache_ttl_seconds,
            cache_log_verbose=cache_log_verbose,
            config=config,
        )
        for q in to_run
    ]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    # If any query failed (e.g. rate limit, insufficient credits), stop the flow
    hits = misses = stores = 0
    for q, res in zip(to_run, results_list):
        if isinstance(res, Exception):
            return {
                "raw_search_results": [],
                "error_message": f"Search API failed: {res!s}",
            }
        _rows, cstat = res
        if cstat.get("hit"):
            hits += 1
        elif cache_enabled:
            misses += 1
        if cstat.get("store"):
            stores += 1

    if cache_enabled and cache_log:
        logger.info(
            "[cache] search batch: queries=%d hits=%d misses=%d stores=%d",
            len(to_run),
            hits,
            misses,
            stores,
        )
        log_cache_event(
            "search_batch",
            {"queries": len(to_run), "hits": hits, "misses": misses, "stores": stores},
        )

    new_results: list[dict] = []
    for q, res in zip(to_run, results_list):
        rows, _ = res
        for r in rows:
            if not isinstance(r, dict):
                continue
            url = r.get("url") or ""
            if not url or url in seen:
                continue
            new_results.append({"query": q, **r})

    return {"raw_search_results": new_results}
