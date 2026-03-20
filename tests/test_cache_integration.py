"""Tests for SQLite TTL cache integrations."""

import asyncio
import sqlite3

from deep_research.cache import stable_cache_key
from deep_research.nodes.search import run_search
from deep_research.nodes.writer_context import prepare_writer_context


def test_search_cache_hit_miss_and_expiry(tmp_path, monkeypatch):
    """run_search should hit cache on second call and refetch after expiry."""
    db_path = tmp_path / "research_cache.sqlite"
    calls = {"count": 0}

    async def fake_tavily(*args, **kwargs):
        calls["count"] += 1
        return [{"url": "https://example.com", "title": "Example", "content": "body"}]

    monkeypatch.setattr("deep_research.nodes.search._tavily_search_async", fake_tavily)
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")

    state = {"search_queries": ["cache me"], "seen_urls": set()}
    config = {
        "configurable": {
            "search_provider": "tavily",
            "results_per_query": 5,
            "search_depth": "advanced",
            "include_raw_content": True,
            "full_page_max_chars": 5000,
            "cache_enabled": True,
            "cache_db_path": str(db_path),
            "search_cache_ttl_seconds": 3600,
        }
    }

    first = asyncio.run(run_search(state, config=config))
    second = asyncio.run(run_search(state, config=config))
    assert calls["count"] == 1
    assert len(first["raw_search_results"]) == 1
    assert len(second["raw_search_results"]) == 1

    cache_key = stable_cache_key(
        "search",
        {
            "provider": "tavily",
            "query": "cache me",
            "max_results": 5,
            "search_depth": "advanced",
            "include_raw_content": True,
            "full_page_max_chars": 5000,
        },
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE cache_entries SET expires_at = 0 WHERE cache_key = ?", (cache_key,))
        conn.commit()

    third = asyncio.run(run_search(state, config=config))
    assert calls["count"] == 2
    assert len(third["raw_search_results"]) == 1


def test_writer_context_full_page_cache_reuse(tmp_path, monkeypatch):
    """prepare_writer_context should reuse cached extracted page text."""
    db_path = tmp_path / "research_cache.sqlite"
    calls = {"count": 0}
    long_text = "Very long extracted content " * 30

    async def fake_extract(urls, extract_depth="basic", max_chars=5000):
        calls["count"] += 1
        return {url: long_text[:max_chars] for url in urls}

    async def fail_extract(*args, **kwargs):
        raise AssertionError("Extraction should not run when cache is warm")

    monkeypatch.setattr("deep_research.nodes.writer_context._tavily_extract_async", fake_extract)

    state = {
        "evidence_items": [
            {
                "url": "https://example.com/article",
                "title": "Article",
                "snippet": "short",
                "section_ids": ["s1"],
                "relevance_score": 8,
            }
        ],
        "report_outline": [{"id": "s1", "title": "One", "description": "desc"}],
        "research_trace": {},
    }
    config = {
        "configurable": {
            "fetch_full_pages": True,
            "extract_depth": "basic",
            "full_page_max_chars": 5000,
            "cache_enabled": True,
            "cache_db_path": str(db_path),
            "full_page_cache_ttl_seconds": 3600,
        }
    }

    first = asyncio.run(prepare_writer_context(state, config=config))
    assert calls["count"] == 1
    first_snippet = first["writer_evidence_subset"][0]["snippet"]
    assert len(first_snippet) > len("short")

    monkeypatch.setattr("deep_research.nodes.writer_context._tavily_extract_async", fail_extract)
    second = asyncio.run(prepare_writer_context(state, config=config))
    second_snippet = second["writer_evidence_subset"][0]["snippet"]
    assert second_snippet == first_snippet
