"""Configuration for the research graph."""

import logging
import os
from pathlib import Path
from typing import Any

from langchain_core.runnables import RunnableConfig

from deep_research.cache import resolve_cache_db_path

logger = logging.getLogger(__name__)

# Path to the bundled report presets file (next to config.yaml in the project root)
_PRESETS_FILE = Path(__file__).parent.parent / "report_presets.yaml"

DEFAULT_MAX_ITERATIONS = 3
DEFAULT_QUERIES_PER_ITERATION = 5
DEFAULT_RESULTS_PER_QUERY = 5
DEFAULT_WRITER_CONTEXT_MAX_ITEMS = 30
DEFAULT_SEARCH_PROVIDER = "gensee"  # "gensee" | "gensee_deep" | "tavily" | "exa"
DEFAULT_SEARCH_DEPTH = "basic"  # "basic" (1 credit) or "advanced" (2 credits)
DEFAULT_INCLUDE_RAW_CONTENT = True
DEFAULT_FETCH_FULL_PAGES = True  # Fetch full page content for better reports
DEFAULT_FULL_PAGE_MAX_CHARS = 5000  # Max chars per page to keep context manageable
DEFAULT_EXTRACT_DEPTH = "basic"  # "basic" or "advanced" (for tables/structured data)
DEFAULT_CACHE_ENABLED = True
DEFAULT_CACHE_DB_PATH = ".cache/research_cache.sqlite"
DEFAULT_SEARCH_CACHE_TTL_SECONDS = 21600
DEFAULT_FULL_PAGE_CACHE_TTL_SECONDS = 43200
DEFAULT_CACHE_LOG = True
DEFAULT_CACHE_LOG_VERBOSE = False

# Phase 2: section workers and conflict resolution
DEFAULT_SECTION_MAX_ITERATIONS = 3
DEFAULT_SECTION_QUERIES_PER_ITERATION = 3
DEFAULT_MAX_PARALLEL_SECTIONS = 15
DEFAULT_CONFLICT_RESOLUTION_ENABLED = True
# Section summary: how much evidence the summary node sees (improves summary quality)
DEFAULT_SECTION_SUMMARY_TOP_N = 25
DEFAULT_SECTION_SUMMARY_SNIPPET_CHARS = 1200
DEFAULT_SECTION_SUMMARY_EVIDENCE_MAX_CHARS = 0  # 0 = use top_n + snippet_chars; >0 = fill until this budget

# Model allocation per plan: start cheap, escalate for complex queries
DEFAULT_CLASSIFIER_MODEL = "gpt-5-nano"  # gpt-5-nano when available
DEFAULT_PLANNER_SIMPLE_MODEL = "gpt-5-mini"  # gpt-5-mini
DEFAULT_PLANNER_COMPLEX_MODEL = "gpt-5.2"  # gpt-5.4
DEFAULT_NORMALIZER_MODEL = "gpt-5-nano"
DEFAULT_COVERAGE_MODEL = "gpt-5-nano"
DEFAULT_WRITER_MODEL = "gpt-5.2"  # gpt-5.4 - strongest for final synthesis
DEFAULT_DECOMPOSE_MODEL = "gpt-5.2"
DEFAULT_SECTION_QUERY_MODEL = "gpt-5-mini"
DEFAULT_SECTION_SUMMARY_MODEL = "gpt-5-mini"
DEFAULT_SECTION_COVERAGE_MODEL = "gpt-5-nano"
DEFAULT_CONFLICT_DETECT_MODEL = "gpt-5-mini"
DEFAULT_CONFLICT_RESOLVER_MODEL = "gpt-5-mini"

# Default ordered sections for the final report (configurable via report.structure in config.yaml)
DEFAULT_REPORT_STRUCTURE = [
    "Title",
    "Executive Summary",
    "Main Findings",
    "Detailed Analysis by Section",
    "Conclusion",
    "Sources",
]

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
    "cache": {
        "enabled": "cache_enabled",
        "db_path": "cache_db_path",
        "search_ttl_seconds": "search_cache_ttl_seconds",
        "full_page_ttl_seconds": "full_page_cache_ttl_seconds",
        "log": "cache_log",
        "log_verbose": "cache_log_verbose",
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
        "max_parallel": "max_parallel_sections",
        "summary_top_n": "section_summary_top_n",
        "summary_snippet_chars": "section_summary_snippet_chars",
        "summary_evidence_max_chars": "section_summary_evidence_max_chars",
    },
    "conflict": {
        "resolution_enabled": "conflict_resolution_enabled",
    },
}


def load_report_presets(path: str | Path | None = None) -> dict[int, list[str]]:
    """Load report structure presets from a YAML file.

    Returns a mapping of preset number -> list of section names.
    Falls back to an empty dict if the file is missing or malformed.
    """
    if path is None:
        path = _PRESETS_FILE
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
    raw_presets = data.get("presets")
    if not isinstance(raw_presets, dict):
        return {}
    result: dict[int, list[str]] = {}
    for key, value in raw_presets.items():
        try:
            preset_num = int(key)
        except (TypeError, ValueError):
            continue
        if not isinstance(value, dict):
            continue
        structure = value.get("structure")
        if isinstance(structure, list) and all(isinstance(s, str) for s in structure):
            result[preset_num] = structure
    return result


def _config_dir_anchor(path_resolved: Path) -> str:
    """Directory used to resolve relative cache paths (same folder as config.yaml)."""
    return str(path_resolved.resolve().parent)


_RESEARCH_MODE_OVERLAYS = frozenset({"basic", "advanced"})


def _merge_yaml_root(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Merge top-level YAML mappings: for nested dict sections, overlay keys win (shallow per section)."""
    out = dict(base)
    for key, val in overlay.items():
        if key in out and isinstance(out[key], dict) and isinstance(val, dict):
            merged_section = dict(out[key])
            merged_section.update(val)
            out[key] = merged_section
        else:
            out[key] = val
    return out


def load_config_file(
    path: str | Path | None = None,
    *,
    research_mode: str | None = None,
) -> dict[str, Any]:
    """Load configuration from a YAML file. Returns empty dict if file missing or invalid.

    Injects ``_cache_path_anchor`` (parent dir of config file, or cwd) so relative
    ``cache.db_path`` resolves next to your project, not the installed package.

    If ``research_mode`` is ``\"basic\"`` or ``\"advanced\"``, merges
    ``config_research_{mode}.yaml`` from the same directory as the base config file
    (so shared settings stay in ``config.yaml`` and mode files only override research
    depth / cost knobs).
    """
    if path is None:
        path = Path.cwd() / "config.yaml"
    path = Path(path)
    cwd_anchor = str(Path.cwd().resolve())

    data: dict[str, Any] = {}
    if path.is_file():
        try:
            import yaml

            with open(path, encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                data = loaded
            else:
                logger.warning(
                    "[config] invalid YAML root in %s; expected mapping",
                    path,
                )
        except Exception as e:
            logger.warning("[config] failed to read %s: %s", path, e)
    else:
        logger.info("[config] file not found: %s (using defaults / overlay only)", path)

    if research_mode is not None:
        mode = str(research_mode).strip().lower()
        if mode not in _RESEARCH_MODE_OVERLAYS:
            logger.warning(
                "[config] unknown research_mode %r (expected basic|advanced); skipping overlay",
                research_mode,
            )
        else:
            overlay_path = path.parent / f"config_research_{mode}.yaml"
            if overlay_path.is_file():
                try:
                    import yaml

                    with open(overlay_path, encoding="utf-8") as f:
                        overlay_raw = yaml.safe_load(f)
                    if isinstance(overlay_raw, dict):
                        data = _merge_yaml_root(data, overlay_raw)
                        logger.info(
                            "[config] merged research preset %r from %s",
                            mode,
                            overlay_path,
                        )
                    else:
                        logger.warning(
                            "[config] invalid YAML root in overlay %s",
                            overlay_path,
                        )
                except Exception as e:
                    logger.warning(
                        "[config] failed to load overlay %s: %s",
                        overlay_path,
                        e,
                    )
            else:
                logger.warning(
                    "[config] research overlay not found: %s (preset %r skipped)",
                    overlay_path,
                    mode,
                )

    flat: dict[str, Any] = {}
    for section, mappings in _YAML_TO_FLAT.items():
        section_data = data.get(section)
        if not isinstance(section_data, dict):
            continue
        for yaml_key, flat_key in mappings.items():
            if yaml_key in section_data:
                flat[flat_key] = section_data[yaml_key]

    # Prompt overrides: only include non-null string values
    prompts_data = data.get("prompts")
    if isinstance(prompts_data, dict):
        flat["prompt_overrides"] = {
            k: v for k, v in prompts_data.items() if v is not None and isinstance(v, str)
        }

    # Report structure: explicit list takes priority; preset number is the fallback.
    report_data = data.get("report")
    if isinstance(report_data, dict):
        structure = report_data.get("structure")
        if isinstance(structure, list) and all(isinstance(x, str) for x in structure):
            # Explicit structure list wins unconditionally.
            flat["report_structure"] = structure
        else:
            # Try to resolve a preset number when no explicit structure is given.
            preset_num = report_data.get("preset")
            if preset_num is not None:
                try:
                    preset_num = int(preset_num)
                except (TypeError, ValueError):
                    preset_num = None
            if preset_num is not None:
                presets = load_report_presets()
                if preset_num in presets:
                    flat["report_structure"] = presets[preset_num]
                else:
                    available = sorted(presets.keys())
                    raise ValueError(
                        f"report.preset {preset_num!r} not found in report_presets.yaml. "
                        f"Available presets: {available}"
                    )

    flat["_cache_path_anchor"] = (
        _config_dir_anchor(path) if path.is_file() else cwd_anchor
    )

    logger.info(
        "[config] loaded base=%s research_mode=%s mapped_keys=%d: %s",
        path,
        research_mode or "(none)",
        len(flat),
        ", ".join(sorted(k for k in flat.keys() if not k.startswith("_"))) if flat else "(none)",
    )
    return flat


def get_config(config: RunnableConfig | dict[str, Any] | None) -> dict[str, Any]:
    """Extract configuration from RunnableConfig, using defaults for missing values.
    Merge order: hardcoded defaults < config.yaml < configurable overrides.
    If config is a dict with a 'configurable' key (RunnableConfig), use that; else treat config as the configurable dict."""
    config = config or {}
    cfg = (
        config.get("configurable")
        if isinstance(config, dict) and "configurable" in config
        else config
    ) or {}
    cache_anchor = cfg.get("_cache_path_anchor") or str(Path.cwd().resolve())
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
        "cache_enabled": cfg.get("cache_enabled", DEFAULT_CACHE_ENABLED),
        "cache_db_path": resolve_cache_db_path(
            str(cfg.get("cache_db_path", DEFAULT_CACHE_DB_PATH)),
            anchor=cache_anchor,
        ),
        "search_cache_ttl_seconds": cfg.get(
            "search_cache_ttl_seconds",
            DEFAULT_SEARCH_CACHE_TTL_SECONDS,
        ),
        "full_page_cache_ttl_seconds": cfg.get(
            "full_page_cache_ttl_seconds",
            DEFAULT_FULL_PAGE_CACHE_TTL_SECONDS,
        ),
        "cache_log": cfg.get("cache_log", DEFAULT_CACHE_LOG),
        "cache_log_verbose": cfg.get(
            "cache_log_verbose",
            DEFAULT_CACHE_LOG_VERBOSE,
        ),
        "section_max_iterations": cfg.get(
            "section_max_iterations", DEFAULT_SECTION_MAX_ITERATIONS
        ),
        "section_queries_per_iteration": cfg.get(
            "section_queries_per_iteration", DEFAULT_SECTION_QUERIES_PER_ITERATION
        ),
        "max_parallel_sections": cfg.get(
            "max_parallel_sections", DEFAULT_MAX_PARALLEL_SECTIONS
        ),
        "section_summary_top_n": cfg.get(
            "section_summary_top_n", DEFAULT_SECTION_SUMMARY_TOP_N
        ),
        "section_summary_snippet_chars": cfg.get(
            "section_summary_snippet_chars", DEFAULT_SECTION_SUMMARY_SNIPPET_CHARS
        ),
        "section_summary_evidence_max_chars": cfg.get(
            "section_summary_evidence_max_chars",
            DEFAULT_SECTION_SUMMARY_EVIDENCE_MAX_CHARS,
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
        "prompt_overrides": cfg.get("prompt_overrides", {}),
        "report_structure": cfg.get("report_structure", DEFAULT_REPORT_STRUCTURE),
    }
