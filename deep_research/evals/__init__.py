"""Phase 2 evaluation modules.

Each eval returns (score: float 0-1, reasoning: str).
Run all via run_evals().
"""

from deep_research.evals.claim_support import eval_claim_support
from deep_research.evals.section_completeness import eval_section_completeness
from deep_research.evals.source_quality import eval_source_quality
from deep_research.evals.conflict_handling import eval_conflict_handling
from deep_research.evals.stop_decision import eval_stop_decision
from deep_research.evals.comparative_breadth import eval_comparative_breadth
from deep_research.evals.factual_accuracy import eval_factual_accuracy
from deep_research.evals.citation_relevance import eval_citation_relevance
from deep_research.evals.synthesis_quality import eval_synthesis_quality
from deep_research.evals.tool_trajectory import eval_tool_trajectory


def run_evals(
    report_markdown: str,
    report_outline: list[dict],
    writer_evidence: list[dict],
    knowledge_gaps: list[dict],
    section_results: list[dict] | None = None,
    research_trace: dict | None = None,
    query: str = "",
) -> dict:
    """Run all applicable evals and return summary."""
    results: dict[str, tuple[float, str]] = {}
    research_trace = research_trace or {}
    section_results = section_results or []

    score, reason = eval_claim_support(report_markdown, writer_evidence)
    results["claim_support"] = (score, reason)

    score, reason = eval_section_completeness(report_markdown, report_outline)
    results["section_completeness"] = (score, reason)

    score, reason = eval_source_quality(writer_evidence)
    results["source_quality"] = (score, reason)

    score, reason = eval_conflict_handling(report_markdown, research_trace=research_trace)
    results["conflict_handling"] = (score, reason)

    score, reason = eval_stop_decision(research_trace, knowledge_gaps)
    results["stop_decision"] = (score, reason)

    score, reason = eval_comparative_breadth(report_markdown, query)
    results["comparative_breadth"] = (score, reason)

    score, reason = eval_factual_accuracy(report_markdown, writer_evidence)
    results["factual_accuracy"] = (score, reason)

    score, reason = eval_citation_relevance(report_markdown, writer_evidence)
    results["citation_relevance"] = (score, reason)

    score, reason = eval_synthesis_quality(report_markdown, query, report_outline)
    results["synthesis_quality"] = (score, reason)

    score, reason = eval_tool_trajectory(research_trace, section_results)
    results["tool_trajectory"] = (score, reason)

    return results
