"""decompose_into_sections node and dispatch_sections fan-out function."""

import json

from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from langgraph.types import Send

from deep_research.configuration import get_config
from deep_research.prompts import DECOMPOSE_PROMPT, get_prompt
from deep_research.research_logger import log_decision, log_node_end, log_node_start, log_prompt, log_route
from deep_research.state import ResearchState


async def decompose_into_sections(
    state: ResearchState,
    config: RunnableConfig | None = None,
) -> dict:
    """Convert research plan into independent section tasks."""
    log_node_start("decompose_into_sections", config)
    research_plan = state.get("research_plan") or {}
    cfg = get_config(config)
    model_name = cfg.get("decompose_model") or "gpt-4o"

    plan_str = json.dumps(research_plan, indent=2)
    prompt = get_prompt("decompose", cfg, DECOMPOSE_PROMPT).format(research_plan=plan_str)
    log_prompt("decompose_into_sections", prompt, model=model_name)

    llm = ChatOpenAI(model=model_name, temperature=0)
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
        data = {"section_tasks": []}

    section_tasks = data.get("section_tasks") or []
    if not isinstance(section_tasks, list):
        section_tasks = []
    if not section_tasks:
        section_tasks = [{
            "id": "s1",
            "title": "Overview",
            "goal": research_plan.get("objective", "Research the topic"),
            "key_questions": ["What are the key findings?"],
            "success_criteria": ["At least 2 sources"],
            "priority": 1,
            "search_hints": [],
        }]

    # Ensure each task has required fields
    for i, t in enumerate(section_tasks):
        if not isinstance(t, dict):
            section_tasks[i] = {
                "id": f"s{i+1}",
                "title": "Section",
                "goal": "",
                "key_questions": [],
                "success_criteria": [],
                "priority": 1,
                "search_hints": [],
            }
        else:
            t.setdefault("id", f"s{i+1}")
            t.setdefault("title", "Section")
            t.setdefault("goal", "")
            t.setdefault("key_questions", [])
            t.setdefault("success_criteria", [])
            t.setdefault("priority", 1)
            t.setdefault("search_hints", [])

    cfg = get_config(config)
    section_max_iterations = cfg.get("section_max_iterations", 3)
    log_decision("decompose_into_sections", f"{len(section_tasks)} section tasks", {"section_ids": [t.get("id") for t in section_tasks]})
    log_node_end("decompose_into_sections", {"section_tasks": len(section_tasks), "section_max_iterations": section_max_iterations})

    return {
        "section_tasks": section_tasks,
        "section_max_iterations": section_max_iterations,
        "research_trace": {
            **(state.get("research_trace") or {}),
            "sections_created": len(section_tasks),
            "section_names": [t.get("title", "") for t in section_tasks],
        },
    }


def dispatch_sections(state: ResearchState, config: RunnableConfig | None = None) -> list[Send]:
    """Return Send objects for parallel section workers (one per section task)."""
    section_tasks = state.get("section_tasks") or []
    cfg = get_config(config)
    max_parallel = cfg.get("max_parallel_sections", 6)
    tasks = section_tasks[:max_parallel]
    log_route("decompose_into_sections", "section_worker", f"dispatching {len(tasks)} section workers: {[t.get('id') for t in tasks]}")
    global_seen = state.get("global_seen_urls") or set()
    query = state.get("query") or ""
    section_max_iterations = state.get("section_max_iterations", 3)

    if not section_tasks:
        return []

    return [
        Send(
            "section_worker",
            {
                "section_task": task,
                "global_seen_urls": global_seen,
                "query": query,
                "section_max_iterations": section_max_iterations,
            },
        )
        for task in tasks
    ]
