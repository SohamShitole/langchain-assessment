"""Section worker subgraph for parallel section research."""

from langgraph.graph import END, START, StateGraph

from deep_research.nodes.section_coverage import section_assess_coverage
from deep_research.nodes.section_normalize import section_normalize
from deep_research.nodes.section_queries import generate_section_queries
from deep_research.nodes.section_search import section_search
from deep_research.nodes.section_summary import generate_section_summary
from deep_research.routing import section_route
from deep_research.state import SectionWorkerState


def create_section_worker_graph():
    """Build the section worker subgraph.

    Flow: generate_section_queries -> section_search -> section_normalize
          -> section_assess_coverage -> [route]
          -> generate_section_summary (if done) OR generate_section_queries (loop)
    """
    builder = StateGraph(SectionWorkerState)

    builder.add_node("generate_section_queries", generate_section_queries)
    builder.add_node("section_search", section_search)
    builder.add_node("section_normalize", section_normalize)
    builder.add_node("section_assess_coverage", section_assess_coverage)
    builder.add_node("generate_section_summary", generate_section_summary)

    builder.add_edge(START, "generate_section_queries")
    builder.add_edge("generate_section_queries", "section_search")
    builder.add_edge("section_search", "section_normalize")
    builder.add_edge("section_normalize", "section_assess_coverage")
    builder.add_conditional_edges(
        "section_assess_coverage",
        section_route,
        {
            "section_complete": "generate_section_summary",
            "section_needs_more": "generate_section_queries",
        },
    )
    builder.add_edge("generate_section_summary", END)

    return builder.compile()
