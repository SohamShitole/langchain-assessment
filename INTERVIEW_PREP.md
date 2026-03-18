# Interview Prep: Deep Research Agent

Use this as a study guide and talking-point cheat sheet when presenting this project.

---

## 1. Topics to Study (Concepts)

### LangChain / LangGraph
- **LangGraph**: Graph-based orchestration for LLM workflows (nodes, edges, state, conditional edges).
- **StateGraph**: How state flows between nodes; `TypedDict` state with reducers for parallel updates (`add_messages`, `operator.add`, custom `_merge_sets`, `_keep_first`).
- **Conditional edges**: Routing based on state (e.g. “loop again” vs “go to writer”) instead of fixed linear flow.
- **Subgraphs**: Embedding a smaller graph (section worker) as a node in a parent graph.
- **Checkpointing & interrupts**: Pausing the graph (e.g. after plan) for human-in-the-loop; `interrupt_after`, `checkpointer`.

### LLM / Agent Design
- **Iterative research loops**: Generate queries → search → normalize → assess coverage → repeat or write. Why one-shot search is brittle.
- **Evidence normalization**: Clean, dedupe, score, and map search results before the writer. Raw results → structured evidence.
- **Writer-context preparation**: Rank, cap, and curate evidence so the writer gets a bounded, high-quality context (avoids noise and token overflow).
- **Model routing**: Use cheaper models for classification/routing, stronger models for planning and final writing (cost vs quality).
- **Explicit stopping logic**: Coverage checks and iteration budgets instead of “search until it feels done.”

### Search & RAG-Adjacent
- **Search as a replaceable layer**: Multiple providers (Exa, Tavily, Gensee) with a common evidence shape so the graph stays stable.
- **Deduplication**: URL-based (and design doc notes future: canonicalization + optional semantic dedup).
- **Citation grounding**: Report sections tied to evidence; source list rebuilt from state when needed.

### Evaluation & Observability
- **LLM-as-judge evals**: Claim support, factual accuracy, citation relevance, section completeness, conflict handling, stop decision quality, etc.
- **Explainability**: Progress streaming, plan approval, process logs, research trace, saved trace files, evals.

### Software / Architecture
- **Config-driven behavior**: `config.yaml` + `configuration.py` for search, models, writer context, section worker, conflict resolution, report structure.
- **Report presets**: `report_presets.yaml` for different layouts (Standard, Academic, Consulting, OpenAI-style, etc.) referenced by number in config.
- **Entry point**: `run.py` — load config, run graph, stream progress, plan approval, write report, optional `--trace`, `--log`, `--eval`.

---

## 2. What to Know From This Project

### One-Liner
A **graph-based deep research agent** that takes a question, plans a report, runs **parallel section workers** (each with its own search → normalize → coverage loop), merges evidence, optionally resolves conflicts, curates context for the writer, and produces a **grounded markdown report with citations**.

### Default Flow (Phase 2) — Trace It on a Whiteboard
1. **ingest_request** — Read query, init state.
2. **classify_complexity** — Simple / moderate / complex (affects planning tier).
3. **create_research_plan** — Propose report structure.
4. **Human-in-the-loop** — CLI can pause here for plan approve/edit/cancel (`--auto` skips).
5. **decompose_into_sections** — Turn plan into section tasks.
6. **dispatch_sections** — Fan out to **section_worker** (one per section, parallel).
7. **Section worker subgraph** (per section): generate_section_queries → section_search → section_normalize → section_assess_coverage → **route**: loop again (if incomplete and under budget) or generate_section_summary → END.
8. **merge_section_evidence** — Combine section results, dedupe.
9. **detect_global_gaps_and_conflicts** — Decide if conflict-resolution research is needed.
10. **conflict_route** — If conflicts and enabled → **conflict_resolution_research**; else → **prepare_writer_context**.
11. **prepare_writer_context** — Rank, cap, and select evidence for the writer.
12. **write_sections** → **write_report** — Draft sections, assemble final report.
13. **finalize_messages** — Append report to graph messages.

### Key Files (Say Where Things Live)
- **Entry / CLI**: `run.py`
- **Main graph**: `deep_research/graph.py` — `create_research_graph()` (Phase 2), `create_research_graph_phase1()` (legacy).
- **Section worker graph**: `deep_research/section_graph.py`
- **State**: `deep_research/state.py` — `ResearchState`, `SectionWorkerState` (reducers for parallel workers).
- **Routing**: `deep_research/routing.py` — `route` (Phase 1), `section_route`, `conflict_route`.
- **Nodes**: `deep_research/nodes/` — ingest, classify, planner, decompose, search, normalize, coverage, merge, conflicts, writer_context, section_writer, writer, finalize.
- **Config**: `config.yaml`, `deep_research/configuration.py`, `report_presets.yaml`.
- **Prompts**: `deep_research/prompts.py`.
- **Evals**: `deep_research/evals/`.

### Design Decisions You Can Defend
- **Why a graph instead of a chain**: Routing, loops, shared state, optional interrupt — control flow is explicit and inspectable.
- **Why normalize evidence**: Search is noisy; normalization improves report quality more than many prompt tweaks.
- **Why cap writer context**: Too much context hurts quality; ranking and capping beats “dump everything.”
- **Why section workers**: Reports are sectional; per-section research gives narrower queries and better coverage for broad topics.
- **Why pause after plan only**: Human leverage where it matters (scope) without making the whole flow interactive.
- **Why explicit coverage + iteration budget**: “Search until done” is not a design; coverage checks make the loop predictable.

### Honest Shortcomings (From DESIGN.md)
- Config and configuration.py not fully aligned for some planner model names.
- Section summaries don’t get full evidence body yet.
- Conflict resolution is still shallow.
- Dedup is URL-based (no semantic dedup yet).
- Tests are more graph/smoke than deep node correctness.

---

## 3. Likely Interview Questions & Answers

**“Walk me through the architecture.”**  
Use the Phase 2 flow above. Mention: ingest → classify → plan → (optional human approval) → decompose → parallel section workers → merge → conflict detection → optional conflict research → prepare writer context → write sections → write report → finalize. Emphasize state, conditional edges, and subgraph.

**“Why LangGraph?”**  
We need loops (research until coverage or budget), branching (conflict vs no conflict), and a clear place to interrupt (plan approval). A graph makes that explicit and debuggable.

**“How do you avoid the writer hallucinating or ignoring sources?”**  
We normalize and curate evidence, map it to sections, and cap what the writer sees. We also repair the Sources section from state when needed. Evals include claim support and citation relevance.

**“How do you handle conflicting information?”**  
We detect global conflicts after merging section evidence. If enabled, we run a conflict_resolution_research step before preparing writer context; the writer then sees the reconciled picture.

**“How is state managed with parallel section workers?”**  
Section workers run as a subgraph. We use reducers in state: e.g. `section_results` with `operator.add`, `global_seen_urls` with `_merge_sets`, and `_keep_first` for fields like `query` so parallel updates don’t overwrite each other incorrectly.

**“What would you improve next?”**  
Config cleanup, stronger section summaries (full evidence into summary), better conflict adjudication, semantic dedup, caching for search, streaming report output, and more unit tests per node.

**“What was the hardest bug you hit while building this?”**  
A strong answer is **state merging with parallel section workers (and the checkpointer)**. When the main graph fans out with `Send()` to multiple section workers, each worker returns a state update that LangGraph merges using reducers. We use `operator.add` for `section_results`, `_merge_sets` for `global_seen_urls`, and `_keep_first` for `query` and `section_max_iterations`. In some runs, `writer_evidence_subset` (set by `prepare_writer_context`) could end up empty in the state that the writer node saw—e.g. due to reducer semantics, merge order, or how the checkpointer applied updates. The writer node has an explicit fallback: if `writer_evidence_subset` is empty, it uses `merged_evidence` to build the evidence list. That fallback exists because we hit the “writer got no evidence” case (see comment in `nodes/writer.py`). Other candidates: **malformed JSON from the planner or decompose** (we added strip‑code‑fence + fallback defaults); **coverage/route returning something unexpected** and breaking the conditional edge; or **section worker state** (e.g. `section_results` shape) not matching what merge expects. If you didn’t hit a specific bug, say: “The trickiest area was getting state and reducers right when merging parallel section worker results back into the main graph, and ensuring the writer always receives evidence—we added a fallback path for that.”

**“If you had 2 more days, what would you improve?”**  
(1) **Robustness and safety:** Wrap all `with_structured_output` / function-calling nodes in try/except with safe defaults (§27), and add a minimal guardrail (e.g. one content-safety or regex check on the final report before returning) so we don’t serve clearly off-policy output. (2) **Observability and cost:** Implement token tracking and a per-run cost guardrail (cap estimated cost and abort or trim if exceeded), and ensure every run emits a LangSmith trace with cost and step count for alerting. (3) **Quality:** Add one retry-before-fallback for JSON and structured output nodes to reduce silent degradation; optionally add async for search loops and writer-context prep to cut latency. (4) **Security/compliance:** Add prompt delimiters for user/evidence (§29) and PII redaction (or allowlist) for logs (§30). Pick 2–3 that match the role (e.g. safety + cost for production, or quality + tests for reliability).

**“How do you stay up-to-date with LangChain/LangGraph releases?”**  
(1) **GitHub:** Watch [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) and [langchain-ai/langchain](https://github.com/langchain-ai/langchain) for Releases and Discussions; skim release notes for breaking changes and new features (e.g. checkpointing, streaming, Studio). (2) **Docs and changelog:** Check the official LangChain/LangGraph docs and any “What’s new” or changelog pages when starting a new feature or upgrading. (3) **Community:** LangChain Discord and their blog for announcements, migration guides, and best practices. (4) **Dependency hygiene:** Periodically run `pip list --outdated` or Dependabot and read release notes before bumping `langgraph` / `langchain-*` so you catch deprecations and new APIs early.

**“Any questions for us?”** — Use 2–3 of these (adapt to who you’re talking to):

1. **Agent platform & LangGraph:** “How are production agents built today—fully on LangGraph, or a mix of LangGraph and other stacks? What’s the main thing you’d want to improve in your agent platform over the next year?”
2. **LangSmith usage:** “How do you use LangSmith internally—mainly for eval and debugging, or also for production monitoring, cost tracking, and alerting? How do you decide what gets traced in prod vs. only in staging?”
3. **Eval and quality:** “How do you run evals on agent flows—LangSmith datasets + custom evaluators, or something else? How do you gate or monitor quality when you ship a new prompt or graph change?”
4. **Scale and reliability:** “For high-traffic agent use cases, how do you handle rate limits, retries, and fallbacks to the LLM and external tools? Any patterns you’ve settled on for cost guardrails or per-user caps?”

---

## 4. Demo / Presentation Tips

1. **Run a short query** (e.g. “What are the main differences between LangGraph and CrewAI?”) so they see progress and a report.
2. **Show the flow in LangSmith Studio** if possible: `langgraph dev` → connect Studio → run the research graph and show nodes/steps.
3. **Mention Phase 1 vs Phase 2**: “Default is section-based (Phase 2); we also kept the simpler single-agent loop (Phase 1) for comparison and debugging.”
4. **Point to DESIGN.md**: “We documented evolution, tradeoffs, and known gaps so the design is honest, not just aspirational.”
5. **CLI flags**: `--auto` (skip plan approval), `--trace` (save trace JSON), `--eval` (run evals), `--search-provider`, `--max-iterations`.

---

## 5. Quick Reference: Commands

```bash
# Run
python run.py "Your research question"
python run.py "Question" --auto
python run.py "Question" --trace --eval -o ./output

# Dev server for Studio
langgraph dev

# Tests
pytest tests/ -v
```

---

## 6. Mock Interview: 20 Project-Grounded Questions

These are the kinds of questions a Senior EM at LangChain would ask **about this repo specifically**. Use them to prep; answer in terms of your actual graph, state, nodes, and config.

### Phase 1: Grounded opening (Q1–2)

1. **"Walk me through your deep research agent. What does it do end-to-end, and what was the hardest part that wasn't in the LangGraph docs?"**  
   *Probing:* One-liner + real pain (e.g. state merge with parallel workers, writer fallback, JSON from planner/decompose).

2. **"In your project you have both Phase 1 (single-agent loop) and Phase 2 (section workers). When would you choose one over the other, and why is Phase 2 the default?"**  
   *Probing:* Tradeoffs (monolithic vs sectional research, coverage, context limits) and product sense.

### Phase 2: Architecture, scale, resilience (Q3–10)

3. **"Your `dispatch_sections` returns a list of `Send('section_worker', {...})`. Walk me through what each worker receives, what it returns, and how the parent graph merges those results. What could go wrong at merge time?"**  
   *Probing:* Payload (section_task, global_seen_urls, query, section_max_iterations), section_results reducer, and the writer_evidence_subset fallback in `writer.py`.

4. **"In `state.py` you use `_keep_first` for `query` and `section_max_iterations` and `operator.add` for `section_results`. Why not use the same reducer for everything? What happens if you did?"**  
   *Probing:* Parallel workers each emitting a scalar vs a list; overwrite vs accumulate.

5. **"Your config has `section.max_parallel: 10` and each section worker can do up to `section_max_iterations` with multiple search calls. How would you add rate limiting so you don't blow through Exa/Tavily/OpenAI limits when 10 sections run at once?"**  
   *Probing:* DESIGN.md calls out no retry/backoff; they want a concrete design (per-provider limits, queue, backoff, fallback provider).

6. **"The writer node has a fallback: if `writer_evidence_subset` is empty, it uses `merged_evidence`. Why does that empty case happen, and is that fallback sufficient for production?"**  
   *Probing:* Reducer/checkpointer merge order; whether fallback is correct or just a band-aid.

7. **"How would you debug a run where the final report is wrong but `prepare_writer_context` and `merged_evidence` look correct? What do you log today, and what would you add?"**  
   *Probing:* Trace, `--trace` JSON, LangSmith; gaps (e.g. token counts, per-node timing, evidence actually passed to writer).

8. **"Your section worker loop is: generate_section_queries → section_search → section_normalize → section_assess_coverage → route. Where would you put retries and timeouts, and what's the failure model if section_search returns 429?"**  
   *Probing:* Today the graph can fail; they want retry boundaries and fallback (e.g. skip section, use cached, or fail gracefully).

9. **"`writer_context_max_items` caps how much evidence the writer sees. How did you pick that number, and how would you tune it for a 50-section report vs a 3-section brief?"**  
   *Probing:* Token budget, quality vs context size; dynamic cap or per-section caps.

10. **"You support multiple search providers (Exa, Tavily, Gensee). How is the evidence shape normalized so the rest of the graph doesn't care which provider ran? What breaks if a new provider returns a different schema?"**  
    *Probing:* Normalize layer, common evidence structure; adapter pattern and validation.

### Phase 3: "8th house" — hidden systems, debt, failure (Q11–14)

11. **"Your DESIGN.md says config and configuration.py aren't fully aligned for some planner model names, and that section summaries don't get full evidence body yet. If you inherited this codebase, what would you fix first and why?"**  
    *Probing:* Prioritization: correctness (writer fallback, config) vs quality (summaries) vs robustness (retries, rate limits).

12. **"A run produces a report that cites a URL that never appeared in the evidence. Where in your pipeline could that leak, and how would you prevent it?"**  
    *Probing:* Writer only sees writer_evidence_subset/merged_evidence; source list rebuilt from state; hallucination vs bug in source assembly.

13. **"The planner and decompose nodes parse JSON from the LLM with strip-code-fence and fallback defaults. What's the risk of silent degradation when the model returns malformed JSON, and how would you harden it?"**  
    *Probing:* Try/except, retry once, fallback to minimal valid structure; observability (log parse failures).

14. **"Your evals run after the report is written (`--eval`). How would you use them to gate a bad deploy—e.g. a prompt change that tanks citation relevance? What's missing today?"**  
    *Probing:* Evals are "for inspection and benchmarking"; no threshold or CI gate; dataset + threshold + blocking deploy.

### Phase 4: Edge cases, future-proofing (Q15–17)

15. **"Right now the graph is synchronous and single-tenant (one query per process). How would you design it so the same code could run in a server with 100 concurrent requests and shared rate limits?"**  
    *Probing:* Concurrency, queue, or per-request isolation; shared checkpointer vs in-memory; rate-limit pool.

16. **"If LangGraph added a native 'parallel node with merge' primitive that replaced your Send + reducer pattern, would you migrate? What would you want from that primitive?"**  
    *Probing:* Reducer semantics, payload shape, observability per branch.

17. **"Your conflict resolution runs after merge and before prepare_writer_context. How would you extend the system so conflicts could be resolved per-section inside the section worker, instead of only globally?"**  
    *Probing:* Where conflict detection lives; tradeoff between global consistency and latency/complexity.

### Phase 5: Ownership and responsibility (Q18–20)

18. **"You own this agent in production. OpenAI has a 4-hour outage. What's your runbook? How does the CLI and graph behave today, and what would you add?"**  
    *Probing:* Today: graph fails; add retries, fallback model or queue, user-facing message, status page.

19. **"A PM wants to add 'regenerate section' so the user can click one section and re-run only that section worker. What would you need to change in the graph and state to support that?"**  
    *Probing:* Re-entrancy, partial state (one section_task), merge back into existing merged_evidence; checkpointer and thread_id.

20. **"What's one thing you'd change about how this project is structured or documented before handing it to another team at LangChain? Why does it matter?"**  
    *Probing:* Honest ownership: tests, config alignment, DESIGN.md, runbooks, or observability—and impact on maintainability.

---

**Feedback to apply after each answer:**  
- If you sounded too passive: add one sentence of "why this matters for production" or "what I'd ship first."  
- When you stayed high-level: drop into a specific file or state key (e.g. "in `writer.py` we do…", "the reducer for `section_results`…").  
- When you nail the architecture: briefly call out the tradeoff you made (e.g. "we chose _keep_first so we don't overwrite query when N workers finish").

---

Good luck. You built a real multi-node, stateful, section-parallel research graph with routing, human-in-the-loop, and evaluation — that’s plenty to talk about.
