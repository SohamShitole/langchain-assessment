"""Configuration for the research graph."""

import os
from pathlib import Path
from typing import Any

from langchain_core.runnables import RunnableConfig

DEFAULT_MAX_ITERATIONS = 3
DEFAULT_QUERIES_PER_ITERATION = 5
DEFAULT_RESULTS_PER_QUERY = 5
DEFAULT_WRITER_CONTEXT_MAX_ITEMS = 30
DEFAULT_SEARCH_PROVIDER = "gensee"  # "gensee" | "tavily"
DEFAULT_SEARCH_DEPTH = "advanced"  # "basic" (1 credit) or "advanced" (2 credits)
DEFAULT_INCLUDE_RAW_CONTENT = True
DEFAULT_FETCH_FULL_PAGES = True  # Fetch full page content for better reports
DEFAULT_FULL_PAGE_MAX_CHARS = 5000  # Max chars per page to keep context manageable
DEFAULT_EXTRACT_DEPTH = "basic"  # "basic" or "advanced" (for tables/structured data)

# Phase 2: section workers and conflict resolution
DEFAULT_SECTION_MAX_ITERATIONS = 3
DEFAULT_SECTION_QUERIES_PER_ITERATION = 3
DEFAULT_MAX_PARALLEL_SECTIONS = 6
DEFAULT_CONFLICT_RESOLUTION_ENABLED = True

# Model allocation per plan: start cheap, escalate for complex queries
DEFAULT_CLASSIFIER_MODEL = "gpt-4o-mini"  # gpt-5-nano when available
DEFAULT_PLANNER_SIMPLE_MODEL = "gpt-4o-mini"  # gpt-5-mini
DEFAULT_PLANNER_COMPLEX_MODEL = "gpt-4o"  # gpt-5.4
DEFAULT_NORMALIZER_MODEL = "gpt-4o-mini"
DEFAULT_COVERAGE_MODEL = "gpt-4o-mini"
DEFAULT_WRITER_MODEL = "gpt-4o"  # gpt-5.4 - strongest for final synthesis
DEFAULT_DECOMPOSE_MODEL = "gpt-4o"
DEFAULT_SECTION_QUERY_MODEL = "gpt-4o-mini"
DEFAULT_SECTION_SUMMARY_MODEL = "gpt-4o-mini"
DEFAULT_SECTION_COVERAGE_MODEL = "gpt-4o-mini"
DEFAULT_CONFLICT_DETECT_MODEL = "gpt-4o-mini"
DEFAULT_CONFLICT_RESOLVER_MODEL = "gpt-4o-mini"

# Mapping from config.yaml nested keys to flat get_config keys
_YAML_TO_FLAT = {
    "search": {
        "provider": "search_provider",
        "max_iterations": "max_iterations",
        "queries_per_iteration": "queries_per_iteration",
        "results_per_query": "results_per_query",
        "search_depth": "search_depth",
        "include_raw_content": "include_raw_content",
    },
    "extract": {
        "fetch_full_pages": "fetch_full_pages",
        "extract_depth": "extract_depth",
        "full_page_max_chars": "full_page_max_chars",
    },
    "models": {
        "classifier": "classifier_model",
        "planner_simple": "planner_simple_model",
        "planner_complex": "planner_complex_model",
        "normalizer": "normalizer_model",
        "coverage": "coverage_model",
        "writer": "writer_model",
        "decompose": "decompose_model",
        "section_query": "section_query_model",
        "section_summary": "section_summary_model",
        "section_coverage": "section_coverage_model",
        "conflict_detect": "conflict_detect_model",
        "conflict_resolver": "conflict_resolver_model",
    },
    "writer": {
        "context_max_items": "writer_context_max_items",
    },
    "section": {
        "max_iterations": "section_max_iterations",
        "queries_per_iteration": "section_queries_per_iteration",
    },
    "conflict": {
        "resolution_enabled": "conflict_resolution_enabled",
    },
}


def load_config_file(path: str | Path | None = None) -> dict[str, Any]:
    """Load configuration from a YAML file. Returns empty dict if file missing or invalid."""
    if path is None:
        path = Path.cwd() / "config.yaml"
    path = Path(path)
    if not path.is_file():
        return {}
    try:
        import yaml

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    flat: dict[str, Any] = {}
    for section, mappings in _YAML_TO_FLAT.items():
        section_data = data.get(section)
        if not isinstance(section_data, dict):
            continue
        for yaml_key, flat_key in mappings.items():
            if yaml_key in section_data:
                flat[flat_key] = section_data[yaml_key]
    return flat


def get_config(config: RunnableConfig | dict[str, Any] | None) -> dict[str, Any]:
    """Extract configuration from RunnableConfig, using defaults for missing values.
    Merge order: hardcoded defaults < config.yaml < configurable overrides."""
    config = config or {}
    cfg = config.get("configurable") or {}
    return {
        "max_iterations": cfg.get("max_iterations", DEFAULT_MAX_ITERATIONS),
        "queries_per_iteration": cfg.get(
            "queries_per_iteration", DEFAULT_QUERIES_PER_ITERATION
        ),
        "results_per_query": cfg.get(
            "results_per_query", DEFAULT_RESULTS_PER_QUERY
        ),
        "writer_context_max_items": cfg.get(
            "writer_context_max_items", DEFAULT_WRITER_CONTEXT_MAX_ITEMS
        ),
        "research_model": cfg.get("research_model"),
        "writer_model": cfg.get("writer_model", DEFAULT_WRITER_MODEL),
        "classifier_model": cfg.get("classifier_model", DEFAULT_CLASSIFIER_MODEL),
        "planner_simple_model": cfg.get(
            "planner_simple_model", DEFAULT_PLANNER_SIMPLE_MODEL
        ),
        "planner_complex_model": cfg.get(
            "planner_complex_model", DEFAULT_PLANNER_COMPLEX_MODEL
        ),
        "normalizer_model": cfg.get("normalizer_model", DEFAULT_NORMALIZER_MODEL),
        "coverage_model": cfg.get("coverage_model", DEFAULT_COVERAGE_MODEL),
        "fetch_full_pages": cfg.get("fetch_full_pages", DEFAULT_FETCH_FULL_PAGES),
        "full_page_max_chars": cfg.get(
            "full_page_max_chars", DEFAULT_FULL_PAGE_MAX_CHARS
        ),
        "search_provider": cfg.get("search_provider", DEFAULT_SEARCH_PROVIDER),
        "search_depth": cfg.get("search_depth", DEFAULT_SEARCH_DEPTH),
        "include_raw_content": cfg.get(
            "include_raw_content", DEFAULT_INCLUDE_RAW_CONTENT
        ),
        "extract_depth": cfg.get("extract_depth", DEFAULT_EXTRACT_DEPTH),
        "section_max_iterations": cfg.get(
            "section_max_iterations", DEFAULT_SECTION_MAX_ITERATIONS
        ),
        "section_queries_per_iteration": cfg.get(
            "section_queries_per_iteration", DEFAULT_SECTION_QUERIES_PER_ITERATION
        ),
        "max_parallel_sections": cfg.get(
            "max_parallel_sections", DEFAULT_MAX_PARALLEL_SECTIONS
        ),
        "conflict_resolution_enabled": cfg.get(
            "conflict_resolution_enabled", DEFAULT_CONFLICT_RESOLUTION_ENABLED
        ),
        "decompose_model": cfg.get("decompose_model", DEFAULT_DECOMPOSE_MODEL),
        "section_query_model": cfg.get(
            "section_query_model", DEFAULT_SECTION_QUERY_MODEL
        ),
        "section_summary_model": cfg.get(
            "section_summary_model", DEFAULT_SECTION_SUMMARY_MODEL
        ),
        "section_coverage_model": cfg.get(
            "section_coverage_model", DEFAULT_SECTION_COVERAGE_MODEL
        ),
        "conflict_detect_model": cfg.get(
            "conflict_detect_model", DEFAULT_CONFLICT_DETECT_MODEL
        ),
        "conflict_resolver_model": cfg.get(
            "conflict_resolver_model", DEFAULT_CONFLICT_RESOLVER_MODEL
        ),
    }
