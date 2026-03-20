#!/usr/bin/env python3
"""Gradio UI for the deep research agent.

Run with: python gradio_app.py
Then open the URL shown (default http://127.0.0.1:7860).

Supports plan approval: after the research plan is created, the graph pauses.
You can Proceed, Edit (with feedback), or Cancel—same as the CLI.
"""

import asyncio
import json
import logging
import os
import re
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import HumanMessage

from deep_research.configuration import get_config, load_config_file
from deep_research.graph import create_research_graph

logger = logging.getLogger(__name__)

try:
    from langgraph.checkpoint.memory import MemorySaver
except ImportError:
    MemorySaver = None

try:
    from langgraph.types import Command
except ImportError:
    Command = None

# Progress messages (mirrors deep_research/progress.py NODE_MESSAGES)
_NODE_MESSAGES: dict[str, str] = {
    "ingest_request": "Reading your query...",
    "classify_complexity": "Figuring out how complex this topic is...",
    "create_research_plan": "Drafting a research plan...",
    "decompose_into_sections": "Breaking the plan into independent research sections...",
    "section_worker": "Finished researching: {section_title}",
    "merge_section_evidence": "Merging evidence from all sections...",
    "detect_global_gaps_and_conflicts": "Checking for gaps and contradictions across sections...",
    "conflict_resolution_research": "Running additional searches to resolve contradictions...",
    "prepare_writer_context": "Selecting the best evidence for the report...",
    "write_sections": "Writing section drafts...",
    "write_report": "Assembling the final report...",
    "finalize_messages": "Done!",
}

# Shared graph with interrupt for plan approval (one per process)
_graph_with_interrupt = None


def _get_graph():
    """Return the shared research graph with plan-interrupt enabled."""
    global _graph_with_interrupt
    if _graph_with_interrupt is None and MemorySaver is not None:
        _graph_with_interrupt = create_research_graph(
            checkpointer=MemorySaver(),
            interrupt_after=["create_research_plan"],
        )
    return _graph_with_interrupt


def _progress_line(node_name: str, data: dict[str, Any] | None) -> list[str]:
    """Return one or more progress lines for this node update."""
    data = data or {}
    msg = _NODE_MESSAGES.get(node_name)
    if not msg:
        return []
    if node_name == "section_worker":
        results = data.get("section_results") or []
        lines = []
        for one in results:
            if isinstance(one, dict):
                title = one.get("section_title") or one.get("section_id") or "a section"
                lines.append(msg.format(section_title=title))
        if not lines:
            lines.append("Researching sections in parallel...")
        return lines
    if "{section_title}" in msg:
        msg = msg.format(section_title="a section")
    return [msg]


def _section_count_line(n: int) -> str | None:
    if n > 0:
        return f"Researching {n} sections in parallel..."
    return None


def _json_safe(obj: Any) -> Any:
    """Strip non-JSON-serializable values (e.g. Pydantic, datetime) via round-trip."""
    return json.loads(json.dumps(obj, default=str))


def _format_error(e: BaseException) -> str:
    """Format an exception for UI display so 'Error: 1' becomes descriptive."""
    name = type(e).__name__
    msg = str(e).strip()
    if not msg or msg.isdigit() or (len(msg) <= 2 and msg in ("0", "1", "-1")):
        return f"Error: {name} (no message). Check the terminal where you ran gradio_app.py for the full traceback."
    return f"Error: {name} — {msg}"


def _log_exception(e: BaseException, context: str) -> None:
    """Log full traceback to stderr so the user can see it in the terminal."""
    print(f"\n[{context}] Exception: {type(e).__name__}: {e}", flush=True)
    traceback.print_exc()


# Step order for progress bar (1..12). Maps display message to step index.
_STEP_ORDER: dict[str, int] = {
    "Reading your query...": 1,
    "Figuring out how complex this topic is...": 2,
    "Drafting a research plan...": 3,
    "Breaking the plan into independent research sections...": 4,
    "Researching sections in parallel...": 5,
    "Merging evidence from all sections...": 6,
    "Checking for gaps and contradictions across sections...": 7,
    "Running additional searches to resolve contradictions...": 8,
    "Selecting the best evidence for the report...": 9,
    "Writing section drafts...": 10,
    "Assembling the final report...": 11,
    "Done!": 12,
}
_TOTAL_STEPS = 12

# Full Phase-2 pipeline node list (matches deep_research/graph.py order)
_GRAPH_NODES: list[tuple[str, str, bool]] = [
    ("ingest_request", "Ingest Request", False),
    ("classify_complexity", "Classify Complexity", False),
    ("create_research_plan", "Create Research Plan", False),
    ("human_plan_feedback", "Human Plan Feedback", False),
    ("decompose_into_sections", "Decompose into Sections", False),
    ("section_worker", "Section Workers", False),
    ("merge_section_evidence", "Merge Evidence", False),
    ("detect_global_gaps_and_conflicts", "Detect Conflicts and Gaps", False),
    ("conflict_resolution_research", "Resolve Conflicts", True),
    ("eval_stop_gate", "Eval Stop Gate", False),
    ("prepare_writer_context", "Prepare Writer Context", False),
    ("write_sections", "Write Sections", False),
    ("write_report", "Write Report", False),
    ("finalize_messages", "Finalize", False),
]
_GRAPH_NODE_IDS = {node_id for node_id, _label, _is_conditional in _GRAPH_NODES}


def _make_graph_html(active_node: str | None, completed_nodes: set[str] | None) -> str:
    """Return a script-free SVG graph so it always renders in Gradio HTML."""
    completed_nodes = completed_nodes or set()
    state_by_node: dict[str, str] = {}
    for node_id, _label, _is_conditional in _GRAPH_NODES:
        if node_id == active_node:
            state_by_node[node_id] = "active"
        elif node_id in completed_nodes:
            state_by_node[node_id] = "done"
        else:
            state_by_node[node_id] = "pending"

    # Horizontal layout positions
    node_w = 180
    node_h = 44
    x0 = 40
    step = 210
    y_top = 64
    y_bottom = 210
    main_order = [
        "ingest_request",
        "classify_complexity",
        "create_research_plan",
        "decompose_into_sections",
        "section_worker",
        "merge_section_evidence",
        "detect_global_gaps_and_conflicts",
        "eval_stop_gate",
        "prepare_writer_context",
        "write_sections",
        "write_report",
        "finalize_messages",
    ]
    positions: dict[str, tuple[int, int]] = {}
    for i, node_id in enumerate(main_order):
        positions[node_id] = (x0 + i * step, y_top)
    positions["human_plan_feedback"] = (
        (positions["create_research_plan"][0] + positions["decompose_into_sections"][0]) // 2,
        y_bottom,
    )
    positions["conflict_resolution_research"] = (
        (positions["detect_global_gaps_and_conflicts"][0] + positions["eval_stop_gate"][0]) // 2,
        y_bottom,
    )

    labels = {node_id: label for node_id, label, _ in _GRAPH_NODES}

    def node_colors(node_id: str) -> tuple[str, str, str]:
        state = state_by_node.get(node_id, "pending")
        if state == "active":
            return "#2563eb", "#93c5fd", "#ffffff"
        if state == "done":
            return "#16a34a", "#86efac", "#ffffff"
        return "#1e293b", "#64748b", "#f8fafc"

    def mid_right(node_id: str) -> tuple[int, int]:
        x, y = positions[node_id]
        return x + node_w, y + node_h // 2

    def mid_left(node_id: str) -> tuple[int, int]:
        x, y = positions[node_id]
        return x, y + node_h // 2

    # Build main sequential edges (skip create_research_plan -> decompose; routed via human feedback)
    edges_svg: list[str] = []
    for a, b in zip(main_order[:-1], main_order[1:]):
        if a == "create_research_plan" and b == "decompose_into_sections":
            continue
        x1, y1 = mid_right(a)
        x2, y2 = mid_left(b)
        edges_svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#64748b" stroke-width="2" marker-end="url(#gv-arrow)" />')

    # Human approval branch
    # create_research_plan -> human_plan_feedback
    x1, y1 = positions["create_research_plan"][0] + node_w // 2, positions["create_research_plan"][1] + node_h
    x2, y2 = positions["human_plan_feedback"][0] + node_w // 2, positions["human_plan_feedback"][1]
    edges_svg.append(
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#64748b" stroke-width="2" marker-end="url(#gv-arrow)" />'
    )
    edges_svg.append(
        f'<text x="{x1 + 12}" y="{(y1 + y2)//2}" fill="#cbd5e1" font-size="11">review</text>'
    )

    # human_plan_feedback -> decompose_into_sections (no edit/proceed)
    x1, y1 = mid_right("human_plan_feedback")
    x2, y2 = mid_left("decompose_into_sections")
    edges_svg.append(
        f'<path d="M {x1} {y1} C {x1+40} {y1}, {x2-40} {y2}, {x2} {y2}" '
        'fill="none" stroke="#22c55e" stroke-width="2" marker-end="url(#gv-arrow-green)" />'
    )
    edges_svg.append(
        f'<text x="{(x1 + x2)//2}" y="{((y1 + y2)//2)-8}" fill="#86efac" font-size="11" text-anchor="middle">no edit / proceed</text>'
    )

    # human_plan_feedback -> create_research_plan (edit loop)
    x1, y1 = mid_left("human_plan_feedback")
    x2, y2 = positions["create_research_plan"][0] + node_w // 2, positions["create_research_plan"][1] + node_h
    edges_svg.append(
        f'<path d="M {x1} {y1} C {x1-70} {y1}, {x2-80} {y2+40}, {x2} {y2}" '
        'fill="none" stroke="#ef4444" stroke-width="2" stroke-dasharray="6 4" marker-end="url(#gv-arrow-red)" />'
    )
    edges_svg.append(
        f'<text x="{x1-44}" y="{y1-8}" fill="#fca5a5" font-size="11" text-anchor="middle">edit</text>'
    )

    # Branch edge (dashed amber): detect_global_gaps_and_conflicts -> conflict_resolution_research
    x1, y1 = mid_right("detect_global_gaps_and_conflicts")
    x2, y2 = mid_left("conflict_resolution_research")
    edges_svg.append(
        f'<path d="M {x1} {y1} C {x1+40} {y1}, {x2-40} {y2}, {x2} {y2}" '
        'fill="none" stroke="#f59e0b" stroke-width="2" stroke-dasharray="6 4" marker-end="url(#gv-arrow-amber)" />'
    )
    edges_svg.append(
        f'<text x="{(x1 + x2)//2}" y="{((y1 + y2)//2)-8}" fill="#fbbf24" font-size="11" text-anchor="middle">conflicts</text>'
    )

    # Up edge: conflict_resolution_research -> eval_stop_gate
    x1, y1 = mid_right("conflict_resolution_research")
    x2, y2 = mid_left("eval_stop_gate")
    edges_svg.append(
        f'<path d="M {x1} {y1} C {x1+40} {y1}, {x2-40} {y2}, {x2} {y2}" '
        'fill="none" stroke="#64748b" stroke-width="2" marker-end="url(#gv-arrow)" />'
    )

    # Retry edge (dashed red): eval_stop_gate -> conflict_resolution_research
    x1, y1 = positions["eval_stop_gate"][0] + node_w // 2, positions["eval_stop_gate"][1] + node_h
    x2, y2 = positions["conflict_resolution_research"][0] + node_w // 2, positions["conflict_resolution_research"][1]
    edges_svg.append(
        f'<path d="M {x1} {y1} C {x1+60} {y1+40}, {x2+60} {y2-40}, {x2} {y2}" '
        'fill="none" stroke="#ef4444" stroke-width="2" stroke-dasharray="6 4" marker-end="url(#gv-arrow-red)" />'
    )
    edges_svg.append(
        f'<text x="{max(x1, x2)+42}" y="{(y1 + y2)//2}" fill="#fca5a5" font-size="11" text-anchor="middle">retry</text>'
    )

    nodes_svg: list[str] = []
    for node_id, label, is_conditional in _GRAPH_NODES:
        x, y = positions[node_id]
        fill, stroke, text = node_colors(node_id)
        dash = ' stroke-dasharray="6 4"' if is_conditional else ""
        extra = " (parallel)" if node_id == "section_worker" else ""
        pulse = ' class="gv-active-node"' if state_by_node.get(node_id) == "active" else ""
        nodes_svg.append(
            f'<g{pulse}>'
            f'<rect x="{x}" y="{y}" width="{node_w}" height="{node_h}" rx="10" ry="10" fill="{fill}" stroke="{stroke}" stroke-width="2"{dash} />'
            f'<text x="{x + node_w//2}" y="{y + 27}" fill="{text}" font-size="11" text-anchor="middle">{_escape_html(label + extra)}</text>'
            f"</g>"
        )

    width = x0 + len(main_order) * step + 120
    height = 320
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        + "<defs>"
        + '<marker id="gv-arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#94a3b8"/></marker>'
        + '<marker id="gv-arrow-green" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#22c55e"/></marker>'
        + '<marker id="gv-arrow-amber" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#f59e0b"/></marker>'
        + '<marker id="gv-arrow-red" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#ef4444"/></marker>'
        + "</defs>"
        + "".join(edges_svg)
        + "".join(nodes_svg)
        + "</svg>"
    )

    # CSS-only zoom controls (no script needed)
    graph_id = f"gv-static-{uuid.uuid4().hex[:8]}"
    template = """
<style>
#GRAPH_ID {
  border: 1px solid #334155;
  border-radius: 10px;
  background: #0f172a;
  padding: 10px;
  margin: 8px 0 12px;
}
#GRAPH_ID .gv-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
#GRAPH_ID .gv-title {
  margin: 0;
  color: #e2e8f0;
  font-size: 0.95rem;
  font-weight: 600;
}
#GRAPH_ID .gv-controls {
  display: flex;
  gap: 6px;
}
#GRAPH_ID .gv-controls label {
  border: 1px solid #475569;
  background: #1e293b;
  color: #e2e8f0;
  border-radius: 6px;
  padding: 3px 8px;
  font-size: 0.75rem;
  cursor: pointer;
}
#GRAPH_ID .gv-scroller {
  overflow: auto;
  border: 1px solid #334155;
  border-radius: 8px;
  background: #0b1220;
  height: 360px;
}
#GRAPH_ID .gv-scale {
  transform-origin: 0 0;
  width: max-content;
  transition: transform 0.15s ease;
}
#GRAPH_ID .gv-active-node {
  animation: gvPulse 1.2s ease-in-out infinite;
}
@keyframes gvPulse {
  0% { opacity: 1; }
  50% { opacity: 0.82; }
  100% { opacity: 1; }
}
#GRAPH_ID input[type="radio"] { display: none; }
#GRAPH_ID #z80:checked ~ .gv-scroller .gv-scale { transform: scale(0.8); }
#GRAPH_ID #z100:checked ~ .gv-scroller .gv-scale { transform: scale(1); }
#GRAPH_ID #z125:checked ~ .gv-scroller .gv-scale { transform: scale(1.25); }
#GRAPH_ID #z150:checked ~ .gv-scroller .gv-scale { transform: scale(1.5); }
</style>
<div id="GRAPH_ID">
  <input type="radio" id="z80" name="GRAPH_ID-zoom">
  <input type="radio" id="z100" name="GRAPH_ID-zoom" checked>
  <input type="radio" id="z125" name="GRAPH_ID-zoom">
  <input type="radio" id="z150" name="GRAPH_ID-zoom">
  <div class="gv-head">
    <p class="gv-title">Pipeline Graph</p>
    <div class="gv-controls">
      <label for="z80">80%</label>
      <label for="z100">100%</label>
      <label for="z125">125%</label>
      <label for="z150">150%</label>
    </div>
  </div>
  <div class="gv-scroller">
    <div class="gv-scale">
      SVG_CONTENT
    </div>
  </div>
</div>
"""
    return template.replace("GRAPH_ID", graph_id).replace("SVG_CONTENT", svg)


def _parse_progress(progress_log: str) -> tuple[str, float]:
    """From accumulated progress log, return (current_label, pct). Only the latest step; parallel work abstracted."""
    current_label = "Starting..."
    pct = 0.0
    lines = [ln.strip() for ln in (progress_log or "").split("\n") if ln.strip()]
    max_step = 0
    for line in lines:
        if line.startswith("Finished researching:"):
            label = "Researching sections in parallel..."
            step = _STEP_ORDER.get(label, 5)
        elif line.startswith("Researching ") and "sections in parallel" in line:
            label = "Researching sections in parallel..."
            step = _STEP_ORDER.get(label, 5)
        else:
            label = line
            step = _STEP_ORDER.get(line, 0)
        if step > max_step:
            max_step = step
            current_label = label
    if max_step > 0:
        pct = min(100.0, (max_step / _TOTAL_STEPS) * 100.0)
    return current_label, pct


def _make_progress_html(msg: str, pct: float) -> str:
    """Return HTML for progress bar + current step label."""
    done = pct >= 100.0
    fill_class = "pr-fill-done" if done else "pr-fill"
    return f"""<div class="pr-wrap">
  <div class="pr-track"><div class="{fill_class}" style="width:{pct:.0f}%"></div></div>
  <p class="pr-label">{msg}</p>
</div>"""


def _format_plan_md(plan: dict) -> str:
    """Format research plan as markdown for the UI."""
    sections = plan.get("desired_structure") or plan.get("section_names") or []
    if isinstance(sections, list) and sections and isinstance(sections[0], dict):
        section_list = [(s.get("id", ""), s.get("title", "Section")) for s in sections]
    elif isinstance(sections, list):
        section_list = [(str(i + 1), t) for i, t in enumerate(sections) if isinstance(t, str)]
    else:
        section_list = []

    lines = ["### Proposed Research Plan", ""]
    if plan.get("objective"):
        lines.append(f"**Objective:** {plan['objective']}")
        lines.append("")
    lines.append("**Sections:**")
    for i, (sid, title) in enumerate(section_list, 1):
        lines.append(f"{i}. {title}")
    return "\n".join(lines)


def _escape_html(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _format_plan_html(plan: dict) -> str:
    """Format research plan as styled HTML for the approval card."""
    sections = plan.get("desired_structure") or plan.get("section_names") or []
    if isinstance(sections, list) and sections and isinstance(sections[0], dict):
        section_list = [(s.get("id", ""), s.get("title", "Section")) for s in sections]
    elif isinstance(sections, list):
        section_list = [(str(i + 1), t) for i, t in enumerate(sections) if isinstance(t, str)]
    else:
        section_list = []

    parts = ['<div class="plan-view">']
    if plan.get("objective"):
        parts.append(f'<p class="plan-obj">Objective: {_escape_html(str(plan["objective"]))}</p>')
    parts.append('<ol class="plan-ol">')
    for i, (_sid, title) in enumerate(section_list, 1):
        parts.append(f'<li><span class="plan-num">{i}</span><span class="plan-title">{_escape_html(str(title))}</span></li>')
    parts.append("</ol></div>")
    return "\n".join(parts)


def _build_report_from_final(final: dict, query: str) -> tuple[str, str]:
    """Extract report and trace summary from final state."""
    messages = final.get("messages") or []
    if messages:
        last = messages[-1]
        report = getattr(last, "content", None) or ""
    else:
        report = final.get("report_markdown") or ""
    report = report or "No report generated."

    sources_from_state = final.get("sources") or []
    if not sources_from_state:
        evidence = final.get("writer_evidence_subset") or []
        sources_from_state = [
            {"index": i, "url": e.get("url", ""), "title": e.get("title", "")}
            for i, e in enumerate(evidence, 1)
        ]
    if sources_from_state:
        sources_block = "\n\n## Sources\n\n" + "\n".join(
            f"[{s.get('index', i)}] {s.get('url', '')} — *{s.get('title', 'Untitled')}*"
            for i, s in enumerate(sources_from_state, 1)
        )
        if "## Sources" in report:
            idx = report.find("## Sources")
            rest = report[idx:].strip()
            if not rest.replace("## Sources", "").replace("Sources list:", "").strip() or "[1]" not in rest:
                report = report[:idx].rstrip() + sources_block
        else:
            report = report.rstrip() + sources_block

    trace = final.get("research_trace") or {}
    sections = trace.get("sections_created", 0)
    conflicts = trace.get("conflicts_detected", 0)
    writer_count = trace.get("writer_evidence_count", 0)
    trace_summary = f"Sections: {sections} | Conflicts detected: {conflicts} | Evidence items: {writer_count}"
    return report, trace_summary


async def run_research_async(
    query: str,
    config_path: str | None,
    output_dir: str,
    run_evals: bool,
    research_mode: str | None = None,
):
    """Run graph until completion/interrupt. Yield (progress, report, trace, plan, approval_state, active_node)."""
    progress_lines: list[str] = []
    cfg = load_config_file(
        Path(config_path) if config_path else None,
        research_mode=research_mode,
    )
    effective_cfg = get_config({"configurable": cfg})
    logger.info(
        "[config] research_mode=%s | effective settings | provider=%s depth=%s max_iter=%s qpi=%s rpq=%s writer_ctx=%s section_iter=%s section_qpi=%s cache=%s",
        research_mode or "(default file only)",
        effective_cfg.get("search_provider"),
        effective_cfg.get("search_depth"),
        effective_cfg.get("max_iterations"),
        effective_cfg.get("queries_per_iteration"),
        effective_cfg.get("results_per_query"),
        effective_cfg.get("writer_context_max_items"),
        effective_cfg.get("section_max_iterations"),
        effective_cfg.get("section_queries_per_iteration"),
        effective_cfg.get("cache_enabled"),
    )
    logger.info(
        "[config] cache paths | db=%s | writes_log=%s | anchor=%s",
        effective_cfg.get("cache_db_path"),
        str(Path(effective_cfg.get("cache_db_path", "")).parent / "cache_writes.log")
        if effective_cfg.get("cache_db_path")
        else "(n/a)",
        cfg.get("_cache_path_anchor", "(none)"),
    )
    thread_id = f"research-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    run_config: dict[str, Any] = {
        "configurable": {**cfg, "thread_id": thread_id},
        "run_name": f"deep-research: {query[:60]}",
        "metadata": {"query": query},
    }

    graph = _get_graph()
    if graph is None:
        yield "Error: MemorySaver not available (install langgraph with checkpoint support).", "", "", "", None, None
        return

    initial_state = {"messages": [HumanMessage(content=query)]}

    # Phase 1: stream until end or interrupt
    async for chunk in graph.astream(
        initial_state,
        config=run_config,
        stream_mode="updates",
    ):
        active_node: str | None = None
        for node_name, data in chunk.items():
            active_node = node_name
            if node_name == "decompose_into_sections" and data:
                section_tasks = data.get("section_tasks") or []
                if section_tasks:
                    line = _section_count_line(len(section_tasks))
                    if line:
                        progress_lines.append(line)
            for line in _progress_line(node_name, data if isinstance(data, dict) else {}):
                progress_lines.append(line)
        progress_log = "\n".join(progress_lines)
        yield progress_log, "", "", "", None, active_node

    state_snapshot = graph.get_state(run_config)
    next_nodes = getattr(state_snapshot, "next", None) if state_snapshot else None
    if next_nodes and state_snapshot.values:
        # Interrupted: show plan and wait for approval
        plan = (state_snapshot.values or {}).get("research_plan") or {}
        plan_html = _format_plan_html(plan)
        approval_state = {
            "thread_id": thread_id,
            "run_config": run_config,
            "query": query,
            "run_evals": run_evals,
            "output_dir": output_dir or "",
            "config_path": config_path or "",
            "research_mode": research_mode or "",
            "progress_so_far": "\n".join(progress_lines),
            "plan": plan,
        }
        yield "\n".join(progress_lines), "", "", plan_html, approval_state, None
        return

    # Stream completed without interrupt: check for search error or build report
    final = state_snapshot.values if state_snapshot else {}
    error_message = final.get("error_message") or ""
    if error_message:
        progress_lines.append("Search failed. Stopping.")
        progress_log = "\n".join(progress_lines)
        error_report = f"## Search API failed\n\n{error_message}\n\nPlease check your API key and credits (e.g. Gensee, Tavily, or Exa), then try again."
        yield progress_log, error_report, "", "", None, None
        return

    report, trace_summary = _build_report_from_final(final, query)

    evals_for_json: dict[str, Any] | None = None

    if run_evals:
        try:
            from deep_research.evals import async_run_evals
            evals_result = await async_run_evals(
                report_markdown=report,
                report_outline=final.get("report_outline") or [],
                writer_evidence=final.get("writer_evidence_subset") or [],
                knowledge_gaps=final.get("knowledge_gaps") or [],
                section_results=final.get("section_results"),
                research_trace=final.get("research_trace") or {},
                query=query,
            )
            # Persistable eval structure (mirrors run.py behavior)
            evals_for_json = {}
            for name, result in evals_result.items():
                if len(result) == 3:
                    score, reason, section_scores = result
                    evals_for_json[name] = {
                        "score": score,
                        "reasoning": reason,
                        "section_scores": section_scores,
                    }
                else:
                    score, reason = result[0], result[1]
                    evals_for_json[name] = {"score": score, "reasoning": reason}

            eval_lines = [trace_summary, ""]
            for name, result in evals_result.items():
                score, reason = result[0], result[1]
                eval_lines.append(f"**{name}**: {score:.2f} — {reason}")
            trace_summary = "\n".join(eval_lines)
        except Exception as e:
            trace_summary = trace_summary + f"\n\nEvals error: {e}"

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        safe_query = re.sub(r"[^\w\s-]", "", query)[:40].strip().replace(" ", "_") or "report"
        out_path = os.path.join(output_dir, f"report_{safe_query}_{ts}.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
        progress_lines.append(f"Report saved to {out_path}")

        # Save offline evidence for later inspection (mirrors run.py)
        evidence_path = out_path.replace(".md", "_evidence.json")
        evidence_data = {
            "writer_evidence_subset": final.get("writer_evidence_subset") or [],
            "merged_evidence": final.get("merged_evidence") or [],
            "section_results": final.get("section_results") or [],
        }
        with open(evidence_path, "w", encoding="utf-8") as f:
            json.dump(evidence_data, f, indent=2, default=str)
        progress_lines.append(f"Evidence saved to {evidence_path}")

        # Save eval results (mirrors run.py)
        if evals_for_json is not None:
            evals_path = out_path.replace(".md", "_evals.json")
            with open(evals_path, "w", encoding="utf-8") as f:
                json.dump(evals_for_json, f, indent=2, default=str)
            progress_lines.append(f"Evals saved to {evals_path}")

    progress_log = "\n".join(progress_lines)
    yield progress_log, report, trace_summary, "", None, None


async def resume_after_approval_async(approval_state: dict[str, Any], run_evals: bool, output_dir: str):
    """Resume graph after Proceed. Yield (progress, report, trace, plan, approval_state, active_node)."""
    if not approval_state or not approval_state.get("run_config"):
        yield "No run to resume. Start a new research run first.", "", "", "", None, None
        return

    run_config = approval_state["run_config"]
    query = approval_state.get("query", "")
    progress_lines = (approval_state.get("progress_so_far") or "").split("\n")
    if isinstance(progress_lines, str):
        progress_lines = [progress_lines] if progress_lines else []

    graph = _get_graph()
    if graph is None:
        yield "Error: Graph not available.", "", "", "", None, None
        return

    resume_cmd = Command(resume=True) if Command else True
    async for chunk in graph.astream(resume_cmd, config=run_config, stream_mode="updates"):
        active_node: str | None = None
        for node_name, data in chunk.items():
            active_node = node_name
            if node_name == "decompose_into_sections" and data:
                section_tasks = data.get("section_tasks") or []
                if section_tasks:
                    line = _section_count_line(len(section_tasks))
                    if line:
                        progress_lines.append(line)
            for line in _progress_line(node_name, data if isinstance(data, dict) else {}):
                progress_lines.append(line)
        progress_log = "\n".join(progress_lines)
        yield progress_log, "", "", "", None, active_node

    final = graph.get_state(run_config).values or {}
    error_message = final.get("error_message") or ""
    if error_message:
        progress_lines.append("Search failed. Stopping.")
        progress_log = "\n".join(progress_lines)
        error_report = f"## Search API failed\n\n{error_message}\n\nPlease check your API key and credits (e.g. Gensee, Tavily, or Exa), then try again."
        yield progress_log, error_report, "", "", None, None
        return

    report, trace_summary = _build_report_from_final(final, query)

    evals_for_json: dict[str, Any] | None = None

    if run_evals:
        try:
            from deep_research.evals import async_run_evals
            evals_result = await async_run_evals(
                report_markdown=report,
                report_outline=final.get("report_outline") or [],
                writer_evidence=final.get("writer_evidence_subset") or [],
                knowledge_gaps=final.get("knowledge_gaps") or [],
                section_results=final.get("section_results"),
                research_trace=final.get("research_trace") or {},
                query=query,
            )
            evals_for_json = {}
            for name, result in evals_result.items():
                if len(result) == 3:
                    score, reason, section_scores = result
                    evals_for_json[name] = {
                        "score": score,
                        "reasoning": reason,
                        "section_scores": section_scores,
                    }
                else:
                    score, reason = result[0], result[1]
                    evals_for_json[name] = {"score": score, "reasoning": reason}

            eval_lines = [trace_summary, ""]
            for name, result in evals_result.items():
                score, reason = result[0], result[1]
                eval_lines.append(f"**{name}**: {score:.2f} — {reason}")
            trace_summary = "\n".join(eval_lines)
        except Exception as e:
            trace_summary = trace_summary + f"\n\nEvals error: {e}"

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        safe_query = re.sub(r"[^\w\s-]", "", query)[:40].strip().replace(" ", "_") or "report"
        out_path = os.path.join(output_dir, f"report_{safe_query}_{ts}.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
        progress_lines.append(f"Report saved to {out_path}")

        # Save offline evidence for later inspection (mirrors run.py)
        evidence_path = out_path.replace(".md", "_evidence.json")
        evidence_data = {
            "writer_evidence_subset": final.get("writer_evidence_subset") or [],
            "merged_evidence": final.get("merged_evidence") or [],
            "section_results": final.get("section_results") or [],
        }
        with open(evidence_path, "w", encoding="utf-8") as f:
            json.dump(evidence_data, f, indent=2, default=str)
        progress_lines.append(f"Evidence saved to {evidence_path}")

        # Save eval results (mirrors run.py)
        if evals_for_json is not None:
            evals_path = out_path.replace(".md", "_evals.json")
            with open(evals_path, "w", encoding="utf-8") as f:
                json.dump(evals_for_json, f, indent=2, default=str)
            progress_lines.append(f"Evals saved to {evals_path}")

    progress_log = "\n".join(progress_lines)
    yield progress_log, report, trace_summary, "", None, None


async def apply_edit_async(approval_state: dict[str, Any], feedback: str):
    """Apply user feedback to the plan and return updated plan. Yield (progress, report, trace, plan_md, approval_state)."""
    if not approval_state or not approval_state.get("run_config"):
        yield "", "", "", '<p class="plan-view">No run in progress.</p>', None
        return
    if not (feedback or feedback.strip()):
        plan = approval_state.get("plan") or {}
        yield (
            approval_state.get("progress_so_far", ""),
            "",
            "",
            _format_plan_html(plan) + '<p class="plan-msg">Enter feedback above and click Apply edit.</p>',
            approval_state,
        )
        return

    from run import replan_with_feedback

    run_config = approval_state["run_config"]
    query = approval_state["query"]
    configurable = run_config.get("configurable") or {}
    current = _get_graph().get_state(run_config).values or {}
    current_plan = _json_safe(current.get("research_plan") or {})
    planner_model = current.get("planner_model") or "gpt-4o-mini"
    configurable_safe = _json_safe(configurable)
    research_trace_safe = _json_safe(current.get("research_trace") or {})

    try:
        update = await replan_with_feedback(
            query,
            feedback.strip(),
            current_plan,
            planner_model,
            {**configurable_safe, "research_trace": research_trace_safe},
        )
    except Exception as e:
        yield (
            approval_state.get("progress_so_far", ""),
            "",
            "",
            _format_plan_html(current_plan) + f'<p class="plan-msg plan-err">Edit error: {_escape_html(str(e))}</p>',
            approval_state,
        )
        return

    _get_graph().update_state(run_config, update, as_node="create_research_plan")
    state_snapshot = _get_graph().get_state(run_config)
    new_plan = (state_snapshot.values or {}).get("research_plan") or {}
    approval_state["plan"] = new_plan
    plan_html = _format_plan_html(new_plan) + '<p class="plan-msg">Plan updated. Proceed or edit again.</p>'
    yield (
        approval_state.get("progress_so_far", ""),
        "",
        "",
        plan_html,
        approval_state,
    )


# ---- Gradio handlers (async generators); yield 8-item tuple for UI ----

def _yield_ui(
    progress_log: str,
    report_md: str,
    plan_content: str,
    approval_state: dict | None,
    graph_html: str,
    *,
    running: bool = False,
):
    """Build 8-item UI tuple including graph HTML."""
    import gradio as gr  # noqa: I001
    # Progress bar temporarily disabled in UI.
    progress_html = ""
    approval_visible = gr.update(visible=bool(approval_state))
    if report_md and report_md.strip():
        tabs_update = gr.update(selected=1)  # Report tab index
    else:
        tabs_update = gr.update()
    btn_update = gr.update(interactive=not running)
    return progress_html, plan_content or "", approval_state, approval_visible, report_md or "", tabs_update, btn_update, graph_html


async def run_research(query: str, research_mode: str):
    """Start research; yield 8-item UI tuples. Fixed config/output/evals."""
    base_graph_html = _make_graph_html(active_node=None, completed_nodes=set())
    if not (query or query.strip()):
        progress_html = ""
        import gradio as gr
        yield progress_html, "", None, gr.update(visible=False), "", gr.update(), gr.update(interactive=True), base_graph_html
        return
    query = query.strip()
    import gradio as gr
    completed_nodes: set[str] = set()
    last = None
    mode = (research_mode or "advanced").strip().lower()
    if mode not in ("basic", "advanced"):
        mode = "advanced"
    try:
        async for progress, report, _trace, plan_md, approval_state, active_node in run_research_async(
            query,
            config_path="",
            output_dir="output",
            run_evals=True,
            research_mode=mode,
        ):
            if active_node and active_node in _GRAPH_NODE_IDS:
                completed_nodes.add(active_node)
            display_active = active_node
            # Graph is paused for human approval/edit at this point.
            if approval_state:
                display_active = "human_plan_feedback"
            graph_html = _make_graph_html(active_node=display_active, completed_nodes=completed_nodes)
            last = (progress, report, plan_md, approval_state, graph_html)
            yield _yield_ui(progress, report, plan_md, approval_state, graph_html, running=True)
        if last is not None:
            yield _yield_ui(*last, running=False)
    except Exception as e:
        _log_exception(e, "run_research")
        err_msg = _format_error(e)
        yield f"<p>{_escape_html(err_msg)}</p>", "", None, gr.update(visible=False), "", gr.update(), gr.update(interactive=True), base_graph_html


async def resume_proceed(approval_state: dict | None):
    """Resume after Proceed; fixed run_evals and output_dir."""
    base_graph_html = _make_graph_html(active_node=None, completed_nodes=set())
    if not approval_state:
        import gradio as gr
        yield "", "", None, gr.update(visible=False), "", gr.update(), gr.update(interactive=True), base_graph_html
        return
    import gradio as gr
    # When resuming after approval, pre-mark nodes already completed before pause.
    completed_nodes: set[str] = {
        "ingest_request",
        "classify_complexity",
        "create_research_plan",
        "human_plan_feedback",
    }
    last = None
    try:
        async for progress, report, _trace, plan_md, _, active_node in resume_after_approval_async(
            approval_state, run_evals=True, output_dir="output"
        ):
            if active_node and active_node in _GRAPH_NODE_IDS:
                completed_nodes.add(active_node)
            graph_html = _make_graph_html(active_node=active_node, completed_nodes=completed_nodes)
            last = (progress, report, plan_md, None, graph_html)
            yield _yield_ui(progress, report, plan_md, None, graph_html, running=True)
        if last is not None:
            yield _yield_ui(*last, running=False)
    except Exception as e:
        _log_exception(e, "resume_proceed")
        err_msg = _format_error(e)
        yield f"<p>{_escape_html(err_msg)}</p>", "", None, gr.update(visible=False), "", gr.update(), gr.update(interactive=True), base_graph_html


async def apply_edit(approval_state: dict | None, feedback: str):
    """Apply edit feedback; yield 8-item UI tuples. Button stays enabled."""
    base_graph_html = _make_graph_html(active_node=None, completed_nodes=set())
    if not approval_state:
        import gradio as gr
        progress_html = ""
        yield progress_html, '<p class="plan-view">No run in progress.</p>', None, gr.update(visible=False), "", gr.update(), gr.update(interactive=True), base_graph_html
        return
    import gradio as gr
    try:
        if feedback and feedback.strip():
            # While applying user feedback, briefly highlight planner node.
            preview_plan = _format_plan_html(approval_state.get("plan") or {})
            editing_graph_html = _make_graph_html(
                active_node="create_research_plan",
                completed_nodes={
                    "ingest_request",
                    "classify_complexity",
                },
            )
            yield _yield_ui(
                approval_state.get("progress_so_far", ""),
                "",
                preview_plan,
                approval_state,
                editing_graph_html,
                running=True,
            )
        async for progress, report, _trace, plan_html, new_state in apply_edit_async(approval_state, feedback or ""):
            # After replan, return to waiting on human plan feedback.
            waiting_graph_html = _make_graph_html(
                active_node="human_plan_feedback",
                completed_nodes={
                    "ingest_request",
                    "classify_complexity",
                    "create_research_plan",
                },
            )
            yield _yield_ui(progress, report, plan_html, new_state, waiting_graph_html, running=False)
    except Exception as e:
        _log_exception(e, "apply_edit")
        err_msg = _format_error(e)
        progress_html = f"<p>{_escape_html(err_msg)}</p>"
        yield progress_html, "", None, gr.update(visible=False), "", gr.update(), gr.update(interactive=True), base_graph_html


def cancel_approval(_approval_state):
    """Clear approval state and hide plan; return 8-item UI tuple."""
    import gradio as gr
    progress_html = ""
    graph_html = _make_graph_html(active_node=None, completed_nodes=set())
    return progress_html, "", None, gr.update(visible=False), "", gr.update(), gr.update(interactive=True), graph_html


def main():
    import gradio as gr

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    custom_css = """
    /* ── Progress bar ─────────────────────────────────────────────────── */
    .pr-wrap { margin: 1rem 0; }
    .pr-track {
        height: 8px;
        border-radius: 4px;
        background: #e2e8f0;
        overflow: hidden;
    }
    .pr-fill {
        height: 100%;
        border-radius: 4px;
        background: linear-gradient(90deg, #3b82f6, #60a5fa);
        transition: width 0.3s ease;
    }
    .pr-fill-done {
        height: 100%;
        border-radius: 4px;
        background: #22c55e;
        transition: width 0.3s ease;
    }
    .pr-label {
        margin: 0.5rem 0 0;
        font-size: 0.9rem;
        color: #64748b;
    }

    /* ── Plan approval card ─────────────────────────────────────────────── */
    #plan-approval-card {
        border: 2px solid #f59e0b !important;
        border-radius: 10px !important;
        background: #fffbeb !important;
        padding: 20px 24px 16px !important;
        margin-top: 12px !important;
        margin-bottom: 12px !important;
    }
    #plan-approval-card .gr-markdown h3 { color: #92400e; }

    /* ── Plan view (numbered sections, ChatGPT-style) ─────────────────────── */
    .plan-view { padding: 4px 0 12px; }
    .plan-obj { font-size: 0.95rem; color: #475569; margin-bottom: 16px; }
    .plan-ol { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 10px; }
    .plan-ol li { display: flex; align-items: flex-start; gap: 12px; }
    .plan-num {
        min-width: 28px; height: 28px; border-radius: 50%; background: #1d4ed8;
        color: #fff; font-size: 0.8rem; font-weight: 700;
        display: flex; align-items: center; justify-content: center; flex-shrink: 0;
    }
    .plan-title { font-size: 0.95rem; line-height: 1.5; padding-top: 4px; }
    .plan-msg { font-size: 0.9rem; color: #64748b; margin-top: 12px; }
    .plan-err { color: #dc2626; }

    /* ── Report document (Report tab) ────────────────────────────────────── */
    #full-report .prose, #full-report .gr-markdown {
        max-width: 800px !important;
        margin: 0 auto !important;
        font-size: 1.05rem !important;
        line-height: 1.9 !important;
        padding: 2rem 1rem !important;
    }
    #full-report .prose h1, #full-report .gr-markdown h1 {
        font-size: 1.75rem !important;
        margin-top: 0 !important;
        padding-bottom: 0.5rem !important;
        border-bottom: 1px solid #e2e8f0 !important;
    }
    #full-report .prose h2, #full-report .gr-markdown h2 {
        font-size: 1.35rem !important;
        margin-top: 2rem !important;
    }
    #full-report .prose h3, #full-report .gr-markdown h3 {
        font-size: 1.15rem !important;
        margin-top: 1.5rem !important;
    }
    #full-report .prose code, #full-report .gr-markdown code {
        font-family: ui-monospace, monospace !important;
        font-size: 0.9em !important;
        background: #f1f5f9 !important;
        padding: 0.15em 0.4em !important;
        border-radius: 4px !important;
    }
    #full-report .prose, #full-report .gr-markdown {
        max-height: 75vh !important;
        overflow-y: auto !important;
    }

    /* ── Action buttons row ─────────────────────────────────────────────── */
    #approval-buttons { gap: 8px !important; }
    """

    with gr.Blocks(
        title="Deep Research Agent",
        theme=gr.themes.Soft(),
        css=custom_css,
    ) as demo:

        approval_state = gr.State(value=None)

        with gr.Tabs(elem_id="main_tabs") as main_tabs:
            with gr.Tab("Research", id="research_tab"):
                gr.Markdown(
                    "# Deep Research\n"
                    "Enter a research question. The agent will draft a plan, pause for your approval, "
                    "then run the full research and open the report."
                )
                query = gr.Textbox(
                    label="Research question",
                    placeholder="e.g. What are the main differences between LangGraph and CrewAI?",
                    lines=3,
                )
                research_mode = gr.Radio(
                    choices=[
                        ("Basic — faster, fewer searches", "basic"),
                        ("Advanced — deeper research", "advanced"),
                    ],
                    value="advanced",
                    label="Mode",
                )
                submit_btn = gr.Button("Run Deep Research", variant="primary", size="lg")

                progress_html = gr.HTML(value="")
                graph_viz_html = gr.HTML(value=_make_graph_html(active_node=None, completed_nodes=set()), elem_id="graph-viz")

                with gr.Group(visible=False, elem_id="plan-approval-card") as approval_section:
                    gr.Markdown(
                        "### Review Research Plan\n\n"
                        "The agent has drafted the plan below. Approve it or request changes."
                    )
                    plan_html = gr.HTML(value="")
                    gr.Markdown(
                        "**Happy with the plan?** Click **Proceed**. "
                        "**Want changes?** Type feedback below and click **Apply edit**."
                    )
                    edit_feedback = gr.Textbox(
                        label="Feedback for the planner (optional)",
                        placeholder="e.g. Add a section on X. Remove the section on Y.",
                        lines=3,
                    )
                    with gr.Row(elem_id="approval-buttons"):
                        proceed_btn = gr.Button("Proceed", variant="primary", scale=3)
                        apply_edit_btn = gr.Button("Apply edit", variant="secondary", scale=2)
                        cancel_btn = gr.Button("Cancel", variant="stop", scale=1)

            with gr.Tab("Report", id="report_tab"):
                new_research_btn = gr.Button("New Research", variant="secondary")
                report_md = gr.Markdown(
                    value="*Complete a research run to see the report here.*",
                    elem_id="full-report",
                )

        # ── Event wiring (8 outputs, includes graph_viz_html) ──

        submit_btn.click(
            fn=run_research,
            inputs=[query, research_mode],
            outputs=[progress_html, plan_html, approval_state, approval_section, report_md, main_tabs, submit_btn, graph_viz_html],
        )

        proceed_btn.click(
            fn=resume_proceed,
            inputs=[approval_state],
            outputs=[progress_html, plan_html, approval_state, approval_section, report_md, main_tabs, submit_btn, graph_viz_html],
        )

        apply_edit_btn.click(
            fn=apply_edit,
            inputs=[approval_state, edit_feedback],
            outputs=[progress_html, plan_html, approval_state, approval_section, report_md, main_tabs, submit_btn, graph_viz_html],
        )

        cancel_btn.click(
            fn=cancel_approval,
            inputs=[approval_state],
            outputs=[progress_html, plan_html, approval_state, approval_section, report_md, main_tabs, submit_btn, graph_viz_html],
        )

        def go_to_research():
            progress_html_init = ""
            graph_html_init = _make_graph_html(active_node=None, completed_nodes=set())
            return (
                progress_html_init,
                "",
                None,
                gr.update(visible=False),
                "*Complete a research run to see the report here.*",
                gr.update(selected=0),
                gr.update(interactive=True),
                graph_html_init,
            )

        new_research_btn.click(
            fn=go_to_research,
            inputs=[],
            outputs=[progress_html, plan_html, approval_state, approval_section, report_md, main_tabs, submit_btn, graph_viz_html],
        )

    demo.launch(server_name="127.0.0.1", server_port=7860, share=True)


if __name__ == "__main__":
    main()
