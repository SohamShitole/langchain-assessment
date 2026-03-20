"""Prompt templates for the research graph."""


def format_report_structure_for_planning(structure: list[str]) -> str:
    """Ordered headings for research_plan / research_plan_edit prompts."""
    if not structure:
        return "(No report headings in config; infer sensible sections from the query.)"
    return "\n".join(f"{i + 1}. {h}" for i, h in enumerate(structure))


def get_prompt(name: str, cfg: dict, fallback: str) -> str:
    """Return override from config if present, otherwise the fallback default prompt."""
    overrides = cfg.get("prompt_overrides") or {}
    return overrides.get(name) or fallback


CLASSIFY_PROMPT = """You are a research query analyst. Classify the research query by complexity.

Consider:
- simple: one clear topic, straightforward report shape
- moderate: a few subparts, still manageable
- complex: broad comparison, many entities, ambiguity, or likely multi-section decomposition

Respond with JSON: {"complexity": "simple"|"moderate"|"complex", "planner_model": "gpt-4o-mini"|"gpt-4o", "reasoning": "short explanation"}
Use gpt-5-nano for simple and moderate. Use gpt-5.2 only for complex queries."""

PLANNER_INITIAL_PROMPT = """You are a research planner. The user wants a report on:

{query}

Your tasks:
1. Define a report outline with sections. Each section: {{"id": "s1", "title": "...", "description": "what this section covers"}}
2. Generate 3-5 search queries to gather information for this report. Be specific and diverse.

Return JSON:
{{
  "report_outline": [{{"id": "s1", "title": "...", "description": "..."}}, ...],
  "search_queries": ["query 1", "query 2", ...]
}}"""

PLANNER_FOLLOWUP_PROMPT = """You are a research planner. The user wants a report on:

{query}

Current report outline:
{report_outline}

Coverage gaps that need more evidence:
{knowledge_gaps}

URLs already seen (do not generate queries that would return these):
{seen_urls}

Generate 2-4 NEW, narrower search queries to fill the critical gaps. Avoid repeating prior query patterns.
Return JSON: {{"search_queries": ["query 1", "query 2", ...]}}"""

NORMALIZE_PROMPT = """Extract structured evidence from these search results for a research report.

Report outline sections: {report_outline}

Search results (raw):
{raw_results}

For each result, output:
- url, title, snippet (best passage), section_ids (which outline sections it supports), relevance_score (1-10), credibility (high/medium/low), iteration (use {iteration})

Discard results with relevance < 5 or that are clearly off-topic.
Return JSON: {{"items": [{{"url": "...", "title": "...", "snippet": "...", "section_ids": ["s1"], "relevance_score": 8, "credibility": "high", "iteration": {iteration}}}, ...]}}"""

COVERAGE_PROMPT = """Assess whether we have enough evidence to write the report.

Report outline:
{report_outline}

Evidence items (count per section):
{evidence_summary}

For each section, score coverage 0-10. Identify knowledge_gaps: sections with score < 6.
Mark gaps as critical if the section is essential to the report's main claim. Mark as optional if it's supplementary.

Return JSON:
{{
  "section_scores": [{{"section_id": "s1", "score": 8, "evidence_count": 5}}, ...],
  "knowledge_gaps": [{{"section_id": "s1", "description": "need more on X", "critical": true}}, ...],
  "coverage_status": "sufficient" | "insufficient",
  "reasoning": "brief explanation"
}}
Set coverage_status to "sufficient" only if there are NO critical gaps."""

WRITER_PROMPT = """You are a research report writer. Write a grounded, well-structured markdown report.

Report outline:
{report_outline}

Evidence to use (ONLY use these - do not make up facts):
{writer_evidence}

Knowledge gaps (for context; do not add a caveats section):
{knowledge_gaps}

Coverage status: {coverage_status}

Conflict resolution guidance (if any — prefer winning claims; note caveats where unresolved):
{conflict_resolutions}

Requirements:
- Use inline citations: [1], [2], etc. corresponding to the numbered evidence
- Do not make claims not supported by the evidence
- Where conflict_resolutions exist, prefer the stated winning_claim and resolution_verdict
- Mention uncertainty where evidence is weak or incomplete
- Structure: {report_structure}
- Use section titles only in headings (e.g. "## Introduction" or "## Applications and Use Cases"); do NOT include internal IDs like s1, s2, s3
- End with a Sources section listing each citation with URL and title

Output the report markdown only. Do not wrap in code blocks."""

# Phase 2 prompts

RESEARCH_PLAN_PROMPT = """You are a research planner. The user wants a report on:

{query}

The final report will use this **ordered top-level outline** (from the configured report preset). You must **cover** these headings with evidence, but `desired_structure` is **not** a copy of that list.

**Report headings (in order):**
{report_structure}

**How to align (read carefully):**
- Each `desired_structure` item is a **research workstream** (parallel search + synthesis). Its **`title` must be a concrete research theme**—e.g. "Tool landscape and vendor comparisons", "Evaluation metrics and benchmarks", "Failure modes and governance"—**not** the report heading repeated or "Abstract (feeds Abstract)". **Forbidden:** titles that are only a preset heading, or the pattern "Heading (feeds Heading)".
- Put mapping to the report in **`description` only**: start with a short line like `Feeds report sections: …` then **3+ specific subtopics, angles, or questions** to investigate. Every description must show real research scope, not a restatement of the heading.
- **Do not** create one shallow row per preset line. Merge related headings into fewer, deeper workstreams where it makes sense. **Skip** dedicated research tasks for: "Title"; "Sources"/"References" (citations come from all streams); "Abstract" (summarize other findings unless the query is meta); "Appendix" unless the query explicitly needs supplementary data. Prefer **roughly 4–8** substantive workstreams for typical presets—not a 1:1 clone of every line.
- If one report heading is huge (e.g. "Results & Analysis"), split into **multiple themed** workstreams; say in each description which part of the report it supplies.
- Keep `section_names` equal to the `desired_structure` titles in order (same strings).

Create a first-class research plan. Do NOT generate search queries yet. Output:

1. objective: The main research objective in one sentence.
2. desired_structure: List of section definitions. Each: {{"id": "s1", "title": "...", "description": "what this section covers; which report heading(s) it feeds; subtopics to research"}}
3. section_names: List of section titles.
4. difficulty_areas: List of topics that may be hard to research (e.g. proprietary data, conflicting sources).
5. section_descriptions: For each section, what specific questions it must answer. List of {{"section_id": "s1", "must_answer": ["question 1", "question 2"]}}

Return JSON:
{{
  "objective": "...",
  "desired_structure": [{{"id": "s1", "title": "...", "description": "..."}}, ...],
  "section_names": ["...", ...],
  "difficulty_areas": ["...", ...],
  "section_descriptions": [{{"section_id": "s1", "must_answer": ["..."]}}, ...]
}}"""

RESEARCH_PLAN_EDIT_PROMPT = """You are a research planner. The user originally asked for a report on:

**Original query:** {query}

The final report must still follow this **ordered outline** (report preset). Revise the plan so `desired_structure` remains **themed research workstreams** (concrete titles), **not** a 1:1 mirror of every heading and **not** titles like "X (feeds X)". Map sections to headings **inside each description** (`Feeds report sections: …` plus subtopics). Merge or drop hollow tasks for Abstract, References, Title, Appendix unless the user or query demands them.

**Report headings (in order):**
{report_structure}

We proposed this research plan:

**Current plan:**
{current_plan}

The user requested changes:

**User feedback:** {feedback}

Your task: Interpret the user's feedback in the context of their original query. Understand what they want changed (e.g. focus on different tools, add a section, remove a topic, compare specific things) and revise the plan accordingly. The revised plan must still align with the original query's intent; do not replace the topic with something unrelated—incorporate the user's edits so the plan better matches what they asked for. Preserve alignment with the report headings above unless the user explicitly asks to ignore a part of the outline.

Output a revised research plan in the same JSON format:
{{
  "objective": "...",
  "desired_structure": [{{"id": "s1", "title": "...", "description": "..."}}, ...],
  "section_names": ["...", ...],
  "difficulty_areas": ["...", ...],
  "section_descriptions": [{{"section_id": "s1", "must_answer": ["..."]}}, ...]
}}

Return only the JSON. Do NOT generate search queries."""

DECOMPOSE_PROMPT = """You are a research decomposer. Convert the research plan into independent section tasks.

Research plan:
{research_plan}

For each section in desired_structure, create a SectionTask:
- id: section id (e.g. s1, s2)
- title: section title
- goal: one-sentence goal for this section
- key_questions: 2-4 specific questions this section must answer (from section_descriptions if provided)
- success_criteria: 2-3 criteria that indicate the section is complete (e.g. "Has data from at least 2 sources")
- priority: 1=high (essential), 2=medium, 3=low
- search_hints: optional keywords or search phrases for this section

Return JSON:
{{
  "section_tasks": [
    {{"id": "s1", "title": "...", "goal": "...", "key_questions": [...], "success_criteria": [...], "priority": 1, "search_hints": [...]}},
    ...
  ]
}}"""

SECTION_QUERY_PROMPT = """You are a section research assistant. Generate search queries for ONE section.

Section task:
{section_task}

Main research query: {query}

Generate 2-5 search queries tailored to this section's goal and key questions. Be specific and diverse.
Do not repeat queries. Use search_hints if provided.

Return JSON: {{"search_queries": ["query 1", "query 2", ...]}}"""

SECTION_QUERY_FOLLOWUP_PROMPT = """You are a section research assistant. Generate follow-up search queries to fill gaps.

Section task:
{section_task}

Identified gaps:
{section_gaps}

URLs already seen for this section (avoid):
{seen_urls}

Generate 2-4 NEW, narrower search queries to address the gaps. Avoid repeating prior query patterns.

Return JSON: {{"search_queries": ["query 1", "query 2", ...]}}"""

SECTION_NORMALIZE_PROMPT = """Extract structured evidence from search results with rich source quality metadata.

Section: {section_id} - {section_goal}

Search results (raw):
{raw_results}

For each result output:
- url, title, snippet (best passage), relevance_score (1-10)
- credibility: high/medium/low
- credibility_score: 1-10 numeric
- source_type: official|government|press|blog|aggregator|unknown (official=company/official site, government=gov/edu, press=major news, blog=technical/company blog, aggregator=summary/roundup, unknown)
- recency: recent|dated|unknown (or date if known)
- novelty_flag: true if adds new info, false if redundant
- is_primary: true if primary source (original data/statements), false if secondary
- is_redundant: true if largely repeats other evidence

Discard results with relevance_score < 5 or off-topic.
Return JSON: {{"items": [{{"url": "...", "title": "...", "snippet": "...", "relevance_score": 8, "credibility": "high", "credibility_score": 8, "source_type": "press", "recency": "recent", "novelty_flag": true, "is_primary": false, "is_redundant": false}}, ...]}}"""

SECTION_COVERAGE_PROMPT = """Assess whether this section has enough evidence.

Section task:
{section_task}

Success criteria: {success_criteria}

Evidence found ({count} items): {evidence_summary}

Score coverage 0-10. List any gaps. Decide: section_complete or section_needs_more.
Set section_complete only if success criteria are met and score >= 6.

Return JSON:
{{
  "coverage_score": 7,
  "gaps": [{{"description": "need more on X", "critical": true}}, ...],
  "section_complete": true | false,
  "reasoning": "brief explanation"
}}"""

SECTION_SUMMARY_PROMPT = """Create a rich section summary artifact.

Section: {section_id} - {section_title}
Goal: {section_goal}

Evidence found: {evidence_count} items

Top evidence snippets:
{top_evidence}

Write:
1. summary_text: 4-6 sentences summarizing key findings for this section. Include 1-2 illustrative examples or concrete findings when available. Elaborate enough that the writer has a strong backbone to expand from.
2. strongest_sources: list of 2-5 URLs that are the best sources
3. unresolved_questions: list of open questions or gaps (if any)
4. confidence: 0-1 score for how confident we are in this section

Return JSON:
{{
  "summary_text": "...",
  "strongest_sources": ["url1", "url2"],
  "unresolved_questions": ["...", ...],
  "confidence": 0.85
}}"""

CONFLICT_DETECT_PROMPT = """Analyze merged evidence for conflicting claims.

Merged evidence summary (per section):
{merged_evidence_summary}

Look for conflicts in:
- Dates, numbers, release timelines
- Strategy interpretations
- Conflicting expert opinions
- Contradictory facts

For each conflict found, output:
- conflicting_claims: the specific contradictory statements
- source_urls: URLs with conflicting info
- section_ids: which sections are affected
- severity: high|medium|low

Return JSON:
{{
  "conflicts": [
    {{
      "conflicting_claims": ["claim A", "claim B"],
      "source_urls": ["url1", "url2"],
      "section_ids": ["s1", "s2"],
      "severity": "high"
    }}
  ],
  "conflict_resolution_needed": true | false,
  "reasoning": "brief explanation"
}}
Set conflict_resolution_needed to true only if there are high or medium severity conflicts that affect the report's main claims."""

CONFLICT_RESOLVE_PROMPT = """Generate targeted search queries to resolve evidence conflicts.

Conflicts:
{conflicts}

Generate 2-4 disambiguation queries that prioritize primary sources (official sites, original data).
Queries should help find authoritative information to resolve the contradictions.

Return JSON: {{"search_queries": ["query 1", "query 2", ...]}}"""

CONFLICT_ADJUDICATE_PROMPT = """You are a research conflict adjudicator. Determine which claims are best supported.

Conflicts (contradictory claims to resolve):
{conflicts}

Original evidence (snippets and metadata for the conflicting sources — use credibility_score, source_type when present):
{original_evidence}

Additional evidence gathered to resolve them (disambiguation search):
{new_evidence}

For each conflict:
1. Weigh source credibility: use credibility_score and source_type when available (official > government > press > blog > aggregator).
2. Weigh recency (prefer recent over dated) and primary-source status (prefer primary over secondary).
3. Use both original and new evidence to decide which claim is better supported, or mark unresolved if evidence is inconclusive.
4. Output a clear resolution_verdict and winning_claim so the report writer can prefer the winning claim and add caveats for unresolved conflicts.

Return JSON:
{{
  "resolved_conflicts": [
    {{
      "conflicting_claims": ["claim A", "claim B"],
      "source_urls": ["url1", "url2"],
      "section_ids": ["s1"],
      "severity": "high",
      "resolved": true,
      "resolution_verdict": "Claim A is better supported because...",
      "winning_claim": "the specific claim text",
      "confidence": 0.85
    }}
  ]
}}"""

ENHANCED_WRITER_PROMPT = """You are a research report writer. Synthesize a grounded, well-structured markdown report.

Report structure (from research plan):
{report_outline}

Section summaries (use these as the backbone):
{section_summaries}

Evidence to cite (ONLY use these - do not make up facts):
{writer_evidence}

Conflict resolution guidance (from adjudication — prefer winning claims and note caveats where relevant):
{conflict_resolutions}

Requirements:
- Use inline citations: [1], [2], etc. corresponding to the numbered evidence
- Synthesize from section summaries; do not ignore them
- Where conflict_resolutions exist, prefer the stated winning_claim and resolution_verdict; surface remaining uncertainty only when conflict remains unresolved
- Surface contradictions explicitly in the narrative where relevant - do not silently flatten conflicting evidence
- Prefer primary sources in citations when available
- Structure: {report_structure}
- Use section titles only in headings (e.g. "## Introduction" or "## Applications"); do NOT include internal IDs like s1, s2, s3
- End with a Sources section listing each citation with URL and title

Output the report markdown only. Do not wrap in code blocks."""

# ── Section-by-section writing prompts (avoids context-window overflow) ──

SECTION_DRAFT_PROMPT = """You are writing ONE section of a research report. Write a detailed, well-cited section.

Section title: {section_title}
Section description: {section_description}

Research summary for this section:
{section_summary}

Unresolved questions: {unresolved_questions}

Evidence ({evidence_count} items — use citation_index for inline citations like [N]):
{section_evidence}

Requirements:
- Write detailed, thorough markdown content for this section (do NOT include a section heading — it will be added later)
- Use inline citations [N] where N is the citation_index from the evidence
- Explain concepts clearly; assume a reader who is informed but not an expert in this exact topic
- Include concrete examples, data points, or case studies from the evidence when available
- Explain WHY things matter, not just WHAT they are
- Do NOT make claims unsupported by the evidence
- Do NOT wrap output in code blocks

Output the section content only (no heading, no title)."""

REPORT_ASSEMBLY_PROMPT = """You are assembling a final research report from pre-written section drafts.

Report structure:
{report_outline}

Pre-written section drafts (each already contains inline citations):
{section_drafts}

Sources list:
{sources_list}

Conflict resolution guidance (prefer winning claims; add brief caveats where conflicts remained unresolved):
{conflict_resolutions}

Requirements:
- Produce a complete markdown report with this structure: {report_structure}
- Preserve ALL inline citations [N] from the section drafts exactly as they appear
- Where conflict_resolutions exist, if the narrative contradicts a stated winning_claim, add a short caveat or align with the resolution_verdict
- Do NOT invent new claims or citations
- Use section titles only in headings; do NOT include internal IDs like s1, s2, s3
- Do NOT wrap output in code blocks

Output the complete report markdown."""
