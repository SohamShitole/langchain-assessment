"""Pydantic data models for Phase 2 research artifacts."""

from pydantic import BaseModel, Field


class SectionTask(BaseModel):
    """Independent section-level research task."""

    id: str = Field(description="Section ID (e.g. s1, s2)")
    title: str = Field(description="Section title")
    goal: str = Field(description="What this section must accomplish")
    key_questions: list[str] = Field(default_factory=list, description="Questions to answer")
    success_criteria: list[str] = Field(default_factory=list, description="Criteria for completion")
    priority: int = Field(default=1, description="1=high, 2=medium, 3=low")
    search_hints: list[str] = Field(default_factory=list, description="Optional search hints")


class SectionResult(BaseModel):
    """Output from a completed section worker."""

    section_id: str = Field(description="Section ID")
    evidence: list[dict] = Field(default_factory=list, description="Evidence items for this section")
    coverage_score: float = Field(default=0.0, description="0-10 coverage score")
    gaps: list[dict] = Field(default_factory=list, description="Identified gaps")
    summary: dict | None = Field(default=None, description="SectionSummary artifact")
    confidence: float = Field(default=0.0, description="0-1 confidence in section quality")


class EnrichedEvidence(BaseModel):
    """Evidence item with richer source quality metadata."""

    url: str = Field(description="Source URL")
    title: str = Field(description="Source title")
    snippet: str = Field(description="Grounded excerpt")
    section_ids: list[str] = Field(default_factory=list, description="Outline section IDs")
    relevance_score: int = Field(description="1-10 relevance")
    credibility: str = Field(default="medium", description="high, medium, or low")
    credibility_score: int = Field(default=5, description="1-10 numeric credibility")
    source_type: str = Field(
        default="unknown",
        description="official|government|press|blog|aggregator|unknown",
    )
    recency: str = Field(default="unknown", description="recent|dated|unknown or date string")
    novelty_flag: bool = Field(default=True, description="Adds new info vs redundant")
    is_primary: bool = Field(default=False, description="Primary source")
    is_redundant: bool = Field(default=False, description="Redundant with other evidence")
    found_by_section_id: str = Field(default="", description="Section worker that found this")
    iteration: int = Field(default=1, description="Iteration found")


class MergedEvidence(BaseModel):
    """Evidence item after global merge with provenance."""

    url: str = Field(description="Source URL")
    title: str = Field(description="Source title")
    snippet: str = Field(description="Content excerpt")
    supporting_sections: list[str] = Field(
        default_factory=list, description="Section IDs this evidence supports"
    )
    cross_cutting: bool = Field(default=False, description="Evidence spans multiple sections")
    evidence_meta: dict = Field(default_factory=dict, description="Original evidence metadata")


class ConflictRecord(BaseModel):
    """Detected contradiction in merged evidence."""

    conflicting_claims: list[str] = Field(
        default_factory=list, description="The conflicting statements"
    )
    source_urls: list[str] = Field(default_factory=list, description="URLs with conflicting info")
    section_ids: list[str] = Field(default_factory=list, description="Affected sections")
    severity: str = Field(default="medium", description="high|medium|low")
    resolved: bool = Field(default=False, description="Whether conflict was resolved")
    resolution_note: str = Field(default="", description="Resolution if resolved")


class SectionSummary(BaseModel):
    """Intermediate summary artifact for a completed section."""

    section_id: str = Field(description="Section ID")
    summary_text: str = Field(description="Brief summary of findings")
    strongest_sources: list[str] = Field(
        default_factory=list, description="URLs of best sources"
    )
    unresolved_questions: list[str] = Field(
        default_factory=list, description="Questions still open"
    )
    confidence: float = Field(default=0.0, description="0-1 confidence")


class ResearchPlan(BaseModel):
    """First-class research plan artifact."""

    objective: str = Field(description="Main research objective")
    desired_structure: list[dict] = Field(
        default_factory=list, description="Desired report structure"
    )
    section_names: list[str] = Field(default_factory=list, description="Section names")
    difficulty_areas: list[str] = Field(
        default_factory=list, description="Likely difficulty areas"
    )
    section_descriptions: list[dict] = Field(
        default_factory=list,
        description="Per-section: what each section must answer",
    )


class ResearchTrace(BaseModel):
    """Per-run observability trace."""

    planner_model_used: str = Field(default="", description="Model used for planning")
    sections_created: int = Field(default=0, description="Number of sections")
    section_names: list[str] = Field(default_factory=list, description="Section names")
    per_section_iterations: dict[str, int] = Field(
        default_factory=dict, description="section_id -> iteration count"
    )
    urls_found: int = Field(default=0, description="Total URLs found")
    urls_deduped: int = Field(default=0, description="URLs deduplicated in merge")
    section_coverage_scores: dict[str, float] = Field(
        default_factory=dict, description="section_id -> coverage score"
    )
    conflicts_detected: int = Field(default=0, description="Number of conflicts found")
    writer_evidence_count: int = Field(default=0, description="Evidence items passed to writer")
