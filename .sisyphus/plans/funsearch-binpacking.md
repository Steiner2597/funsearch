# FunSearch-Style LLM-Guided Evolutionary Search (Bin Packing) — Work Plan

## TL;DR

> **Quick Summary**: Build a minimal-but-complete FunSearch-style evolutionary program search loop where LLMs propose bin-packing heuristics, a best-effort pure-Python sandbox executes them safely, deterministic multi-fidelity evaluators score them, and the system logs/plots the full search trajectory.
>
> **Deliverables**:
> - Python packages: `funsearch_core/`, `llm/`, `evaluator/`, `sandbox/`, `store/`, `experiments/` (+ `ui/` placeholder)
> - Deterministic bin packing task with `cheap_eval` + `full_eval`
> - Multi-model generation/refinement via unified `BaseLLMProvider`
> - SQLite-backed candidate store + dedup + run artifacts
> - CLI one-click runs from YAML config + matplotlib evolution curves
> - Pytest unit + integration + sandbox safety tests
>
> **Estimated Effort**: Large (course-grade completeness + safety + tests)
> **Parallel Execution**: YES — 4 waves after scaffold
> **Critical Path**: Sandbox → Evaluator → Core search loop → Experiments/CLI + observability

---

## Context

### Original Request
Greenfield Python 3.10+ FunSearch-style LLM-guided evolutionary search system with:
- 7 modules (core/llm/evaluator/sandbox/store/experiments/ui-later)
- 3 innovation points: multi-fidelity eval, multi-model collaboration, trajectory observability
- deterministic automated numeric evaluation; untrusted code must be sandboxed
- config-driven + reproducible experiments + pytest tests

### Interview Summary (Confirmed Decisions)
- Demo task: **Bin Packing Problem**
  - `cheap_eval`: small instances (10–20 items)
  - `full_eval`: larger instances (50–100 items)
- Sandbox: **pure-Python lightweight** (no Docker); use timeout + restricted imports + execution restrictions (best-effort)
- Candidate interface: **NARROW** — LLM generates only:
  - `score_bin(item_size, remaining_capacity, bin_index, step) -> float`
- Dependencies allowed: `matplotlib`, `pyyaml`, `pydantic`, `typer`, stdlib `sqlite3`
- Tests: **pytest** (unit + integration + sandbox safety)
- Config: **YAML**
- Target OS: **cross-platform with degradation**
  - Windows supported with documented limitations
  - Use `resource.setrlimit`/POSIX controls where available; otherwise fall back to timeout-only + import restrictions
- Package layout: **flat** (packages at repo root)

### “Metis-style” Gap Analysis (Planner Note)
In this environment I can’t invoke a separate Metis agent, so this section captures the same intent: identify hidden requirements and guardrails.

Potential gaps/risks to explicitly guardrail:
- **Pure-Python sandbox is not truly secure** against a determined adversary; we will treat it as best-effort suitable for a course project.
- “No network” must be enforced by **blocking imports/APIs** (e.g., `socket`, `requests`) and by running in a subprocess with a strict allowlist; this is still bypassable in principle.
- Cross-platform resource limiting differs; we will include **graceful degradation + documentation** (Windows supported, but with weaker guarantees).

Guardrails applied:
- Keep candidate interface narrow (heuristic function, not arbitrary full programs) to reduce sandbox attack surface and evaluation variance.
- Determinism: all randomness comes from explicit seeded RNG; forbid candidate access to global RNG/time.

---

## Work Objectives

### Core Objective
Implement a reproducible closed-loop system that evolves LLM-generated bin-packing heuristics using deterministic, sandboxed evaluation with multi-fidelity scoring, multi-model collaboration, and full trajectory logging/plotting.

### Concrete Deliverables
- **Module skeletons** (docstrings + clear interfaces):
  - `funsearch_core/` (search loop, islands, selection/mutation/promotion)
  - `llm/` (providers, prompt templates, retry/backoff, cache)
  - `evaluator/` (task API + bin packing multi-fidelity evaluator)
  - `sandbox/` (subprocess runner, policy/allowlist, time/memory limits)
  - `store/` (SQLite schema, candidate/eval/run persistence, dedup)
  - `experiments/` (YAML config, seeds, CLI, artifacts, plotting)
  - `ui/` (placeholder module; later)
- **Bin Packing baseline** (non-LLM heuristic) to validate evaluator + plotting.
- **End-to-end run** from a single YAML config.

### Definition of Done
- [ ] `pytest -q` passes (unit + integration + sandbox tests)
- [ ] `python -m experiments.cli run configs/binpacking.yaml` produces:
  - SQLite DB artifacts, JSONL/CSV metrics, and a matplotlib curve image
  - a clear “best candidate” export (code + score + provenance)

### Must Have
- Multi-fidelity `cheap_eval → full_eval(Top-K)` with recorded metadata
- Multi-model workflow (cheap generator + strong refiner) selectable by config; candidate records model provenance
- Observability: per-generation best/avg/count + failure stats + plots

### Must NOT Have (Guardrails)
- No hidden randomness (no `time.time()` seeded behavior; no ambient global RNG)
- No hardcoded provider keys/URLs/models inside code (config-driven only)
- No assumption that sandbox is “secure”; document limitations explicitly

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: NO (greenfield) → must be created
- **User wants tests**: YES (pytest)
- **QA approach**: Tests-first where feasible; otherwise tests-after with exhaustive integration checks

### Test Infrastructure Setup (pytest)
Include an early task to add:
- `pyproject.toml` with dependencies and pytest config
- `tests/` layout
- one “smoke test” proving imports + CLI entrypoint wiring

---

## System Design (Key Interfaces — to implement)

### Candidate Contract (Recommended Narrow Interface)
To reduce sandbox risk and ensure deterministic evaluation, constrain LLM output to a **single heuristic function** used by a fixed packing algorithm.

**Candidate code defines**:
```python
def score_bin(item_size: int, remaining_capacity: int, bin_index: int, step: int) -> float:
    ...
```
Framework runs a fixed greedy loop:
- consider all feasible bins
- choose argmax(score_bin)
- else open new bin

Notes:
- Candidate gets only primitives (ints) and no direct access to bins list objects.
- This still allows rich heuristics via arithmetic but avoids arbitrary side effects.

### Multi-Fidelity Evaluation
- `cheap_eval`: few small instances; fast; used for broad filtering
- `full_eval`: more/larger instances; used only on Top-K from cheap
- Store both results + runtime + failure metadata per candidate

### Multi-Model Collaboration
- **Generator model**: cheap provider produces many candidates (mutations + fresh)
- **Refiner model**: stronger provider refines Top-K (prompt includes best candidates + failure modes)

### Observability
- Log per generation: best score, avg score, n_candidates, n_failures, eval_time
- Export metrics as JSONL (append-only) + optional CSV
- Plot curves with matplotlib after run

---

## Execution Strategy

### Parallel Execution Waves

Wave 0 (Foundation — sequential, unblock everything):
- Project scaffold + config + core schemas + test harness

Wave 1 (Parallel):
- Sandbox runner/policy
- Evaluator (bin packing + multi-fidelity)
- Store (SQLite + dedup)

Wave 2 (Parallel):
- LLM abstraction + providers + caching
- Funsearch_core population/islands/selection/mutation logic (using stub LLM)

Wave 3 (Parallel):
- Experiments CLI + orchestration + metrics export
- Observability plotting

Wave 4 (Integration):
- End-to-end run, tuning defaults, documentation for course report

### Dependency Matrix (High Level)
| Component | Depends On |
|---|---|
| Sandbox | Foundation |
| Evaluator | Foundation |
| Store | Foundation |
| LLM | Foundation |
| Funsearch core loop | Sandbox + Evaluator + Store + (LLM or stub) |
| Experiments/CLI | Core loop |
| Plotting/log export | Experiments |

---

## TODOs (Ordered by Dependency & Priority)

> Each task includes: what to do, what not to do, recommended agent profile, parallelization, and acceptance criteria.
> File paths below are **intended outputs** for the executor to create in the implementation phase.

### 0. Repository & Project Scaffold (pyproject, package layout, pytest, typing)

**What to do**:
- Choose and document layout: flat packages at repo root (recommended for course simplicity)
- Add `pyproject.toml` with:
  - dependencies: pydantic, pyyaml, typer, matplotlib, openai (optional, see LLM providers), pytest
  - ruff/black optional (nice-to-have)
- Create package directories with `__init__.py` and module docstrings:
  - `funsearch_core/`, `llm/`, `evaluator/`, `sandbox/`, `store/`, `experiments/`, `ui/`
- Add `tests/` with a smoke test importing each module

**Must NOT do**:
- Don’t implement real logic yet; focus on importable skeleton + contracts

**Recommended Agent Profile**:
- Category: `quick`
- Skills: (none)
- Skills evaluated but omitted: `git-master` (not needed unless committing), `frontend-ui-ux` (UI later)

**Parallelization**: NO (Wave 0)

**Acceptance Criteria**:
- [ ] `pytest -q` runs and passes smoke tests
- [ ] `python -c "import funsearch_core, llm, evaluator, sandbox, store, experiments"` succeeds

---

### 1. Define Core Schemas & Config Models (Candidate, Run, Provider configs)

**What to do**:
- Implement Pydantic models (or dataclasses + pydantic validation) for:
  - `Candidate` (id, code, score, signature, parent_id, generation, runtime, error_type, model_id, eval_metadata)
  - `RunConfig` / `ExperimentConfig` (YAML-driven)
  - `LLMProviderConfig` (provider type, base_url, model name, retries, timeouts)
- Define serialization rules for storing candidates and metrics

**Must NOT do**:
- No ad-hoc dict configs scattered across modules

**Recommended Agent Profile**:
- Category: `ultrabrain`
- Skills: `test-skill` (light guidance for test scaffolding)
- Skills evaluated but omitted: `git-master`

**Parallelization**: YES (Wave 1-compatible)

**References**:
- External: FunSearch paper (Romera-Paredes et al., Nature 2023) for conceptual framing

**Acceptance Criteria**:
- [ ] Unit tests validate schema parsing from minimal YAML dicts
- [ ] Candidate model round-trips to/from JSON without losing required fields

---

### 2. Store Module: SQLite Schema + Candidate/Eval/Run Persistence + Dedup

**What to do**:
- Design SQLite schema:
  - `runs` table (config snapshot, seed, timestamps)
  - `candidates` table (id, code, hash, parent_id, generation, model_id, signature, best_score, status)
  - `evaluations` table (candidate_id, fidelity, score, runtime_ms, error_type, metadata_json)
  - `events/metrics` table or JSONL export for trajectory
- Implement dedup by `code_hash` (normalized code) and/or `(signature, generation)`
- Implement store API:
  - `save_candidate`, `record_evaluation`, `get_top_k`, `list_generation_stats`, `get_best`

**Must NOT do**:
- Don’t store secrets (API keys) in DB; keep only provider identifiers

**Recommended Agent Profile**:
- Category: `ultrabrain`
- Skills: `test-skill`

**Parallelization**: YES (Wave 1)

**Acceptance Criteria**:
- [ ] Unit tests: dedup prevents duplicates; unique constraint enforced
- [ ] Can query Top-K by `cheap_eval` score and confirm stable ordering

---

### 3. Sandbox Module: Pure-Python Best-Effort Runner (Timeout, Limits, Restricted Imports)

**What to do**:
- Implement sandbox execution via **subprocess** (separate interpreter) with:
  - wall-clock timeout (parent-enforced)
  - CPU/memory limits where supported (`resource.setrlimit` on Unix); on Windows: document limitations and fall back to timeout-only + import restrictions
  - restricted builtins (block `open`, `exec`, `eval`, etc. as feasible)
  - import allowlist via custom `__import__` and explicit module allowlist
  - explicit blocklist: `os`, `sys`, `subprocess`, `socket`, `ctypes`, `importlib`, etc.
- Use a strict “protocol”:
  - parent sends input JSON (instance, candidate code id)
  - child returns output JSON (score or bins used, plus errors)
- Make limitations explicit in docs.

**Must NOT do**:
- Don’t claim strong security; this is best-effort.
- Don’t allow arbitrary file system access (use temp working dir + block open).

**Recommended Agent Profile**:
- Category: `ultrabrain`
- Skills: `test-skill`

**Parallelization**: YES (Wave 1)

**Acceptance Criteria**:
- [ ] Sandbox test: infinite loop candidate times out deterministically
- [ ] Sandbox test: `import socket` fails
- [ ] Sandbox test: `open('x','w')` fails
- [ ] Sandbox test: valid heuristic runs and returns numeric output

---

## Decisions Resolved (No further input required)
- Heuristic interface: **NARROW** `score_bin(item_size, remaining_capacity, bin_index, step) -> float`
- OS support: **cross-platform with degradation** (document Windows limitations)
- Package layout: **flat**
- High accuracy review: **NO** (proceed)

---

### 4. Evaluator Module: Bin Packing Task + Deterministic Instance Generator + Multi-Fidelity

**What to do**:
- Define evaluator base interface:
  - `cheap_eval(candidate) -> EvalResult`
  - `full_eval(candidate) -> EvalResult`
  - both deterministic given `(seed, instance_set_id)`
- Implement bin packing:
  - deterministic instance generator (seeded RNG)
  - validator to ensure packing is feasible (no overflow, all items placed)
  - scoring: minimize bins used (optionally add small penalty for runtime)
- Implement fidelity routing:
  - cheap instances: small n, few cases
  - full instances: larger n, more cases

**Must NOT do**:
- Don’t let candidate influence instance generation

**Recommended Agent Profile**:
- Category: `ultrabrain`
- Skills: `test-skill`

**Parallelization**: YES (Wave 1)

**Acceptance Criteria**:
- [ ] Unit tests: deterministic instance generation (same seed ⇒ identical instances)
- [ ] Unit tests: baseline heuristic yields consistent score
- [ ] Unit tests: invalid candidate outputs are detected and scored as failure with `error_type`

---

### 5. LLM Module: Unified Provider Abstraction + Prompt Templates + Retry + Cache

**What to do**:
- Implement `BaseLLMProvider` and `LLMResponse` (text, usage, latency, raw metadata)
- Implement providers:
  - `OpenAIProvider`
  - `DeepSeekProvider` (OpenAI-compatible base_url)
  - `GLMProvider` (either OpenAI-compatible or native SDK wrapper; config selects)
- Add:
  - prompt templates for (a) fresh candidate generation (b) mutation from parent (c) refinement of Top-K
  - retry/backoff policy
  - caching keyed by (provider_id, model, prompt_hash, config_hash)

**Must NOT do**:
- Don’t bake provider-specific logic into core search loop; keep in `llm/`

**Recommended Agent Profile**:
- Category: `ultrabrain`
- Skills: `test-skill`
- Skills evaluated but omitted: `dev-browser` / `playwright` (no browser)

**Parallelization**: YES (Wave 2)

**External References**:
- DeepSeek/OpenAI-compatible usage patterns (many deployments expose OpenAI-like chat completions)
- GLM docs / OpenAI-compatible gateways vary by provider; keep adapter flexible

**Acceptance Criteria**:
- [ ] Unit tests: cache hit returns identical response for same prompt hash
- [ ] Unit tests: provider selection by config routes to correct provider class
- [ ] “FakeProvider” test double supports deterministic offline integration tests

---

### 6. Funsearch Core: Population/Islands, Selection, Mutation, Promotion, Diversity

**What to do**:
- Implement core loop components:
  - population store/read (via `store/`)
  - islands abstraction (e.g., N islands each with its own Top-K + mutation temperature)
  - selection policy (tournament / rank-based)
  - mutation operators:
    - LLM-based mutate-from-parent prompt
    - occasional “fresh” generation
  - promotion policy:
    - cheap_eval all new candidates
    - select Top-K for full_eval
    - update population with diversity constraints
- Diversity signature:
  - compute behavior signature on fixed probe instances (e.g., vector of bins_used on 5 seeds)
  - keep a minimum distance / uniqueness constraint

**Must NOT do**:
- Don’t couple to a specific task; evaluator must be pluggable

**Recommended Agent Profile**:
- Category: `ultrabrain`
- Skills: `test-skill`

**Parallelization**: YES (Wave 2; can start with FakeProvider)

**Acceptance Criteria**:
- [ ] Integration test (offline): FakeProvider generates N candidates; loop runs G generations deterministically
- [ ] Verifies multi-fidelity routing: cheap_eval called for all, full_eval only for Top-K
- [ ] Verifies diversity: duplicates rejected/deduped

---

### 7. Experiments Module: YAML Configs, Seed Control, CLI, One-Click Runs, Artifacts

**What to do**:
- Implement YAML config loader + validation:
  - search hyperparams (generations, islands, population sizes, Top-K)
  - eval settings (instance counts/sizes)
  - LLM settings (provider IDs for cheap/strong roles)
  - reproducibility settings (global seed)
- Build Typer CLI:
  - `run <config.yaml>`
  - `resume <run_id>` (optional)
  - `export-best <run_id>`
- Artifacts layout:
  - `artifacts/<run_id>/run.yaml` (snapshot)
  - `artifacts/<run_id>/metrics.jsonl`
  - `artifacts/<run_id>/plots/*.png`
  - `artifacts/<run_id>/best_candidate.py`

**Must NOT do**:
- Don’t require manual code edits to switch tasks/models

**Recommended Agent Profile**:
- Category: `quick`
- Skills: `test-skill`

**Parallelization**: YES (Wave 3)

**Acceptance Criteria**:
- [ ] `python -m experiments.cli run configs/binpacking.yaml` completes a short run end-to-end
- [ ] Artifacts created; DB updated; metrics JSONL exists

---

### 8. Observability: Metrics, Failure Taxonomy, Matplotlib Plots

**What to do**:
- Define standard metrics per generation:
  - best/avg cheap score; best/avg full score (when available)
  - n_generated, n_deduped, n_failed
  - eval runtimes
- Define failure taxonomy (`error_type`): timeout, import_blocked, runtime_error, invalid_output, overflow, etc.
- Implement matplotlib plotter:
  - evolution curve (best/avg vs generation)
  - failure counts stacked bar

**Must NOT do**:
- Don’t build a web UI; keep to matplotlib + exported logs

**Recommended Agent Profile**:
- Category: `visual-engineering`
- Skills evaluated but omitted: `frontend-ui-ux` (not needed for matplotlib)

**Parallelization**: YES (Wave 3)

**Acceptance Criteria**:
- [ ] Plot images saved to artifacts and readable
- [ ] Metrics export contains all required fields for course report

---

### 9. Multi-Model Collaboration Wiring (Cheap Gen + Strong Refine)

**What to do**:
- Implement role-based model selection:
  - `generator_provider_id` for bulk
  - `refiner_provider_id` for Top-K
- Ensure each Candidate records `model_id` (and role)
- Add prompts for refiner that include:
  - best candidate(s)
  - top failure modes
  - explicit requirement to output only the heuristic function

**Must NOT do**:
- Don’t let refiner overwrite provenance; track parent/child lineage

**Recommended Agent Profile**:
- Category: `ultrabrain`
- Skills: `test-skill`

**Parallelization**: NO (depends on LLM + core loop)

**Acceptance Criteria**:
- [ ] Integration test uses FakeProvider for generator and refiner to verify routing
- [ ] Candidate metadata shows correct provider/model per candidate

---

### 10. UI Module Placeholder (Later Phase)

**What to do**:
- Create `ui/` package with docstring and TODO notes for future dashboard

**Recommended Agent Profile**:
- Category: `quick`
- Skills: (none)

**Parallelization**: YES (anytime)

**Acceptance Criteria**:
- [ ] Imports cleanly; no runtime dependencies

---

### 11. Documentation for Course Report (Explainability + Innovation Points)

**What to do**:
- Write `README.md` and `docs/` notes explaining:
  - architecture and module boundaries
  - the 3 innovation points and how they are demonstrated
  - sandbox limitations & threat model
  - how to run experiments and reproduce results
- Add a sample `configs/binpacking.yaml` with comments

**Recommended Agent Profile**:
- Category: `writing`
- Skills: (none)

**Parallelization**: YES (Wave 4)

**Acceptance Criteria**:
- [ ] A new student can run the demo in <10 minutes using the README

---

## Commit Strategy (Optional but Recommended)

If using git, prefer multiple atomic commits (per `git-master` discipline):
1) Scaffold + test harness
2) Schemas + config
3) Store
4) Sandbox
5) Evaluator
6) LLM
7) Core loop
8) Experiments/CLI
9) Plotting + docs

---

## Success Criteria (Final)

### Verification Commands
```bash
pytest -q
python -m experiments.cli run configs/binpacking.yaml
```

### Final Checklist
- [ ] Deterministic evaluation (same seed ⇒ same scores)
- [ ] Multi-fidelity pipeline observed in logs (cheap for all, full for Top-K)
- [ ] Multi-model provenance recorded per candidate
- [ ] Metrics exported + matplotlib curves generated
- [ ] Sandbox blocks basic prohibited actions and enforces timeout
