# Design: Deep Research Agent

This document is the plain-English version of how this system works, how the design evolved, and where the code is today. It is intentionally more honest than polished. Some parts are clean and working well. Some parts are still transitional. That is useful context, not a problem to hide.

---

## What This Repo Actually Is

At a high level, this repository is a CLI-first research agent that takes a user question, searches the web, gathers evidence, and writes a grounded markdown report.

The important pieces are:

- `run.py` is the entry point. It loads config, runs the graph, streams progress, handles plan approval, writes the report, optionally writes logs and traces, and can run evals.
- `deep_research/graph.py` defines the main LangGraph workflow. The default path is the newer section-oriented flow. The older single-agent loop is still there as a legacy path.
- `deep_research/section_graph.py` defines the small worker graph used for section-level research.
- `deep_research/nodes/` contains the actual behavior: ingest, classify, planning, search, normalization, coverage checks, merge, conflict handling, writer-context prep, section drafting, report writing, and finalization.
- `deep_research/configuration.py` turns `config.yaml` into runtime settings and provides defaults; it also loads report structure from presets or an explicit list.
- `report_presets.yaml` defines numbered report layouts (e.g. Standard, Brief, Academic, OpenAI-style, Consulting); config can reference a preset by number instead of listing sections.
- `deep_research/prompts.py` holds the system prompts, with support for overriding them from config.
- `deep_research/progress.py` is the small UX layer that turns graph events into human-readable progress messages.
- `deep_research/research_logger.py` writes process logs for debugging.
- `deep_research/evals/` contains the post-run evaluation suite.
- `reports/` stores generated reports, optional logs, and optional trace JSON files.
- `tests/` contains mostly graph and routing smoke tests, plus a few end-to-end checks.

So this is not just "an agent prompt." It is a graph-based research system with state, routing, logging, and evaluation around it.

---

## What We Are Trying To Achieve

The goal sounds simple:

**take a user question, gather information from the web, and write a report that is actually supported by evidence.**

The hard part is not generating text. The hard part is making the system:

- broad enough to find useful information
- selective enough to ignore noisy results
- explicit enough to know when research is incomplete
- constrained enough to stay inside budget and context limits
- inspectable enough to debug when the output is wrong

That is why this became a graph with state instead of a single prompt or a simple linear chain.

---

## How The Design Evolved

This is the part that mattered most during design. The final shape did not appear all at once. It changed because earlier ideas were too weak once I thought through failure modes.

### 1. Initial idea: simple sequential pipeline

The first idea was the obvious one:

query -> web search -> summarize results -> write report

This would have been easy to implement and probably fine for narrow, easy topics.

The problem was that it only searches once. If the first search is weak, the whole report is weak. The system has no real way to notice missing coverage, no real way to recover, and no real way to say "I do not know enough yet."

That pushed the design away from a one-pass pipeline and toward an iterative one.

### 2. Introducing an iterative research loop

The next version became:

query
-> generate search queries
-> search
-> extract evidence
-> assess coverage
-> repeat if needed
-> write report

This was much better. It allowed follow-up search rounds, better targeting after weak early results, and a more realistic path to covering a topic.

But the early stopping rule was still too fuzzy. "Stop when evidence seems sufficient" sounds reasonable until you actually need consistent behavior. In practice, vague stopping logic causes two bad outcomes: stopping too early or looping too long.

That is what led to explicit coverage assessment.

### 3. Evidence normalization

At one point I was tempted to pass raw search results directly into the writer. That looked simpler on paper.

It was the wrong move. Search results are noisy: duplicate URLs, shallow snippets, irrelevant hits, mixed source quality, conflicting details, and inconsistent formatting. Asking the writer model to clean all of that up at generation time is expensive and unreliable.

So the design gained a dedicated normalization layer. That layer filters weak results, deduplicates URLs, scores relevance, and maps evidence to sections. This turned out to matter more than I first expected. Cleaner evidence improved report quality more than many prompt tweaks did.

### 4. Token budget problems

Another design turning point was context size. If you run multiple iterations, or multiple section workers, the amount of collected evidence grows fast. Passing all of it into the writer sounds thorough, but it actually hurts quality once the context becomes noisy or too large.

So the design added a writer-context preparation step that ranks evidence, ensures coverage across sections, removes redundancy, and caps the final evidence set before writing.

This is one of those architecture decisions that matters more than model size. Better input selection usually beats blindly sending more context.

### 5. Model routing strategy

The early idea of using one model for every task also fell apart quickly. Many parts of the pipeline are simple and do not need a strong model. Using the most expensive model everywhere wastes budget without improving the final result much.

That led to role-based routing:

- cheap model for classification and lightweight normalization
- medium model for planning
- stronger model for complex planning and final writing

The current configuration aims in that direction even though the exact model names are still in flux.

### 6. Explainability concerns

Once the system stopped being linear, explainability became necessary. Without it, debugging is guesswork. If the report is wrong, you need to know:

- why the agent stopped
- which evidence supported which section
- where gaps remained
- whether a conflict was detected and what happened next

That is why the design picked up trace data, evidence mapping, progress messages, logs, and post-run evals.

### 7. Evaluation strategy

The first evaluation ideas were too shallow. "Does the report have citations?" and "Does it list sources?" are useful formatting checks, but they do not tell you whether the report is actually faithful to evidence.

So the evaluation plan expanded toward things like:

- claim support
- factual accuracy against evidence
- section completeness
- comparative balance
- stop decision quality
- tool trajectory quality
- conflict handling

The main lesson here was that formatting quality is not the same thing as factual support.

### 8. Multi-agent architecture

After the single-agent loop looked viable, I explored splitting the work by section. That made sense for broad topics because different parts of a report often need different search paths.

This improved modularity and coverage, but it also increased complexity. Now there is merging, cross-section deduplication, conflict handling, and more room for state bugs.

That is why the recommended progression became:

- Phase 1: reliable single-agent iterative loop
- Phase 2: parallel section workers
- Phase 3: deeper human-in-the-loop workflows

This repo now mostly lives in Phase 2, but the Phase 1 path is still present and useful as a simpler mental model.

### 9. Human-in-the-loop decisions

I considered putting user approval into the flow earlier, then postponed it, then brought back a targeted version of it.

The reason is simple: human review is valuable, but pause/resume logic adds complexity. It is not free. The compromise that made sense was to keep the automated research loop intact, but pause after the plan so the user can confirm scope before expensive search starts.

That gave the user leverage where it matters most, without turning the whole system into an interactive workflow engine.

---

## Biggest Lessons From The Design Process

1. Research quality depends more on architecture than model size.
2. Evidence normalization is critical.
3. Explicit stopping logic is necessary.
4. Explainability is essential for debugging.
5. Start simple, then scale.

Those lessons are not abstract. They directly shaped the code that exists in this repo now.

---

## Why LangGraph Was The Right Fit

This system has routing, loops, shared state, and optional interruption. That is exactly the kind of workload where a graph makes more sense than a plain chain.

The important benefit is not just "multiple nodes." The real benefit is that the graph makes control flow explicit:

- when to loop
- when to stop
- when to fan out into section workers
- when to merge
- when to do conflict follow-up
- when to pause for plan approval

This also keeps the behavior inspectable. The routing is mostly rule-based, which is good. I do not want a language model deciding graph control flow in a completely opaque way.

---

## The Current Architecture In Practice

Today there are really two workflows in the codebase.

### Phase 1: legacy single-agent loop

This is the original iterative design:

ingest -> classify -> plan queries -> search -> normalize -> assess coverage -> either loop or write

This path still exists in `deep_research/graph.py`. It is simpler, easier to reason about, and still useful as the cleanest expression of the original architecture.

### Phase 2: current default orchestrated flow

This is the main path used by `run.py` today:

ingest
-> classify complexity
-> create research plan
-> decompose into sections
-> run parallel section workers
-> merge section evidence
-> detect global gaps and conflicts
-> optionally run conflict-resolution research
-> prepare writer context
-> write section drafts
-> assemble final report
-> append report to messages

This phase is more scalable for broad topics because each section can do its own mini research loop instead of forcing one planner to cover everything at once.

---

## Report Structure And Presets

The final report is built from an ordered list of top-level section names (e.g. Title, Executive Summary, Main Findings, …). That list drives decomposition, section workers, and assembly.

Two ways to define it:

1. **Preset number** — In `config.yaml`, set `report.preset` to an integer (1–10). The structure is looked up from `report_presets.yaml`, which lives next to `config.yaml`. This keeps config short and lets you switch layouts (e.g. from Standard to Consulting) by changing one number.
2. **Explicit structure** — Under `report.structure` in config, provide a full list of section names. If both preset and structure are set, the explicit list wins.

Presets are defined in `report_presets.yaml`. The file includes generic layouts (Standard, Brief, Academic, Comparative, Investigative) and industry-style ones aligned with common practice: OpenAI Deep Research–style (data-driven, citations, limitations), Perplexity-style (BLUF, answer first then evidence), Consulting (McKinsey/BCG situation–complication–resolution), IEEE/technical report, and LangChain-style documentation (overview, concepts, how-to, examples). Adding or editing presets there does not require code changes; only the config reference (preset number or structure list) needs to stay valid.

---

## Section Workers: Why They Exist

The section worker is a small repeated pattern:

generate section queries
-> search
-> normalize
-> assess section coverage
-> loop if needed
-> summarize section

This is the design choice that turns a general "research agent" into something closer to a report-writing system. Reports are naturally sectional. Researching by section lets the system ask narrower questions, collect more targeted evidence, and avoid one monolithic search strategy.

That said, this is also where complexity grows fastest. Once sections run in parallel, merging and reconciliation matter much more.

---

## State: Why It Has So Many Fields

The assignment required a `messages` field, but the graph needs much more than that.

The state has to remember:

- the normalized user query
- query complexity
- the report outline
- generated search queries
- raw search results
- normalized evidence
- seen URLs for deduplication
- coverage status and knowledge gaps
- iteration counts and limits
- writer-ready evidence subset
- final report markdown and sources
- section tasks, section results, merged evidence, conflicts, and trace metadata for Phase 2

This may look heavy, but it is the right kind of complexity. Most of it exists so the agent can make explicit decisions rather than silently guessing.

---

## Search, Evidence, And Writer Preparation

The current system supports multiple search providers, including Gensee, Gensee Deep Search, Tavily, and Exa. The important architectural point is not the provider list by itself. The important point is that search is treated as a replaceable layer, while the rest of the pipeline expects a common evidence shape.

That lets the graph stay mostly stable even when provider behavior changes.

The process is roughly:

1. search returns raw results
2. normalization turns them into structured evidence
3. deduplication reduces overlap
4. evidence is mapped to sections
5. top evidence is selected for the writer
6. full-page enrichment can fetch more content for those selected URLs

This is one of the strongest parts of the architecture. The writer is deliberately protected from raw search noise.

---

## Stopping Logic And Coverage

One of the biggest improvements over the earliest design was moving from vague stopping logic to explicit coverage checks.

In Phase 1, the router decides whether to loop again or move to writing based on coverage and remaining iteration budget.

In Phase 2, each section worker has its own loop, and then there is a second higher-level decision about whether global conflicts justify extra research before writing.

This is important because "search until it feels done" is not a real system design. Coverage assessment is what makes the loop usable.

---

## Model Routing

The intended routing strategy is straightforward:

- cheap models for simple classification and lightweight checks
- medium models for planning
- strong models for hard synthesis and final writing

This is the right design choice for cost and latency. Not every step deserves the strongest model.

One honest caveat from the current code: the model-routing idea is better than the current implementation details. In `config.yaml`, the planner keys are named `planner` and `planner_strong`, but `deep_research/configuration.py` currently reads `planner_simple` and `planner_complex`. That means planner overrides in config are not fully aligned with the loader right now.

So the architecture is correct, but one part of the configuration plumbing still needs cleanup.

---

## Explainability And Observability

This became much more important as the system evolved.

The repo now has several explainability layers:

- streamed progress updates so the user can see what stage is running
- plan approval before expensive research starts
- process logging for prompts, decisions, and routing
- research trace data in state
- saved trace files on demand
- post-run evals
- source injection safeguards so the final report actually shows the evidence list

This makes the system much more debuggable than a plain "prompt in, report out" workflow.

One practical example is the source-list issue. In some runs, especially around checkpointing and resume, the written report could end up with an empty Sources section even when the state had evidence. The system now repairs that after generation by rebuilding the Sources section from state when needed. It is not elegant, but it is pragmatic and correct.

---

## Human Approval, But In A Focused Place

The current human-in-the-loop feature is intentionally narrow.

The graph pauses after `create_research_plan`. The user can:

- approve the plan
- edit the plan
- cancel the run

That is a good compromise. It gives control over scope without making the whole workflow depend on constant user supervision.

The edit path is also better than a naive replan. Instead of just appending feedback to the query, the system passes the original query, the current plan, and the user feedback together so the revised plan stays grounded in the original request.

For non-interactive runs, `--auto` skips this pause entirely.

---

## Evaluation

The repo now has a real evaluation layer, which is a meaningful improvement over the earlier design.

The eval suite covers:

- claim support
- factual accuracy
- citation relevance
- source quality
- section completeness
- comparative breadth
- synthesis quality
- conflict handling
- stop decision quality
- tool trajectory quality

These evals are useful because they judge more than formatting. They try to evaluate whether the report is actually supported and whether the research process behaved reasonably.

The limitation is that they are still mostly LLM-as-judge checks. That makes them helpful for inspection and benchmarking, but not perfect as hard regression tests.

---

## What Works Well Right Now

- The graph structure is a good fit for iterative research and routing.
- Separating planning, search, normalization, coverage, and writing keeps the system understandable.
- Evidence curation before writing improves report quality a lot.
- Section workers make broad topics more manageable.
- Progress streaming and plan approval make the CLI feel much more usable.
- The codebase already has logging, traces, and evals, which makes debugging far easier than in an opaque agent design.
- Report structure is configurable via numbered presets (`report_presets.yaml`) or an explicit section list, including industry-style layouts (OpenAI, Perplexity, consulting, IEEE, docs).

---

## Where The Code Still Falls Short Of The Design

The broad architecture is solid, but a few details are still rough.

- `config.yaml` and `configuration.py` are not fully aligned for planner model names, so some planner config overrides likely do not work as intended.
- `dispatch_sections()` currently hardcodes `6` parallel sections instead of using the configurable parallelism setting.
- Section summaries are weaker than they should be. The current summary node mainly gets section title, goal, and evidence count, not the full evidence body, so summary quality is likely capped.
- Conflict resolution exists, but it is still fairly shallow. It adds more research, but it does not yet feel like a fully mature adjudication layer.
- Deduplication is mostly URL-string-based. That helps, but it is not the same as canonicalization or semantic duplicate detection.
- The README still describes the project mostly as a simpler single-agent workflow, while the actual default runtime is now the section-oriented Phase 2 path.
- Tests exist, but they are still heavier on graph shape and smoke coverage than on deep node correctness and grounding quality.

I want this section in the design doc because it is easy for a design writeup to become too idealized. The implementation is good, but it is not finished.

---

## Future Direction

The clean roadmap still looks like this:

### Phase 1

Make the single-agent iterative loop reliable.

### Phase 2

Use parallel section workers for broader and more modular research.

### Phase 3

Add deeper human-in-the-loop workflows where they truly help, not everywhere by default.

Beyond that, the most useful next improvements would probably be:

- better conflict adjudication
- stronger section-summary grounding
- config cleanup
- richer source filtering
- caching
- stronger regression-style evaluation

---

## Future Scope 🚀

### Priority 2 — High-Impact Improvements

**5. Caching Layer**

- **What:** Cache search results by query hash + provider. Across runs, the same sub-queries often recur (especially for follow-up research).
- **Why:** Saves API cost and latency. Also enables offline debugging of the pipeline without burning credits.
- **How:** Simple shelve / sqlite cache keyed on `(provider, query_hash, search_depth)` with TTL-based expiry.

**6. Semantic Deduplication**

- **What:** Current dedup is URL-string-based. Two different URLs can contain the same evidence, and the same URL with trailing slashes or UTM params is treated as different.
- **Upgrade to:** URL canonicalization (strip params, normalize scheme) + optional embedding-based semantic similarity check on snippets above a threshold.

**7. Streaming Output / Progressive Report**

- **What:** Right now the report appears all at once at the end. For long research runs (5+ minutes), stream section drafts as they complete.
- **Why:** Dramatically better UX. Users see progress and can cancel early if the direction is wrong.

**8. Retry & Error Handling per Node**

- **What:** If a search provider returns a 429 or 500, the entire graph fails. Add per-node retry with exponential backoff, and fallback to alternate search providers.
- **Why:** Production resilience. Search APIs are flaky.

**9. Multi-Provider Search Fusion**

- **What:** Use 2+ search providers per query and merge results (reciprocal rank fusion or similar). Different providers have different coverage biases.
- **Why:** Significantly improves recall and reduces provider-specific blind spots.

**10. Stronger Test Coverage**

Currently there's only 1 test file (`test_graph.py`, 239 lines). Add:

- Unit tests per node — test each node function in isolation with mocked LLM calls
- Eval regression tests — golden report + eval scores checked against thresholds
- Config validation tests — ensure all config paths produce valid Configuration objects
- Edge case tests — empty search results, LLM refusals, malformed JSON responses

### Priority 3 — If You Had More Time (Stretch Goals)

These are features that would make this genuinely competitive with commercial deep research tools.

**11. Persistent Vector Store for Evidence**

Store all evidence across runs in a vector DB (ChromaDB, Qdrant, or pgvector). Enable:

- "What have I already researched about X?"
- Cross-run knowledge accumulation
- Semantic retrieval of past evidence for new queries

**12. Multi-Modal Sources**

Add support for:

- PDF extraction — academic papers, whitepapers
- YouTube transcript search — talks, interviews
- GitHub code search — for technical topics
- ArXiv API — first-class academic source

**13. Interactive Report Editing**

After the report is generated, let the user interactively:

- Ask follow-up questions about specific sections
- Request deeper research on a section
- Edit section content and regenerate with new evidence

This is essentially Phase 3 (deeper HITL) from your roadmap.

**14. Cost Tracking & Budget Controls**

Track and display:

- Total tokens used (input/output per model)
- Total search API calls and credits
- Estimated cost per run
- Hard budget caps that stop the graph when exceeded

**15. Async / Parallel Node Execution**

Section workers already run conceptually in parallel, but within each section worker, the search → normalize → assess loop is sequential. For broad sections, run multiple search queries concurrently using asyncio or LangGraph's native async support.

**16. Web UI / API Mode**

Wrap `run.py` in a FastAPI server with:

- WebSocket for streaming progress
- REST endpoint for submitting queries
- Simple React frontend showing plan → progress → report
- Report history and re-run capability

**17. Source Credibility Database**

Build a lightweight credibility index for domains:

- Known official/government domains → high credibility
- Known content farms / SEO spam → low credibility

Use this to weight evidence during writer-context preparation, not just as metadata.

**18. Comparative Analysis Engine**

For queries classified as "comparative" (e.g., "LangGraph vs CrewAI"):

- Enforce balanced evidence collection per subject
- Auto-generate comparison tables
- Flag when one side has significantly more/better sources

**19. Citation Verification Loop**

After the report is written, run a verification pass:

- Check that each [N] citation actually matches the evidence it's attributed to
- Flag hallucinated citations (claims attributed to sources that don't support them)
- Regenerate problem sections if citation accuracy is below threshold

**20. Export Formats**

Beyond Markdown, support:

- PDF (via pandoc or weasyprint)
- HTML (styled, with collapsible sources)
- Google Docs (via API)
- Notion (via API)

---

## Summary

This project started from a simple "search once and summarize" idea, but that design was too brittle for serious research. The system gradually evolved toward iterative search, explicit coverage checks, evidence normalization, writer-context curation, model routing, explainability, and finally section-level orchestration.

The current codebase reflects that evolution. `run.py` drives a LangGraph workflow that defaults to a Phase 2 section-based architecture, while keeping the older Phase 1 loop as a simpler legacy path. The most important architectural lessons were that evidence quality matters more than raw volume, stopping logic must be explicit, and observability is essential if the reports are meant to be trusted.

The design is in a good place conceptually. The biggest remaining work is not inventing a new architecture. It is tightening the implementation so the config, summaries, conflict handling, docs, and tests fully catch up to the design.
