"""prepare_writer_context node - curate evidence subset for the writer."""

import asyncio
import logging
import re
import ssl
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen

from langchain_core.runnables import RunnableConfig

from deep_research.cache import SQLiteTTLCache, append_cache_write_log, stable_cache_key
from deep_research.configuration import get_config
from deep_research.research_logger import log_cache_event, log_node_end, log_node_start
from deep_research.state import ResearchState

logger = logging.getLogger(__name__)

# Optional: trafilatura for fallback extraction (install: pip install trafilatura)
try:
    import trafilatura

    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False

_TAG_RE = re.compile(r"<[^>]+>")


def _cache_url_preview(url: str, max_len: int = 72) -> str:
    u = (url or "").strip()
    if len(u) <= max_len:
        return u
    return u[: max_len - 3] + "..."


def _strip_html(html: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    text = _TAG_RE.sub(" ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _exa_get_contents(urls: list[str], max_chars: int = 5000) -> dict[str, str]:
    """Extract content from URLs via Exa get_contents API. Returns url -> raw_content map."""
    if not urls:
        return {}
    import os
    api_key = (os.environ.get("EXA_API_KEY") or "").strip().strip('"').strip("'")
    if not api_key:
        return {}
    try:
        from exa_py import Exa
    except ImportError:
        return {}
    exa = Exa(api_key=api_key)
    try:
        response = exa.get_contents(urls, text={"max_characters": max_chars})
    except Exception:
        return {}
    results = getattr(response, "results", None) or []
    out: dict[str, str] = {}
    for r in results:
        url = getattr(r, "url", None) or getattr(r, "id", "") or ""
        if not url:
            continue
        raw = getattr(r, "text", None) or ""
        if raw:
            out[url] = raw[:max_chars]
    return out


async def _exa_get_contents_async(urls: list[str], max_chars: int = 5000) -> dict[str, str]:
    """Async wrapper for Exa get_contents (runs in thread)."""
    if not urls:
        return {}
    return await asyncio.to_thread(_exa_get_contents, urls, max_chars)


def _tavily_extract(
    urls: list[str], extract_depth: str = "basic", max_chars: int = 5000
) -> dict[str, str]:
    """Extract content from URLs via Tavily Extract API. Returns url -> raw_content map."""
    if not urls:
        return {}
    try:
        from langchain_tavily import TavilyExtract
    except ImportError:
        return {}
    tool = TavilyExtract(extract_depth=extract_depth)
    try:
        resp = tool.invoke({"urls": urls})
    except Exception:
        return {}
    if not isinstance(resp, dict):
        return {}
    results = resp.get("results") or []
    out: dict[str, str] = {}
    for r in results:
        if not isinstance(r, dict):
            continue
        url = r.get("url") or ""
        raw = r.get("raw_content") or ""
        if url and raw:
            out[url] = raw[:max_chars]
    return out


async def _tavily_extract_async(
    urls: list[str], extract_depth: str = "basic", max_chars: int = 5000
) -> dict[str, str]:
    """Async Tavily Extract."""
    if not urls:
        return {}
    try:
        from langchain_tavily import TavilyExtract
    except ImportError:
        return {}
    tool = TavilyExtract(extract_depth=extract_depth)
    try:
        resp = await tool.ainvoke({"urls": urls})
    except Exception:
        return {}
    if not isinstance(resp, dict):
        return {}
    results = resp.get("results") or []
    out: dict[str, str] = {}
    for r in results:
        if not isinstance(r, dict):
            continue
        url = r.get("url") or ""
        raw = r.get("raw_content") or ""
        if url and raw:
            out[url] = raw[:max_chars]
    return out


def _fetch_full_page(url: str, max_chars: int) -> str | None:
    """Fetch and extract main text from URL (trafilatura fallback). Returns None on failure."""
    try:
        if TRAFILATURA_AVAILABLE:
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(downloaded)
                if text:
                    return text[:max_chars]
        # Fallback: stdlib fetch + strip HTML
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"})
        with urlopen(req, timeout=10, context=ctx) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        return _strip_html(html)[:max_chars] or None
    except (URLError, OSError, UnicodeDecodeError, Exception):
        return None


async def _fetch_full_page_async(url: str, max_chars: int) -> tuple[str, str | None]:
    """Fetch full page in thread; returns (url, content)."""
    content = await asyncio.to_thread(_fetch_full_page, url, max_chars)
    return (url, content)


async def prepare_writer_context(
    state: ResearchState,
    config: RunnableConfig | None = None,
) -> dict:
    """Rank evidence, ensure section coverage, cap volume, output writer_evidence_subset.
    Phase 2: uses merged_evidence and supporting_sections when available.
    Full-page enrichment uses async Tavily/Exa and parallel trafilatura fallback.
    """
    log_node_start("prepare_writer_context", config)
    # Prefer Phase 2 merged_evidence; fallback to Phase 1 evidence_items
    merged = list(state.get("merged_evidence") or [])
    evidence = list(state.get("evidence_items") or [])
    if merged:
        # Convert merged format to writer format; use supporting_sections as section_ids
        evidence = [
            {
                "url": m.get("url", ""),
                "title": m.get("title", ""),
                "snippet": m.get("snippet", ""),
                "section_ids": m.get("supporting_sections", []),
                "relevance_score": m.get("evidence_meta", {}).get("relevance_score", 7),
                "is_primary": m.get("evidence_meta", {}).get("is_primary", False),
                "cross_cutting": m.get("cross_cutting", False),
                **m.get("evidence_meta", {}),
            }
            for m in merged
        ]
    elif not evidence:
        return {"writer_evidence_subset": []}

    outline = list(state.get("report_outline") or [])
    section_ids = [s.get("id") for s in outline if s.get("id")]

    cfg = get_config(config)
    max_items = cfg["writer_context_max_items"]
    fetch_full = cfg.get("fetch_full_pages", False)
    max_chars = cfg.get("full_page_max_chars", 5000)
    extract_depth = cfg.get("extract_depth") or "basic"
    cache_enabled = bool(cfg.get("cache_enabled", True))
    cache_db_path = str(cfg.get("cache_db_path", ".cache/research_cache.sqlite"))
    full_page_cache_ttl_seconds = int(cfg.get("full_page_cache_ttl_seconds", 43200))
    cache_log = bool(cfg.get("cache_log", True))
    cache_log_verbose = bool(cfg.get("cache_log_verbose", False))

    # Score: prefer primary, higher relevance; deprioritize redundant
    def _score(e: dict) -> float:
        r = float(e.get("relevance_score", 0) or 0)
        if e.get("is_primary"):
            r += 2.0
        if e.get("is_redundant"):
            r -= 2.0
        return r

    scored = [(e, _score(e)) for e in evidence if isinstance(e, dict)]
    scored.sort(key=lambda x: x[1], reverse=True)

    chosen: list[dict] = []
    used_urls: set[str] = set()
    section_covered: set[str] = set()

    # Reserve slots per section; ensure at least one per section
    for sid in section_ids:
        for e, _ in scored:
            url = (e.get("url") or "").strip()
            if not url or url in used_urls:
                continue
            ids = e.get("section_ids") or e.get("supporting_sections") or []
            if sid in ids or (not ids and not section_covered):
                chosen.append(e)
                used_urls.add(url)
                section_covered.add(sid)
                for i in ids:
                    section_covered.add(i)
                break

    # Add cross-cutting sources
    for e, _ in scored:
        if e.get("cross_cutting") and (e.get("url") or "").strip() not in used_urls:
            if len(chosen) < max_items:
                chosen.append(e)
                used_urls.add((e.get("url") or "").strip())

    # Fill remainder by relevance
    for e, _ in scored:
        if len(chosen) >= max_items:
            break
        url = (e.get("url") or "").strip()
        if not url or url in used_urls:
            continue
        chosen.append(e)
        used_urls.add(url)

    # Enrich with full page content when enabled (async: Tavily -> Exa -> parallel trafilatura)
    if fetch_full:
        cache: SQLiteTTLCache | None = None
        if cache_enabled:
            try:
                cache = SQLiteTTLCache(cache_db_path)
            except Exception:
                cache = None
        enriched: list[dict] = []
        needs_extract: list[str] = []
        fp_hits = fp_misses = fp_stores = 0
        for item in chosen:
            url = (item.get("url") or "").strip()
            if not url or not url.startswith("http"):
                enriched.append(dict(item))
                continue
            raw = item.get("raw_content") or ""
            if raw:
                full_text = raw[:max_chars]
                if len(full_text) > len(item.get("snippet") or ""):
                    item = dict(item)
                    item["snippet"] = full_text
                enriched.append(item)
            else:
                cached_text = None
                if cache:
                    cache_key = stable_cache_key(
                        "full_page_extract",
                        {"url": url, "extract_depth": extract_depth, "max_chars": max_chars},
                    )
                    try:
                        candidate = cache.get(cache_key)
                        if isinstance(candidate, str) and candidate:
                            cached_text = candidate[:max_chars]
                    except Exception:
                        pass
                if cached_text:
                    fp_hits += 1
                    if cache_log_verbose:
                        logger.info(
                            "[cache] full_page HIT url=%r key_ctx=depth=%s max_chars=%s",
                            _cache_url_preview(url),
                            extract_depth,
                            max_chars,
                        )
                    item = dict(item)
                    if len(cached_text) > len(item.get("snippet") or ""):
                        item["snippet"] = cached_text
                    enriched.append(item)
                else:
                    fp_misses += 1
                    if cache_log_verbose:
                        logger.info(
                            "[cache] full_page MISS url=%r (will fetch)",
                            _cache_url_preview(url),
                        )
                    needs_extract.append(url)
                    enriched.append(dict(item))

        if needs_extract:
            extracted = await _tavily_extract_async(
                needs_extract, extract_depth=extract_depth, max_chars=max_chars
            )
            still_needed = [u for u in needs_extract if not extracted.get(u)]
            if still_needed:
                extracted.update(await _exa_get_contents_async(still_needed, max_chars))
            still_needed = [u for u in still_needed if not extracted.get(u)]
            # Parallel trafilatura fallback for remaining URLs
            if still_needed and TRAFILATURA_AVAILABLE:
                fallback_results = await asyncio.gather(
                    *[_fetch_full_page_async(u, max_chars) for u in still_needed],
                    return_exceptions=True,
                )
                for res in fallback_results:
                    if isinstance(res, tuple) and len(res) == 2 and res[1]:
                        extracted[res[0]] = res[1]
            for item in enriched:
                url = (item.get("url") or "").strip()
                if url in extracted:
                    full_text = extracted[url]
                    if cache and full_text:
                        cache_key = stable_cache_key(
                            "full_page_extract",
                            {"url": url, "extract_depth": extract_depth, "max_chars": max_chars},
                        )
                        try:
                            cache.set(cache_key, full_text, full_page_cache_ttl_seconds)
                            fp_stores += 1
                            _wmsg = (
                                f"[cache] wrote to SQLite | kind=full_page_extract "
                                f"chars={len(full_text)} url={_cache_url_preview(url)!r} db={cache_db_path}"
                            )
                            logger.info(_wmsg)
                            logging.getLogger().info(_wmsg)
                            print(_wmsg, file=sys.stderr, flush=True)
                            append_cache_write_log(_wmsg, db_path=cache_db_path)
                            if cache_log_verbose:
                                logger.info(
                                    "[cache] full_page STORE detail key_suffix=%s",
                                    cache_key[-16:],
                                )
                        except Exception as e:
                            logger.warning(
                                "[cache] full_page STORE failed path=%s: %s",
                                cache_db_path,
                                e,
                            )
                    if len(full_text) > len(item.get("snippet") or ""):
                        item["snippet"] = full_text
        if cache_enabled and cache_log and (fp_hits + fp_misses) > 0:
            logger.info(
                "[cache] full_page batch: candidates=%d hits=%d misses=%d stores=%d",
                fp_hits + fp_misses,
                fp_hits,
                fp_misses,
                fp_stores,
            )
            log_cache_event(
                "full_page_batch",
                {
                    "candidates": fp_hits + fp_misses,
                    "hits": fp_hits,
                    "misses": fp_misses,
                    "stores": fp_stores,
                },
            )
        chosen = enriched

    # Update trace
    trace = dict(state.get("research_trace") or {})
    trace["writer_evidence_count"] = len(chosen)
    log_node_end("prepare_writer_context", {"writer_evidence_count": len(chosen), "sections_covered": len(section_ids)})

    return {
        "writer_evidence_subset": chosen,
        "research_trace": trace,
    }
