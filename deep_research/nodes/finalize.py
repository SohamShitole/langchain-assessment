"""finalize_messages node - append report to messages."""

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from deep_research.research_logger import log_node_end, log_node_start
from deep_research.state import ResearchState


async def finalize_messages(
    state: ResearchState,
    config: RunnableConfig | None = None,
) -> dict:
    """Append the final report as an assistant message to messages."""
    log_node_start("finalize_messages")
    report = state.get("report_markdown") or ""
    msg = AIMessage(content=report)
    log_node_end("finalize_messages", {"report_chars": len(report)})
    return {"messages": [msg]}
