"""create_research_plan node - define research plan (no query generation)."""

import json

from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig

from deep_research.configuration import (
    DEFAULT_PLANNER_COMPLEX_MODEL,
    get_config,
)
from deep_research.prompts import RESEARCH_PLAN_PROMPT
from deep_research.research_logger import log_decision, log_node_end, log_node_start, log_prompt
from deep_research.state import ResearchState


def create_research_plan(
    state: ResearchState,
    config: RunnableConfig | None = None,
) -> dict:
    """Create a research plan: objective, structure, difficulty areas. No search queries."""
    log_node_start("create_research_plan", config)
    query = state.get("query") or ""
    planner_model = state.get("planner_model") or "gpt-4o-mini"
    cfg = get_config(config)

    prompt = RESEARCH_PLAN_PROMPT.format(query=query)
    log_prompt("create_research_plan", prompt, model=planner_model)
    llm = ChatOpenAI(model=planner_model, temperature=0)
    raw = llm.invoke([{"role": "user", "content": prompt}])
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
        data = {
            "objective": query,
            "desired_structure": [{"id": "s1", "title": "Overview", "description": query}],
            "section_names": ["Overview"],
            "difficulty_areas": [],
            "section_descriptions": [],
        }

    research_plan = {
        "objective": data.get("objective", query),
        "desired_structure": data.get("desired_structure", []),
        "section_names": data.get("section_names", []),
        "difficulty_areas": data.get("difficulty_areas", []),
        "section_descriptions": data.get("section_descriptions", []),
    }
    report_outline = research_plan.get("desired_structure", [])
    log_decision("create_research_plan", f"sections={len(report_outline)}", {"section_names": research_plan.get("section_names", [])})
    log_node_end("create_research_plan", {"sections_created": len(report_outline), "objective": research_plan.get("objective", "")[:100]})

    return {
        "research_plan": research_plan,
        "report_outline": report_outline,
        "research_trace": {
            "planner_model_used": planner_model,
            "sections_created": len(report_outline),
            "section_names": research_plan.get("section_names", []),
        },
    }


def plan_and_generate_queries(
    state: ResearchState,
    config: RunnableConfig | None = None,
) -> dict:
    """Phase 1 compatibility: define outline and generate search queries.
    Kept for backward compatibility with Phase 1 graph."""
    from deep_research.prompts import PLANNER_FOLLOWUP_PROMPT, PLANNER_INITIAL_PROMPT

    query = state.get("query") or ""
    planner_model = state.get("planner_model") or "gpt-4o-mini"
    iteration = state.get("iteration") or 0
    outline = state.get("report_outline") or []
    gaps = state.get("knowledge_gaps") or []
    seen = state.get("seen_urls") or set()
    cfg = get_config(config)

    if iteration >= 1 and "mini" in (planner_model or "").lower():
        planner_model = cfg.get("planner_complex_model") or DEFAULT_PLANNER_COMPLEX_MODEL

    llm = ChatOpenAI(model=planner_model, temperature=0)

    if iteration == 0:
        prompt = PLANNER_INITIAL_PROMPT.format(query=query)
        raw = llm.invoke([{"role": "user", "content": prompt}])
        text = raw.content if hasattr(raw, "content") else str(raw)
    else:
        outline_str = json.dumps(outline, indent=2)
        gaps_str = json.dumps(gaps, indent=2)
        seen_list = list(seen)[:50]
        prompt = PLANNER_FOLLOWUP_PROMPT.format(
            query=query,
            report_outline=outline_str,
            knowledge_gaps=gaps_str,
            seen_urls=", ".join(seen_list) if seen_list else "(none yet)",
        )
        raw = llm.invoke([{"role": "user", "content": prompt}])
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
        data = {"report_outline": outline, "search_queries": []}

    report_outline = data.get("report_outline") or outline
    search_queries = data.get("search_queries") or []
    if not isinstance(search_queries, list):
        search_queries = [str(search_queries)] if search_queries else []

    return {
        "report_outline": report_outline,
        "search_queries": search_queries,
        "iteration": iteration + 1,
    }
