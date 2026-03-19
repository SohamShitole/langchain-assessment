#!/usr/bin/env python3
"""CLI entry point for the deep research agent."""

import argparse
import asyncio
import json
import os
import re
import sys
import uuid
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from deep_research.configuration import get_config, load_config_file
from deep_research.graph import create_research_graph
from deep_research.langsmith_redact import redact_raw_content_in_payload
from deep_research.progress import display_plan, print_progress, print_section_count
from deep_research.research_logger import close_log, init_log

try:
    from langgraph.checkpoint.memory import MemorySaver
except ImportError:
    MemorySaver = None

try:
    from langgraph.types import Command
except ImportError:
    Command = None


def _json_safe(obj):
    """Return a JSON-serializable copy (avoids 400 from API when payload has Pydantic/datetime etc.)."""
    return json.loads(json.dumps(obj, default=str))


async def replan_with_feedback(
    query: str,
    feedback: str,
    current_plan: dict,
    planner_model: str,
    config: dict,
) -> dict:
    """Revise the research plan using the original query, current plan, and user feedback.
    The LLM interprets the feedback in context and returns an updated plan (state update dict)."""
    from deep_research.prompts import RESEARCH_PLAN_EDIT_PROMPT, get_prompt

    current_plan = _json_safe(current_plan or {})
    config = _json_safe(config or {})
    cfg = get_config(config)
    template = get_prompt("research_plan_edit", cfg, RESEARCH_PLAN_EDIT_PROMPT)
    current_plan_str = json.dumps(current_plan, indent=2, default=str)
    prompt = template.format(
        query=query,
        current_plan=current_plan_str,
        feedback=feedback,
    )
    llm = ChatOpenAI(model=planner_model, temperature=0)
    raw = await llm.ainvoke([{"role": "user", "content": prompt}])
    text = raw.content if hasattr(raw, "content") else str(raw)
    text = text.strip()
    if "```" in text:
        for block in ("json", ""):
            start = f"```{block}"
            if start in text:
                i = text.find(start) + len(start)
                j = text.find("```", i)
                if j > i:
                    text = text[i:j].strip()
                    break
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Keep current plan on parse failure so we don't lose context
        data = {
            "objective": current_plan.get("objective", query),
            "desired_structure": current_plan.get("desired_structure", [{"id": "s1", "title": "Overview", "description": query}]),
            "section_names": current_plan.get("section_names", ["Overview"]),
            "difficulty_areas": current_plan.get("difficulty_areas", []),
            "section_descriptions": current_plan.get("section_descriptions", []),
        }
    research_plan = {
        "objective": data.get("objective", query),
        "desired_structure": data.get("desired_structure", []),
        "section_names": data.get("section_names", []),
        "difficulty_areas": data.get("difficulty_areas", []),
        "section_descriptions": data.get("section_descriptions", []),
    }
    report_outline = research_plan.get("desired_structure", [])
    trace = (config.get("research_trace") or {}).copy()
    trace["planner_model_used"] = planner_model
    trace["sections_created"] = len(report_outline)
    trace["section_names"] = research_plan.get("section_names", [])
    return {
        "research_plan": research_plan,
        "report_outline": report_outline,
        "research_trace": trace,
    }


async def async_main() -> None:
    """Async entry: parse args, build graph, run with ainvoke/astream, write outputs, run evals."""
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
        choices=["gensee", "gensee_deep", "tavily", "exa"],
        default=None,
        help="Search provider: gensee, gensee_deep, tavily, or exa (overrides config)",
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
        default=True,
        help="Run evals after report generation (default: on)",
    )
    parser.add_argument(
        "--no-eval",
        dest="eval",
        action="store_false",
        help="Skip evals after report generation",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Save research trace JSON alongside report",
    )
    parser.add_argument(
        "--log",
        type=str,
        nargs="?",
        const="auto",
        default=None,
        metavar="PATH",
        help="Write process log (prompts, decisions, routing) to file. "
        "Use --log for auto path (alongside report), or --log path/to/file.log",
    )
    parser.add_argument(
        "--langsmith",
        action="store_true",
        default=True,
        help="Enable LangSmith tracing for this run (default: on)",
    )
    parser.add_argument(
        "--no-langsmith",
        dest="langsmith",
        action="store_false",
        help="Disable LangSmith tracing",
    )
    parser.add_argument(
        "--langsmith-light",
        action="store_true",
        help="Enable LangSmith with inputs/outputs hidden to stay under 20MB trace limit (structure, timing, errors only)",
    )
    parser.add_argument(
        "--langsmith-project",
        type=str,
        default="deep-research-agent",
        help="LangSmith project name (default: deep-research-agent)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Skip research plan approval (non-interactive / CI)",
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

    thread_id = f"research-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    run_config = {
        "configurable": {
            **cfg,
            "thread_id": thread_id,
        },
        "run_name": f"deep-research: {query[:60]}",
        "metadata": {"query": query},
    }

    # Log file: same dir as report, same base name, .log extension
    log_path = None
    if args.log:
        output_dir = args.output or "reports"
        os.makedirs(output_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        safe_query = re.sub(r"[^\w\s-]", "", query)[:40].strip().replace(" ", "_")
        safe_query = safe_query if safe_query else "report"
        if args.log == "auto":
            log_path = os.path.join(output_dir, f"log_{safe_query}_{ts}.log")
        else:
            log_path = args.log
        init_log(log_path)
        print(f"Log file: {log_path}")

    if args.langsmith or args.langsmith_light:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_PROJECT"] = args.langsmith_project
    if args.langsmith_light:
        # Keep trace under ~20MB: hide large inputs/outputs (prompts, evidence, state).
        # You still get: run tree, node names, timing, errors, metadata.
        os.environ["LANGSMITH_HIDE_INPUTS"] = "true"
        os.environ["LANGSMITH_HIDE_OUTPUTS"] = "true"
        print("LangSmith lightweight tracing (inputs/outputs hidden to avoid size limit)")
    elif args.langsmith:
        # Redact only raw fetched content (snippet, raw_content) so trace stays under ~20MB
        # while keeping full structure (section_results, URLs, titles, etc.) in the trace.
        try:
            from langsmith import Client
            redacting_client = Client(
                hide_inputs=lambda inputs: redact_raw_content_in_payload(inputs),
                hide_outputs=lambda outputs: redact_raw_content_in_payload(outputs),
            )
            run_config["langsmith_extra"] = {"client": redacting_client}
            print("LangSmith tracing (snippet/raw_content redacted to stay under size limit)")
        except Exception as e:
            print(f"LangSmith redacting client not available: {e}", file=sys.stderr)

    # Build graph: with checkpointer for streaming + optional interrupt for plan approval
    checkpointer = MemorySaver() if MemorySaver else None
    interrupt_after = None if args.auto else (["create_research_plan"] if checkpointer else None)
    graph = create_research_graph(checkpointer=checkpointer, interrupt_after=interrupt_after)

    initial_state = {"messages": [HumanMessage(content=query)]}

    try:
        if not checkpointer:
            # No checkpointer: run with ainvoke (no progress, no plan approval)
            final = await graph.ainvoke(initial_state, config=run_config)
        else:
            # Phase 1: stream until end or interrupt (async)
            async for chunk in graph.astream(
                initial_state,
                config=run_config,
                stream_mode="updates",
            ):
                for node_name, data in chunk.items():
                    if node_name == "decompose_into_sections" and data:
                        section_tasks = data.get("section_tasks") or []
                        if section_tasks:
                            print_section_count(len(section_tasks))
                    print_progress(node_name, data if isinstance(data, dict) else {})

            # If we used interrupt, check whether we're paused for plan approval
            state_snapshot = graph.get_state(run_config)
            if interrupt_after and getattr(state_snapshot, "next", None) and state_snapshot.next:
                # Interrupted: show plan and get approval
                plan = (state_snapshot.values or {}).get("research_plan") or {}
                while True:
                    display_plan(plan)
                    try:
                        choice = input("Proceed with this plan? (Y / Edit / Cancel): ").strip().lower()
                    except EOFError:
                        choice = "y"
                    if choice in ("y", "yes", ""):
                        break
                    if choice in ("c", "cancel"):
                        print("Cancelled.", file=sys.stderr)
                        sys.exit(0)
                    if choice in ("e", "edit"):
                        try:
                            feedback = input("What would you like to change? ").strip()
                        except EOFError:
                            feedback = ""
                        if not feedback:
                            continue
                        current = state_snapshot.values or {}
                        planner_model = current.get("planner_model") or "gpt-4o-mini"
                        current_plan = current.get("research_plan") or {}
                        update = await replan_with_feedback(
                            query,
                            feedback,
                            current_plan,
                            planner_model,
                            {**run_config.get("configurable", {}), "research_trace": current.get("research_trace")},
                        )
                        graph.update_state(run_config, update, as_node="create_research_plan")
                        plan = update.get("research_plan") or {}
                        state_snapshot = graph.get_state(run_config)
                        continue
                    # Unrecognized: prompt again
                    print("Please enter Y (proceed), Edit, or Cancel.", file=sys.stderr)

                # Resume graph from interrupt (async)
                resume_cmd = Command(resume=True) if Command else True
                async for chunk in graph.astream(
                    resume_cmd,
                    config=run_config,
                    stream_mode="updates",
                ):
                    for node_name, data in chunk.items():
                        if node_name == "decompose_into_sections" and data:
                            section_tasks = data.get("section_tasks") or []
                            if section_tasks:
                                print_section_count(len(section_tasks))
                        print_progress(node_name, data if isinstance(data, dict) else {})

                final = graph.get_state(run_config).values
            else:
                # Stream completed without interrupt
                final = graph.get_state(run_config).values
    finally:
        if log_path:
            close_log()

    final = final or {}
    error_message = final.get("error_message") or ""
    if error_message:
        print("Search API failed. Stopping.", file=sys.stderr)
        print(error_message, file=sys.stderr)
        sys.exit(1)

    messages = final.get("messages") or []
    if messages:
        last = messages[-1]
        report = getattr(last, "content", None) or ""
    else:
        report = final.get("report_markdown") or ""

    report = report or "No report generated."

    # Ensure report has a non-empty Sources section when we have sources in state
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
        # If report has empty or placeholder Sources section, replace with real sources
        if "## Sources" in report:
            idx = report.find("## Sources")
            rest = report[idx:].strip()
            # Empty or only "Sources list:" with no [1] [2] lines
            if not rest.replace("## Sources", "").replace("Sources list:", "").strip() or "[1]" not in rest:
                report = report[:idx].rstrip() + sources_block
        else:
            report = report.rstrip() + sources_block

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

    # Offline evidence file when LangSmith is enabled (for local inspection without LangSmith)
    if args.langsmith or args.langsmith_light:
        evidence_path = output_path.replace(".md", "_evidence.json")
        evidence_data = {
            "writer_evidence_subset": final.get("writer_evidence_subset") or [],
            "merged_evidence": final.get("merged_evidence") or [],
            "section_results": final.get("section_results") or [],
        }
        with open(evidence_path, "w", encoding="utf-8") as f:
            json.dump(evidence_data, f, indent=2, default=str)
        print(f"Evidence saved to {evidence_path}")

    if args.eval:
        from deep_research.evals import async_run_evals
        evals = await async_run_evals(
            report_markdown=report,
            report_outline=final.get("report_outline") or [],
            writer_evidence=final.get("writer_evidence_subset") or [],
            knowledge_gaps=final.get("knowledge_gaps") or [],
            section_results=final.get("section_results"),
            research_trace=trace,
            query=query,
        )
        print("\n[Evals]")
        evals_for_json = {}
        for name, result in evals.items():
            if len(result) == 3:
                score, reason, section_scores = result
                evals_for_json[name] = {"score": score, "reasoning": reason, "section_scores": section_scores}
            else:
                score, reason = result
                evals_for_json[name] = {"score": score, "reasoning": reason}
        for name, result in evals.items():
            score, reason = result[0], result[1]
            print(f"  {name}: {score:.2f} - {reason}")
            if len(result) == 3:
                for s in result[2]:
                    print(f"    [{s.get('section_id')}] {s.get('title', '')}: {s.get('score', 0):.2f} - {s.get('reason', '')}")
        evals_path = output_path.replace(".md", "_evals.json")
        with open(evals_path, "w", encoding="utf-8") as f:
            json.dump(evals_for_json, f, indent=2)
        print(f"Evals saved to {evals_path}")

    print(report)


def main() -> None:
    """Sync entry point: run async_main in the event loop."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
