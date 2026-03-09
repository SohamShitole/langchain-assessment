"""finalize_messages node - append report to messages."""

from langchain_core.messages import AIMessage

from deep_research.state import ResearchState


def finalize_messages(state: ResearchState) -> dict:
    """Append the final report as an assistant message to messages."""
    report = state.get("report_markdown") or ""
    msg = AIMessage(content=report)
    return {"messages": [msg]}
