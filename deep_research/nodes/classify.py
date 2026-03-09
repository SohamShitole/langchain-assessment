"""classify_complexity node - decide query complexity and planner model."""

from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from deep_research.configuration import DEFAULT_PLANNER_COMPLEX_MODEL, DEFAULT_PLANNER_SIMPLE_MODEL, get_config
from deep_research.prompts import CLASSIFY_PROMPT
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
    query = state.get("query") or ""
    cfg = get_config(config)
    model_name = cfg.get("classifier_model") or "gpt-4o-mini"

    llm = ChatOpenAI(model=model_name, temperature=0)
    structured = llm.with_structured_output(ClassifyOutput, method="function_calling")
    result = structured.invoke(
        [{"role": "system", "content": CLASSIFY_PROMPT}, {"role": "user", "content": query}]
    )

    planner = result.planner_model
    if "gpt-4o" in planner.lower() and "mini" not in planner.lower():
        planner = cfg.get("planner_complex_model") or DEFAULT_PLANNER_COMPLEX_MODEL
    else:
        planner = cfg.get("planner_simple_model") or DEFAULT_PLANNER_SIMPLE_MODEL

    complexity = (result.complexity or "moderate").lower()
    if complexity not in ("simple", "moderate", "complex"):
        complexity = "moderate"

    return {
        "complexity": complexity,
        "planner_model": planner,
    }
