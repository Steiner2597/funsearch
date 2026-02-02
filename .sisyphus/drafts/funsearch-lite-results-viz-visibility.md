# Draft: FunSearch-Lite Results Analysis + Viz + Project Visibility

## Core Objective (user request)
- Analyze latest training results (funsearch_orlib_small_20260201_144522)
- Propose concrete improvement ideas (algorithm + LLM prompting + evaluation metrics)
- Add enhanced visualization/output (dashboard, per-island plots, dedup stats, timing, report)
- Increase “work visibility” (docs, diagrams, tables, annotated examples, benchmarks)

## Current Observations (provided)
- Gen0–1: best 54.85, avg 46.88, count 3; Gen2: best 92.1125, avg 58.19, count 4; Gen3–5 plateau; dedup_skipped grows 16–37.
- Best candidate: sophisticated heuristic with sigmoid penalty + exponential decay age factor.
- High dedup_skipped suggests LLM generates many duplicates / functionally equivalent variants.

## Existing Code/Artifacts (verified from repo)
- Plotting: `experiments/plotting.py` supports evolution curve, failure distribution pie, diversity curve.
- Runner prints tqdm progress and saves per-generation stats to JSONL via `experiments/artifacts.py`.
- Deduplication: `funsearch_core/deduplication.py` implements code-hash + behavior signature and tracks stats internally.
- Prompts: `llm/prompts.py` has simple “fresh/mutate/refine” prompts; no explicit novelty/anti-dup constraints.
- Latest best candidate exported to: `artifacts/funsearch_orlib_small_20260201_144522/best_candidate.py`.

## Gaps / Opportunities (initial)
- Metrics JSONL currently stores whatever `FunSearchLoop.run_generation()` returns; includes `overall`, `islands`, `dedup_skipped`, `dedup_skipped_total` but lacks LLM call stats, timing breakdown, per-island dedup, evaluation failures breakdown (beyond error_type).
- No multi-panel dashboard plot; no per-island curve plot; no dedup/time series visualizations.
- No run-to-run comparison report/table.
- README already strong but could add “benchmarks table”, “example artifacts”, “architecture diagrams” (Mermaid), “experiment cookbook”.

## Constraints (confirmed)
- Python project; matplotlib, tqdm, SQLite; avoid new major deps.
- Prefer adding/modifying: `experiments/plotting.py`, `experiments/artifacts.py`, `experiments/runner.py`, `README.md`.
- Potential new modules: `experiments/report.py`, `experiments/dashboard.py`, `docs/` additions.

## Open Questions
- Test strategy for this work: **TDD** (user confirmed).
- Scope aggressiveness: implement search/prompt changes now vs only add reporting/visibility?

## Test Strategy Decision
- **Infrastructure exists**: YES (pytest; ~48 tests)
- **User wants tests**: YES (TDD)
- **QA approach**: Automated via pytest + golden artifact checks for plots/reports

## Scope Boundaries
- INCLUDE: metrics schema extension, richer plots, markdown run report, comparison utilities, docs/README enhancements.
- EXCLUDE (not yet confirmed): changing core search semantics beyond diversity/prompt improvements (needs explicit go/no-go).
