"""Structured research process logging to file.

Logs node execution, prompts, decisions, and routing choices for observability.
Use --log or --log-file in run.py to enable.
"""

from datetime import datetime
import json
from typing import Any

# Max chars to log for prompts/ outputs (truncate to avoid huge files)
_MAX_PROMPT_CHARS = 4000
_MAX_OUTPUT_CHARS = 2000

_log_path: str | None = None
_log_handle = None


def init_log(log_path: str) -> None:
    """Initialize file logging. Call from run.py before graph invocation."""
    global _log_path, _log_handle
    _log_path = log_path
    _log_handle = open(log_path, "w", encoding="utf-8")
    _write("=" * 80)
    _write("RESEARCH PROCESS LOG")
    _write(f"Started: {datetime.now().isoformat()}")
    _write("=" * 80)


def close_log() -> None:
    """Close the log file. Call when run completes."""
    global _log_handle
    if _log_handle:
        _log_handle.close()
        _log_handle = None


def _write(line: str) -> None:
    if _log_handle:
        _log_handle.write(line + "\n")
        _log_handle.flush()


def _truncate(s: str, max_chars: int) -> str:
    if not s:
        return ""
    s = str(s)
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + f"\n... [truncated, total {len(s)} chars]"


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def is_enabled() -> bool:
    """Whether logging is active."""
    return _log_handle is not None


def log_node_start(node_name: str, config: Any = None, section_id: str | None = None) -> None:
    """Log that a node has started."""
    if not is_enabled():
        return
    ctx = f" (section={section_id})" if section_id else ""
    _write(f"\n[{_ts()}] >>> NODE START: {node_name}{ctx}")


def log_node_end(node_name: str, output_summary: dict | None = None) -> None:
    """Log that a node has finished, with optional output summary."""
    if not is_enabled():
        return
    if output_summary:
        s = json.dumps(output_summary, default=str)[:_MAX_OUTPUT_CHARS]
        if len(str(output_summary)) > _MAX_OUTPUT_CHARS:
            s += "... [truncated]"
        _write(f"    output: {s}")
    _write(f"[{_ts()}] <<< NODE END: {node_name}\n")


def log_prompt(
    node_name: str,
    prompt: str,
    model: str | None = None,
    system_content: str | None = None,
) -> None:
    """Log a prompt sent to an LLM."""
    if not is_enabled():
        return
    _write(f"  [PROMPT] model={model or 'N/A'}")
    if system_content:
        _write(f"  system: {_truncate(system_content, 800)}")
    _write(f"  user: {_truncate(prompt, _MAX_PROMPT_CHARS)}")


def log_decision(node_name: str, decision: str, details: dict | None = None) -> None:
    """Log a decision made by a node (e.g. complexity, coverage, route)."""
    if not is_enabled():
        return
    _write(f"  [DECISION] {decision}")
    if details:
        s = json.dumps(details, default=str, indent=2)[:_MAX_OUTPUT_CHARS]
        if len(json.dumps(details, default=str)) > _MAX_OUTPUT_CHARS:
            s += "\n... [truncated]"
        _write(f"  details: {s}")


def log_route(from_node: str, route: str, reason: str | None = None) -> None:
    """Log a routing decision."""
    if not is_enabled():
        return
    _write(f"\n[{_ts()}] ROUTE: {from_node} -> {route}")
    if reason:
        _write(f"  reason: {reason}\n")


def log_section_header(title: str) -> None:
    """Log a section header (e.g. 'Main graph' vs 'Section worker s1')."""
    if not is_enabled():
        return
    _write(f"\n{'#' * 60}")
    _write(f"# {title}")
    _write(f"{'#' * 60}\n")
