"""classify_complexity node - decide query complexity and planner model."""

from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from deep_research.configuration import DEFAULT_PLANNER_COMPLEX_MODEL, DEFAULT_PLANNER_SIMPLE_MODEL, get_config
from deep_research.prompts import CLASSIFY_PROMPT, get_prompt
from deep_research.research_logger import log_decision, log_node_end, log_node_start, log_prompt
from deep_research.state import ResearchState


class ClassifyOutput(BaseModel):
    """Structured output for complexity classification."""

    complexity: str = Field(description="simple, moderate, or complex")
    planner_model: str = Field(description="gpt-4o-mini or gpt-4o")
    reasoning: str = Field(description="Short explanation")


def classify_complexity(
    state: ResearchState,
    config: RunnableConfig | None = None,
) -> dict:
    """Classify query complexity and select planner model."""
    log_node_start("classify_complexity", config)
    query = state.get("query") or ""
    cfg = get_config(config)
    model_name = cfg.get("classifier_model") or "gpt-4o-mini"

    classify_prompt = get_prompt("classify", cfg, CLASSIFY_PROMPT)
    log_prompt("classify_complexity", query, model=model_name, system_content=classify_prompt)
    llm = ChatOpenAI(model=model_name, temperature=0)
    structured = llm.with_structured_output(ClassifyOutput, method="function_calling")
    result = structured.invoke(
        [{"role": "system", "content": classify_prompt}, {"role": "user", "content": query}]
    )

    planner = result.planner_model
    if "gpt-4o" in planner.lower() and "mini" not in planner.lower():
        planner = cfg.get("planner_complex_model") or DEFAULT_PLANNER_COMPLEX_MODEL
    else:
        planner = cfg.get("planner_simple_model") or DEFAULT_PLANNER_SIMPLE_MODEL

    complexity = (result.complexity or "moderate").lower()
    if complexity not in ("simple", "moderate", "complex"):
        complexity = "moderate"

    log_decision("classify_complexity", f"complexity={complexity}, planner={planner}", {"reasoning": getattr(result, "reasoning", "")})
    log_node_end("classify_complexity", {"complexity": complexity, "planner_model": planner})
    return {
        "complexity": complexity,
        "planner_model": planner,
    }
