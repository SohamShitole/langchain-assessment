"""Focused tests for the deep research graph."""

import asyncio
from pathlib import Path

import pytest

from deep_research.graph import create_research_graph, create_research_graph_phase1
from deep_research.routing import conflict_route, route, section_route
from deep_research.state import ResearchState, SectionWorkerState
from deep_research.nodes.decompose import dispatch_sections
from deep_research.nodes.merge import merge_section_evidence
from deep_research.configuration import load_config_file
from deep_research.nodes.conflicts import ResolvedConflict, AdjudicationOutput
from deep_research.evals import run_evals
from langchain_core.messages import AIMessage, HumanMessage


def test_graph_compiles():
    """Phase 2 graph compiles successfully."""
    g = create_research_graph()
    assert g is not None
    assert hasattr(g, "invoke")


def test_phase1_graph_compiles():
    """Phase 1 graph compiles successfully."""
    g = create_research_graph_phase1()
    assert g is not None
    assert hasattr(g, "invoke")


def test_section_dispatch_returns_sends():
    """dispatch_sections returns one Send per section task."""
    state: ResearchState = {
        "section_tasks": [
            {"id": "s1", "title": "A", "goal": "x"},
            {"id": "s2", "title": "B", "goal": "y"},
        ],
        "global_seen_urls": set(),
        "query": "test",
        "section_max_iterations": 2,
    }
    sends = dispatch_sections(state)
    assert len(sends) == 2
    assert all(s.node == "section_worker" for s in sends)
    assert sends[0].arg["section_task"]["id"] == "s1"
    assert sends[1].arg["section_task"]["id"] == "s2"


def test_section_dispatch_empty_fallback():
    """dispatch_sections returns empty list when no tasks."""
    state: ResearchState = {"section_tasks": [], "global_seen_urls": set(), "query": ""}
    sends = dispatch_sections(state)
    assert sends == []


def test_merge_dedup():
    """merge_section_evidence deduplicates by URL."""
    state: ResearchState = {
        "section_results": [
            {
                "section_id": "s1",
                "evidence": [
                    {"url": "https://a.com", "title": "A", "snippet": "x"},
                    {"url": "https://b.com", "title": "B", "snippet": "y"},
                ],
                "coverage_score": 7,
                "gaps": [],
                "summary": {},
                "confidence": 0.8,
            },
            {
                "section_id": "s2",
                "evidence": [
                    {"url": "https://a.com", "title": "A", "snippet": "x"},
                    {"url": "https://c.com", "title": "C", "snippet": "z"},
                ],
                "coverage_score": 6,
                "gaps": [],
                "summary": {},
                "confidence": 0.7,
            },
        ],
    }
    out = asyncio.run(merge_section_evidence(state))
    merged = out["merged_evidence"]
    urls = [m["url"] for m in merged]
    assert "https://a.com" in urls
    assert urls.count("https://a.com") == 1
    assert set(merged[urls.index("https://a.com")]["supporting_sections"]) == {"s1", "s2"}
    assert merged[urls.index("https://a.com")]["cross_cutting"] is True


def test_conflict_route():
    """conflict_route routes to resolve or prepare_writer."""
    s1: ResearchState = {
        "conflict_resolution_needed": True,
        "conflict_resolution_enabled": True,
    }
    assert conflict_route(s1) == "conflict_resolution_research"
    s2: ResearchState = {
        "conflict_resolution_needed": False,
        "conflict_resolution_enabled": True,
    }
    assert conflict_route(s2) == "prepare_writer_context"
    s3: ResearchState = {
        "conflict_resolution_needed": True,
        "conflict_resolution_enabled": False,
    }
    assert conflict_route(s3) == "prepare_writer_context"


def test_section_route():
    """section_route routes based on coverage and iteration."""
    s1: SectionWorkerState = {"section_complete": True, "section_iteration": 1}
    assert section_route(s1) == "section_complete"
    s2: SectionWorkerState = {
        "section_complete": False,
        "section_iteration": 1,
        "section_max_iterations": 3,
    }
    assert section_route(s2) == "section_needs_more"
    s3: SectionWorkerState = {
        "section_complete": False,
        "section_iteration": 3,
        "section_max_iterations": 3,
    }
    assert section_route(s3) == "section_complete"


def test_route_sufficient_coverage():
    """Route (Phase 1) returns prepare_writer_context when coverage sufficient."""
    state: ResearchState = {
        "coverage_status": "sufficient",
        "iteration": 1,
        "max_iterations": 3,
    }
    assert route(state) == "prepare_writer_context"


def test_route_insufficient_with_iterations_left():
    """Route returns plan_and_generate_queries when insufficient."""
    state: ResearchState = {
        "coverage_status": "insufficient",
        "iteration": 1,
        "max_iterations": 3,
    }
    assert route(state) == "plan_and_generate_queries"


def test_route_budget_exhausted():
    """Route returns prepare_writer_context when budget exhausted."""
    state: ResearchState = {
        "coverage_status": "insufficient",
        "iteration": 3,
        "max_iterations": 3,
    }
    assert route(state) == "prepare_writer_context"


def test_evals_run():
    """Evals run and return scores."""
    results = run_evals(
        report_markdown="# Report\n[1] says X. [2] says Y.",
        report_outline=[{"id": "s1", "title": "Overview"}],
        writer_evidence=[
            {"url": "u1", "title": "T1", "snippet": "S1", "is_primary": True},
        ],
        knowledge_gaps=[],
        research_trace={"sections_created": 1},
        query="Compare A and B",
    )
    assert "claim_support" in results
    assert "section_completeness" in results
    assert "source_quality" in results
    assert "factual_accuracy" in results
    assert "citation_relevance" in results
    assert "synthesis_quality" in results
    assert "tool_trajectory" in results
    assert len(results) == 10
    for k, result in results.items():
        score, reason = result[0], result[1]
        assert 0 <= score <= 1
        assert isinstance(reason, str)
        if k == "section_completeness" and len(result) == 3:
            for s in result[2]:
                assert "section_id" in s and "score" in s
                assert 0 <= s["score"] <= 1


def _has_search_key():
    return bool(
        __import__("os").environ.get("GENSEE_API_KEY")
        or __import__("os").environ.get("TAVILY_API_KEY")
    )


@pytest.mark.skipif(
    not (__import__("os").environ.get("OPENAI_API_KEY") and _has_search_key()),
    reason="OPENAI_API_KEY and GENSEE_API_KEY or TAVILY_API_KEY required for e2e",
)
def test_graph_e2e_run():
    """Phase 2 graph runs end-to-end."""
    graph = create_research_graph()
    initial = {"messages": [HumanMessage(content="What is Python? Brief overview.")]}
    config = {"configurable": {"section_max_iterations": 1}}
    final = graph.invoke(initial, config=config)
    assert "report_markdown" in final
    assert final.get("report_markdown")
    msgs = final.get("messages") or []
    assert msgs
    assert isinstance(msgs[-1], AIMessage)
    assert msgs[-1].content


@pytest.mark.skipif(
    not (__import__("os").environ.get("OPENAI_API_KEY") and _has_search_key()),
    reason="OPENAI_API_KEY and search key required",
)
def test_report_in_messages():
    """Final messages contain the report as last AIMessage."""
    graph = create_research_graph()
    initial = {"messages": [HumanMessage(content="What is 2+2?")]}
    config = {"configurable": {"section_max_iterations": 1}}
    final = graph.invoke(initial, config=config)
    msgs = final.get("messages") or []
    assert len(msgs) >= 1
    last = msgs[-1]
    assert isinstance(last, AIMessage)
    assert last.content


@pytest.mark.skipif(
    not (__import__("os").environ.get("OPENAI_API_KEY") and _has_search_key()),
    reason="OPENAI_API_KEY and search key required",
)
def test_sources_present():
    """Sources or citation-style content present."""
    graph = create_research_graph()
    initial = {"messages": [HumanMessage(content="What is LangChain?")]}
    config = {"configurable": {"section_max_iterations": 1}}
    final = graph.invoke(initial, config=config)
    sources = final.get("sources") or []
    report = final.get("report_markdown") or ""
    assert report
    has_sources = "source" in report.lower() or "http" in report.lower() or "[" in report
    assert has_sources or sources


def test_config_yaml_planner_keys():
    """config.yaml planner keys map correctly to flat config keys."""
    flat = load_config_file()
    assert "planner_simple_model" in flat, "planner_simple_model missing — config.yaml likely uses wrong key name"
    assert "planner_complex_model" in flat, "planner_complex_model missing — config.yaml likely uses wrong key name"


def test_research_mode_basic_overlay():
    """Basic preset overlay lowers max_iterations and section iterations."""
    root = Path(__file__).resolve().parent.parent
    cfg_yaml = root / "config.yaml"
    basic_overlay = root / "config_research_basic.yaml"
    if not cfg_yaml.is_file() or not basic_overlay.is_file():
        pytest.skip("config.yaml / config_research_basic.yaml not in repo root")
    flat = load_config_file(cfg_yaml, research_mode="basic")
    assert flat.get("max_iterations") == 1
    assert flat.get("queries_per_iteration") == 3
    assert flat.get("results_per_query") == 3
    assert flat.get("section_max_iterations") == 2
    assert flat.get("section_queries_per_iteration") == 3


def test_dispatch_respects_max_parallel_config():
    """dispatch_sections caps sections to max_parallel_sections from config."""
    state: ResearchState = {
        "section_tasks": [
            {"id": f"s{i}", "title": f"S{i}", "goal": "x"} for i in range(1, 6)
        ],
        "global_seen_urls": set(),
        "query": "test",
        "section_max_iterations": 2,
    }
    config = {"configurable": {"max_parallel_sections": 2}}
    sends = dispatch_sections(state, config)
    assert len(sends) == 2
    assert sends[0].arg["section_task"]["id"] == "s1"
    assert sends[1].arg["section_task"]["id"] == "s2"


def test_adjudication_models():
    """ResolvedConflict and AdjudicationOutput have expected fields."""
    rc = ResolvedConflict(
        conflicting_claims=["A", "B"],
        resolved=True,
        resolution_verdict="A wins",
        winning_claim="A",
        confidence=0.9,
    )
    assert rc.resolved is True
    assert rc.confidence == 0.9

    ao = AdjudicationOutput(resolved_conflicts=[rc])
    assert len(ao.resolved_conflicts) == 1
    dumped = ao.resolved_conflicts[0].model_dump()
    assert "resolution_verdict" in dumped
    assert "winning_claim" in dumped
