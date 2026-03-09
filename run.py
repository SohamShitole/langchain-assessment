#!/usr/bin/env python3
"""CLI entry point for the deep research agent."""

import argparse
import json
import os
import re
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import HumanMessage

from deep_research.configuration import load_config_file
from deep_research.graph import create_research_graph


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the deep research agent on a query."
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="",
        help="Research query (or read from stdin)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config.yaml (default: ./config.yaml)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Max research iterations (overrides config)",
    )
    parser.add_argument(
        "--search-provider",
        type=str,
        choices=["gensee", "tavily"],
        default=None,
        help="Search provider: gensee or tavily (overrides config)",
    )
    parser.add_argument(
        "--search-depth",
        type=str,
        choices=["basic", "advanced"],
        default=None,
        help="Tavily search depth: basic (1 credit) or advanced (2 credits)",
    )
    parser.add_argument(
        "--extract-depth",
        type=str,
        choices=["basic", "advanced"],
        default=None,
        help="Tavily extract depth for enrichment",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output directory for reports (default: reports/); each run creates a unique file",
    )
    parser.add_argument(
        "--eval",
        action="store_true",
        help="Run evals after report generation",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Save research trace JSON alongside report",
    )
    args = parser.parse_args()

    query = args.query.strip()
    if not query:
        query = sys.stdin.read().strip()
    if not query:
        print("Usage: python run.py 'your research query'", file=sys.stderr)
        sys.exit(1)

    # Load config: file first, then overlay CLI overrides
    cfg = load_config_file(args.config)
    if args.max_iterations is not None:
        cfg["max_iterations"] = args.max_iterations
    if args.search_provider is not None:
        cfg["search_provider"] = args.search_provider
    if args.search_depth is not None:
        cfg["search_depth"] = args.search_depth
    if args.extract_depth is not None:
        cfg["extract_depth"] = args.extract_depth
    if args.max_iterations is not None:
        cfg["section_max_iterations"] = args.max_iterations

    run_config = {"configurable": cfg}

    graph = create_research_graph()
    initial_state = {"messages": [HumanMessage(content=query)]}
    final = graph.invoke(initial_state, config=run_config)

    messages = final.get("messages") or []
    if messages:
        last = messages[-1]
        report = getattr(last, "content", None) or ""
    else:
        report = final.get("report_markdown") or ""

    report = report or "No report generated."

    # Create unique filename per run
    output_dir = args.output or "reports"
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_query = re.sub(r"[^\w\s-]", "", query)[:40].strip().replace(" ", "_")
    safe_query = safe_query if safe_query else "report"
    output_path = os.path.join(output_dir, f"report_{safe_query}_{ts}.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report saved to {output_path}")

    # Observability summary
    trace = final.get("research_trace") or {}
    sections = trace.get("sections_created", 0)
    conflicts = trace.get("conflicts_detected", 0)
    writer_count = trace.get("writer_evidence_count", 0)
    print(f"\n[Trace] sections={sections} conflicts={conflicts} writer_evidence={writer_count}")

    if args.trace:
        trace_path = output_path.replace(".md", "_trace.json")
        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(trace, f, indent=2, default=str)
        print(f"Trace saved to {trace_path}")

    if args.eval:
        from deep_research.evals import run_evals
        evals = run_evals(
            report_markdown=report,
            report_outline=final.get("report_outline") or [],
            writer_evidence=final.get("writer_evidence_subset") or [],
            knowledge_gaps=final.get("knowledge_gaps") or [],
            section_results=final.get("section_results"),
            research_trace=trace,
            query=query,
        )
        print("\n[Evals]")
        for name, (score, reason) in evals.items():
            print(f"  {name}: {score:.2f} - {reason}")

    print(report)


if __name__ == "__main__":
    main()
