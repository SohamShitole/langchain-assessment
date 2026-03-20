# Design: Deep Research Agent

This document is the plain-English version of how this system works, how the design evolved, and where the code is today. It is intentionally more honest than polished. Some parts are clean and working well. Some parts are still transitional. That is useful context, not a problem to hide.

---

## What This Repo Actually Is

At a high level, this repository is a CLI-first research agent that takes a user question, searches the web, gathers evidence, and writes a grounded markdown report.

The important pieces are:

- `run.py` is the primary CLI entry point. It loads config (with optional research-mode overlay), runs the graph, streams progress, handles plan approval, writes the report, optionally writes logs and traces, and can run evals.
- `gradio_app.py` is an optional web UI that drives the same graph (progress, plan approval, report download, evals).
- `deep_research/graph.py` defines the main LangGraph workflow. The default path is the newer section-oriented flow. The older single-agent loop is still there as a legacy path.
- `deep_research/section_graph.py` defines the small worker graph used for section-level research.
- `deep_research/nodes/` contains the actual behavior: ingest, classify, planning, search, normalization, coverage checks, merge, conflict handling, writer-context prep, section drafting, report writing, and finalization.
- `deep_research/configuration.py` turns `config.yaml` into runtime settings and provides defaults; it also loads report structure from presets or an explicit list. For `--research-mode basic` or `advanced`, it merges `config_research_basic.yaml` or `config_research_advanced.yaml` over the base file (shallow per-section overrides) so depth/cost knobs can vary without duplicating the whole config.
- `deep_research/cache.py` implements the SQLite TTL cache for search responses and full-page extraction; toggles and paths live under `cache:` in config.
- `report_presets.yaml` defines numbered report layouts (e.g. Standard, Brief, Academic, OpenAI-style, Consulting); config can reference a preset by number instead of listing sections.
- `deep_research/prompts.py` holds the system prompts, with support for overriding them from config.
- `deep_research/progress.py` is the small UX layer that turns graph events into human-readable progress messages.
- `deep_research/research_logger.py` writes process logs for debugging.
- `deep_research/evals/` contains the post-run evaluation suite.
- `reports/` stores generated reports, optional logs, and optional trace JSON files.
- `tests/` contains graph and routing tests (`test_graph.py`), plus cache integration tests (`test_cache_integration.py`).

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

**Update (current tree):** `config.yaml` under `models:` uses **`planner_simple`** and **`planner_complex`**, which match `_YAML_TO_FLAT` in `deep_research/configuration.py` (they map to `planner_simple_model` / `planner_complex_model` for `get_config()`). The older mismatch (`planner` / `planner_strong` in YAML vs `planner_simple` / `planner_complex` in code) has been **resolved**; if you still see those old key names in a fork or external preset, add aliases in `_YAML_TO_FLAT` or rename the YAML keys.

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

## Evaluation Restructure: How We Got Here

This section documents a later pass on the evaluation layer: what we changed, the iterative reasoning, why we chose this approach, and what we explicitly decided not to do.

### Where we started

Evals originally ran only in `run.py` when you passed `--eval`, after the graph had already finished. They produced a single JSON file (scores + reasoning per eval) and some console output. Nothing in the graph read those scores. So evals were **monitoring only** — useful for "did this run go well?" but not for "should we loop again or do more research?"

Two questions came up:

1. **Should any eval drive a decision inside the graph?**  
   If we only ever run evals after the fact, we can notice that research was thin or that we stopped too early, but we cannot correct for it in the same run. So we considered promoting one eval into a **decision gate**: run it inside the graph and use the result to route (e.g. "research sufficient → write" vs "research insufficient → do one more targeted pass").

2. **Where should section completeness live?**  
   We have a natural moment after section drafts are written but before the final report is assembled. One option was to run section completeness there as a graph node, so we could (in theory) rewrite weak sections. The other was to keep it with the other evals in `run.py`, so we only ever score the **final** report against the outline.

### Iterative decisions

**Decision 1: One decision gate, not ten.**  
We could have made every eval a graph node and routed on all of them. That would be expensive (many extra LLM calls per run) and would complicate the graph (many conditional edges and retry loops). So we picked **one** eval to act as a gate: **stop decision** ("did we stop at the right time?"). It runs after conflict detection and before writer context. If the score is below a threshold and we have retry budget left, we route back to `conflict_resolution_research` for a targeted gap-filling pass (max one retry). Otherwise we proceed to the writer. All other evals stay in `run.py` as monitoring only.

**Decision 2: No graph node for section completeness.**  
We briefly had a node `evaluate_section_drafts` between `write_sections` and `write_report` that ran section completeness on the drafts and logged the score. The question was: do we need it in the graph at all? Since section completeness was only for monitoring (no routing), the answer was no. Keeping it as one of the 10 evals in `run.py` is simpler: same pattern as the others, one place for all post-run metrics, and we still evaluate "does the **final** report cover all sections?" which is what we care about for logging. So we removed the node and kept section completeness only in the CLI eval batch.

**Decision 3: Per-section scores without a graph node.**  
We still wanted to know **which** sections were weak, not just an overall section-completeness score. Options were: (a) a graph node that runs after section drafts and stores per-section scores in state, (b) run section completeness once in `run.py` but ask the judge for **structured output** (overall score + a list of section_id, score, reason per section). We chose (b). The section_completeness eval now returns a 3-tuple: (overall_score, reasoning, section_scores). The evals JSON and the CLI both include this breakdown. So we get per-section visibility where we already run evals, without adding graph nodes or state.

**Decision 4: Async evals in the CLI.**  
The 10 monitoring evals in `run.py` are independent LLM-as-judge calls. Running them sequentially was slow. We added async versions of each eval and an `async_run_evals` that uses `asyncio.gather` so all 10 run concurrently. The CLI runs them by default; use `--no-eval` to skip. Same outputs, less wall-clock time.

### What we actually implemented

- **Inside the graph:** A single node `eval_stop_gate` (in `deep_research/nodes/conflicts.py`) that runs `eval_stop_decision(research_trace, knowledge_gaps)`, writes `stop_eval_score`, `research_sufficient`, and `research_retry_count` to state, and is used by `stop_eval_route` to decide between "conflict_resolution_research" and "prepare_writer_context". No other evals run inside the graph.
- **In run.py:** All 10 evals run via `async_run_evals` unless `--no-eval` is passed. Results are printed and written to `*_evals.json`. Section completeness now returns and stores an overall score plus `section_scores` (list of per-section score and reason), so we track each section's completeness in the same file.
- **No extra graph nodes for monitoring.** Section completeness is not a node; it is just one of the 10 evals with a richer return shape.

### Tradeoffs we considered

| Tradeoff | Choice | Why |
|----------|--------|-----|
| Decision gate: one vs many | One (stop decision only) | Cost and complexity. One gate gives most of the benefit (avoid writing when research was clearly insufficient) without turning the graph into a maze of eval-driven branches. |
| Section completeness: graph node vs CLI only | CLI only | It was monitoring only; nothing in the graph consumed the score. Keeping it with the other evals avoids an extra node and keeps all post-run metrics in one place. |
| Per-section scores: node + state vs structured eval output | Structured eval output | We wanted per-section visibility without polluting state or adding a node. Extending the section_completeness judge to return a list of (section_id, score, reason) gave us that in the existing evals JSON and CLI. |
| Eval run location: always in graph vs opt-in in CLI | Gate in graph, monitoring in CLI | The gate must be in the graph to affect routing. Monitoring evals run by default after the report; `--no-eval` skips them to save cost/latency. |

### Summary of the eval restructure

- **One decision gate in the graph:** `eval_stop_gate` uses stop-decision quality to decide whether to do one more research pass or proceed to writing.
- **All other evals stay in the CLI:** Run asynchronously after the report unless `--no-eval`; same JSON and console output as before.
- **Section completeness:** Still one of those 10 evals, but now returns (and we store) an overall score plus per-section scores and reasons, so we can see which sections were weak without adding graph nodes or state.

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

## Improvement: Section summary evidence (addressing shallowness)

This section records the thought process and tradeoffs behind the change that addressed “section summaries don’t get full evidence body yet.”

### The problem

The section summary node produces the “backbone” each section writer uses. It was only given a **truncated slice** of that section’s evidence:

- **Top 10 items only** — evidence sorted by relevance, then only the first 10 were sent to the summary LLM.
- **500 characters per snippet** — each snippet was cut at 500 chars.

So the summary was grounded in at most ~5k characters of evidence per section, even when the section had many more items and longer snippets. The **full** evidence still flowed to the writer later, but the **summary** that shapes what gets written was based on this small slice, which capped quality and could miss important nuance.

### How we iteratively got here

1. **First reaction: “just bump the numbers.”**  
   We could have hardcoded e.g. top 20 and 1200 chars. That would help, but any future tune would require a code change and a release. We wanted the behavior to be **tunable without touching code**.

2. **Second idea: make it configurable.**  
   Add `section.summary_top_n` and `section.summary_snippet_chars` in config, with better defaults (e.g. 25 and 1200). Operators could then trade cost vs quality per deployment. That still leaves a fixed “top-N + cap per snippet” rule: we never pass **all** evidence, only more of it.

3. **Third idea: support “full evidence” when needed.**  
   For sections where we really want the summary to see everything (up to context limits), we added an optional **character budget**: `section.summary_evidence_max_chars`. When set to a value &gt; 0, the node fills the summary context with full snippets in relevance order until the budget is reached, truncating only the last snippet if needed. When 0 (default), we keep the “top-N + per-snippet cap” behaviour. So we get: **configurable defaults** for most runs, and an **opt-in “full evidence” mode** for power users or critical sections.

### What we implemented

- **Configuration:** `section.summary_top_n`, `section.summary_snippet_chars`, and optional `section.summary_evidence_max_chars` (default 0). `configuration.py` defaults are **25** / **1200** / **0** when keys are omitted; the bundled `config.yaml` (and research-mode overlays) may set lower `summary_top_n` (e.g. 5) for cost. All values are read via `get_config()`.
- **Section summary node:** Builds the evidence string for the summary prompt in one of two ways: (1) **Budget mode** (`summary_evidence_max_chars` &gt; 0): fill with full snippets until the budget, then truncate only the last one if necessary. (2) **Top-N mode** (otherwise): take the top `summary_top_n` items and cap each snippet at `summary_snippet_chars`. The rest of the node (prompt, JSON parsing, section_result shape) is unchanged.
- **No change to writer or merge.** The writer still receives section_summaries and evidence as before; we only improved what goes **into** the summary.

### Why this approach

- **Configurable first:** Different runs (e.g. cost-sensitive vs quality-sensitive) can tune limits without code changes. Defaults improve quality over the old 10×500 without requiring new config.
- **Optional full-evidence path:** When someone needs the strongest possible summary for a section, they can set a character budget and get “as much evidence as fits” instead of a fixed top-N. We don’t force that on everyone because it increases token use and can hit context limits on very large sections.
- **Single place to change:** All logic lives in the section summary node and config; no new nodes or graph edges. The writer and the rest of the pipeline stay unaware of the two modes.

### Tradeoffs we considered

| Tradeoff | Choice | Why |
|----------|--------|-----|
| Hardcoded vs configurable | Configurable | Lets us tune and A/B test without code changes; different environments can use different limits. |
| One mode vs two (top-N vs budget) | Two modes | Top-N + snippet cap is simple and predictable; budget mode answers “I want full evidence” without hardcoding a huge top-N. |
| Defaults: conservative vs aggressive | Code defaults 25×1200; repo config may override (e.g. top-N 5) | Old 10×500 was too weak; 25×1200 in code improves quality when no YAML override. Shipped YAML can tune down top-N for cheaper runs. |
| Budget mode: truncate last snippet vs drop last item | Truncate last snippet | Fits as many **items** as possible within the budget, then truncate only the final snippet so we don’t lose a whole source. |
| Where to document | DESIGN.md + config comments | So the next person understands why the knobs exist and what “section shallowness” referred to. |

### Summary

Section summaries used to be shallow because they only saw a small, truncated slice of each section’s evidence. We fixed that by (1) making the slice size and per-snippet length configurable with better defaults, and (2) adding an optional character-budget mode so that when needed, the summary can see “full” evidence up to a cap. The change is entirely in configuration and the section summary node; the iterative thought process was: hardcode bump → make it configurable → add an optional full-evidence path.

---

## Where The Code Still Falls Short Of The Design

The broad architecture is solid, but a few details are still rough.

- **Planner model keys:** Aligned — see note above (`planner_simple` / `planner_complex` in YAML ↔ loader).
- **`dispatch_sections()`** uses **`max_parallel_sections`** from config (`section.max_parallel` in YAML via `_YAML_TO_FLAT`), not a hardcoded fan-out count; the literal `6` appears only as a **fallback default** in code if config omits the value.
- **Section summaries:** The summary node supports **top-N × per-snippet cap** (defaults `section_summary_top_n` / `section_summary_snippet_chars`) and an optional **character-budget mode** when `section.summary_evidence_max_chars` &gt; 0 so more full snippet text can flow into the prompt up to that budget. “Full corpus in one prompt” is still impractical; further gains would be multi-pass or chunked summarization.
- Conflict resolution has been deepened: adjudication now receives original evidence plus metadata (credibility, source_type) and disambiguation search results; the writer receives explicit conflict_resolutions (winning_claim, resolution_verdict) so the report can prefer winning claims and surface caveats. It can be taken further (e.g. iterative resolution, downgrading losing evidence).
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
- stronger regression-style evaluation (cache layer for search/pages is already in place; tuning and broader test coverage remain)

---

## Future Scope 🚀

### Priority 2 — High-Impact Improvements

**5. Caching Layer** *(implemented; extension ideas remain)*

- **What:** SQLite-backed TTL cache for search responses and full-page extraction (`deep_research/cache.py`, `cache:` in `config.yaml`).
- **Why:** Saves API cost and latency; helps offline-ish debugging when hits replay.
- **Possible next steps:** Broader key dimensions, warming, or export of cache stats for ops.

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

**10. Dynamic Section Depth**

- **What:** Allocate iteration budget per section by difficulty instead of a fixed cap for all. Simple sections stop earlier; “hard” sections (low coverage scores, detected gaps, or local conflicts) receive more search–normalize–assess loops or queries before summarizing.
- **Why:** Saves cost and latency on easy sections while pushing depth where evidence is thin—better ROI than uniform max iterations everywhere.

**11. Golden-Query Regression Suite**

- **What:** A small, fixed set of benchmark queries checked in CI: run the graph (or replay saved artifacts), run evals, and assert scores stay above thresholds or compare reports/eval JSON to stored baselines (allowlisted drift).
- **Why:** Catches regressions in routing, prompts, or provider behavior that unit tests miss; fits how LLM workflows are usually gated in practice.

**12. Stronger Test Coverage**

There is graph/routing coverage in `tests/test_graph.py` plus `tests/test_cache_integration.py` for the cache. Still add:

- Unit tests per node — test each node function in isolation with mocked LLM calls
- Config validation tests — ensure all config paths produce valid Configuration objects
- Edge case tests — empty search results, LLM refusals, malformed JSON responses

*(Golden-query / eval-threshold CI is called out explicitly in **11**.)*

### Priority 3 — If You Had More Time (Stretch Goals)

These are features that would make this genuinely competitive with commercial deep research tools.

**13. Persistent Vector Store for Evidence**

Store all evidence across runs in a vector DB (ChromaDB, Qdrant, or pgvector). Enable:

- "What have I already researched about X?"
- Cross-run knowledge accumulation
- Semantic retrieval of past evidence for new queries

**14. Multi-Modal Sources**

Add support for:

- PDF extraction — academic papers, whitepapers
- YouTube transcript search — talks, interviews
- GitHub code search — for technical topics
- ArXiv API — first-class academic source

**15. Interactive Report Editing**

After the report is generated, let the user interactively:

- Ask follow-up questions about specific sections
- Request deeper research on a section
- Edit section content and regenerate with new evidence

This is essentially Phase 3 (deeper HITL) from your roadmap.

**16. Cost Tracking & Budget Controls**

Track and display:

- Total tokens used (input/output per model)
- Total search API calls and credits
- Estimated cost per run
- Hard budget caps that stop the graph when exceeded

**17. Async / Parallel Node Execution**

Section workers already run conceptually in parallel, but within each section worker, the search → normalize → assess loop is sequential. For broad sections, run multiple search queries concurrently using asyncio or LangGraph's native async support.

**18. Web UI / API Mode**

Wrap `run.py` in a FastAPI server with:

- WebSocket for streaming progress
- REST endpoint for submitting queries
- Simple React frontend showing plan → progress → report
- Report history and re-run capability

**19. Source Credibility Database**

Build a lightweight credibility index for domains:

- Known official/government domains → high credibility
- Known content farms / SEO spam → low credibility

Use this to weight evidence during writer-context preparation, not just as metadata.

**20. Comparative Analysis Engine**

For queries classified as "comparative" (e.g., "LangGraph vs CrewAI"):

- Enforce balanced evidence collection per subject
- Auto-generate comparison tables
- Flag when one side has significantly more/better sources

**21. Citation Verification Loop**

After the report is written, run a verification pass:

- Check that each [N] citation actually matches the evidence it's attributed to
- Flag hallucinated citations (claims attributed to sources that don't support them)
- Regenerate problem sections if citation accuracy is below threshold

**22. Export Formats**

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
