"""generate_section_queries node - generate search queries for one section."""

import json

from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig

from deep_research.configuration import get_config
from deep_research.prompts import SECTION_QUERY_FOLLOWUP_PROMPT, SECTION_QUERY_PROMPT
from deep_research.research_logger import log_decision, log_node_end, log_node_start, log_prompt
from deep_research.state import SectionWorkerState


def generate_section_queries(
    state: SectionWorkerState,
    config: RunnableConfig | None = None,
) -> dict:
    """Generate 2-5 search queries for this section. On follow-up, target gaps."""
    section_task = state.get("section_task") or {}
    section_id = section_task.get("id", "")
    log_node_start("generate_section_queries", config, section_id=section_id)
    query = state.get("query", "") if isinstance(state.get("query"), str) else ""
    section_gaps = state.get("section_gaps") or []
    section_iteration = state.get("section_iteration") or 0

    cfg = get_config(config)
    model_name = cfg.get("section_query_model") or "gpt-4o-mini"
    max_queries = cfg.get("section_queries_per_iteration") or 3

    llm = ChatOpenAI(model=model_name, temperature=0)
    task_str = json.dumps(section_task, indent=2)

    is_followup = section_iteration > 0 and section_gaps
    if is_followup:
        seen_urls = state.get("section_seen_urls") or set()
        seen_list = list(seen_urls)[:30]
        prompt = SECTION_QUERY_FOLLOWUP_PROMPT.format(
            section_task=task_str,
            section_gaps=json.dumps(section_gaps, indent=2),
            seen_urls=", ".join(seen_list) if seen_list else "(none yet)",
        )
    else:
        prompt = SECTION_QUERY_PROMPT.format(
            section_task=task_str,
            query=query,
        )

    log_prompt("generate_section_queries", prompt, model=model_name)
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
        data = {"search_queries": []}

    queries = data.get("search_queries") or []
    if not isinstance(queries, list):
        queries = [str(queries)] if queries else []
    queries = [str(q).strip() for q in queries if q][:max_queries]
    log_decision("generate_section_queries", f"iteration={section_iteration + 1}, queries={len(queries)}", {"queries": queries[:5]})
    log_node_end("generate_section_queries", {"section_queries": queries, "iteration": section_iteration + 1})

    return {
        "section_queries": queries,
        "section_iteration": section_iteration + 1,
    }
