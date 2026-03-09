"""Prompt templates for the research graph."""

CLASSIFY_PROMPT = """You are a research query analyst. Classify the research query by complexity.

Consider:
- simple: one clear topic, straightforward report shape
- moderate: a few subparts, still manageable
- complex: broad comparison, many entities, ambiguity, or likely multi-section decomposition

Respond with JSON: {"complexity": "simple"|"moderate"|"complex", "planner_model": "gpt-4o-mini"|"gpt-4o", "reasoning": "short explanation"}
Use gpt-4o-mini for simple and moderate. Use gpt-4o only for complex queries."""

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

Knowledge gaps / caveats (mention these where evidence is weak):
{knowledge_gaps}

Coverage status: {coverage_status}

Requirements:
- Use inline citations: [1], [2], etc. corresponding to the numbered evidence
- Do not make claims not supported by the evidence
- Mention uncertainty where evidence is weak or incomplete
- Structure: Title, Executive Summary, Main Findings, Detailed Analysis by Section, Caveats/Remaining Gaps, Sources
- Use section titles only in headings (e.g. "## Introduction" or "## Applications and Use Cases"); do NOT include internal IDs like s1, s2, s3
- If coverage_status is insufficient or iteration budget was exhausted, include a clear Caveats section
- End with a Sources section listing each citation with URL and title

Output the report markdown only. Do not wrap in code blocks."""

# Phase 2 prompts

RESEARCH_PLAN_PROMPT = """You are a research planner. The user wants a report on:

{query}

Create a first-class research plan. Do NOT generate search queries yet. Output:

1. objective: The main research objective in one sentence.
2. desired_structure: List of section definitions. Each: {{"id": "s1", "title": "...", "description": "what this section covers"}}
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

ENHANCED_WRITER_PROMPT = """You are a research report writer. Synthesize a grounded, well-structured markdown report.

Report structure (from research plan):
{report_outline}

Section summaries (use these as the backbone):
{section_summaries}

Evidence to cite (ONLY use these - do not make up facts):
{writer_evidence}

Unresolved conflicts or caveats (surface these honestly in the report):
{conflicts_and_caveats}

Requirements:
- Use inline citations: [1], [2], etc. corresponding to the numbered evidence
- Synthesize from section summaries; do not ignore them
- Surface contradictions explicitly - do not silently flatten conflicting evidence
- Prefer primary sources in citations when available
- Structure: Title, Executive Summary, Main Findings, Detailed Analysis by Section, Caveats/Conflicts, Sources
- Use section titles only in headings (e.g. "## Introduction" or "## Applications"); do NOT include internal IDs like s1, s2, s3
- Include a Caveats section for unresolved questions and conflicts
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
- Mention unresolved questions or limitations where relevant
- Do NOT make claims unsupported by the evidence
- Do NOT wrap output in code blocks

Output the section content only (no heading, no title)."""

REPORT_ASSEMBLY_PROMPT = """You are assembling a final research report from pre-written section drafts.

Report structure:
{report_outline}

Pre-written section drafts (each already contains inline citations):
{section_drafts}

Conflicts and caveats to surface:
{conflicts_and_caveats}

Sources list:
{sources_list}

Requirements:
- Produce a complete markdown report with this structure:
  1. Title (# heading)
  2. Executive Summary — synthesize the key takeaways across ALL sections (2-3 paragraphs, with citations)
  3. Main Findings — 5-7 numbered key findings that cut across sections, each with citations
  4. Detailed Analysis by Section — include each section draft under its own ## heading. You may lightly edit for flow, transitions, and consistency, but preserve ALL citations and substantive content. Do NOT cut detail.
  5. Caveats/Conflicts (Unresolved Questions) — surface conflicts, unresolved questions, and limitations from the evidence
  6. Sources — reproduce the sources list provided below
- Preserve ALL inline citations [N] from the section drafts exactly as they appear
- Do NOT invent new claims or citations
- Use section titles only in headings; do NOT include internal IDs like s1, s2, s3
- Do NOT wrap output in code blocks

Output the complete report markdown."""
