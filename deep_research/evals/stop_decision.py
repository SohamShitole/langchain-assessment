"""Stop decision eval: did the agent stop appropriately vs loop unnecessarily."""

import json

from deep_research.evals.judge import judge_call

RUBRIC = """Score 0-10: Did the agent stop at the right time?
- Consider: were all critical knowledge gaps addressed before stopping?
- Were iterations proportionate to section count and complexity?
- 10 = stopped at the right time; 0 = stopped too early with critical gaps, or looped excessively."""


def eval_stop_decision(
    research_trace: dict, knowledge_gaps: list[dict]
) -> tuple[float, str]:
    """Check whether the agent stopped appropriately (LLM-as-judge)."""
    trace = research_trace or {}
    sections = trace.get("sections_created", 0)
    if not sections:
        return 0.5, "No section trace data"

    trace_str = json.dumps(trace, default=str, indent=0)[:1500]
    gaps_str = json.dumps(knowledge_gaps[:20], default=str, indent=0)[:1000]
    context = f"RESEARCH TRACE:\n{trace_str}\n\nKNOWLEDGE GAPS (remaining):\n{gaps_str}"
    return judge_call(RUBRIC, context)
