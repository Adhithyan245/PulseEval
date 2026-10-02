# PulseEval Project Context

## CURRENT STATUS

Phase: 1 — Minimal Vertical Slice

Status: COMPLETE

Last completed:
End-to-end slice: fixture timeline → deterministic agent → structured trace → temporal-consistency evaluator → structured result + CLI report (tests passing).

Currently working on:
Nothing in progress.

Next task:
Phase 2 — add numerical-correctness evaluator (deterministic, tolerance-based) with its own fixture cases.

Blocked by:
None. (MMASH/PHIA ingestion needs user approval to download data; LLM-backed agent needs an API key.)

Last architecture change:
ADR-001 (flat modules instead of subpackages), ADR-002 (deterministic agent first), ADR-003 (fixture timeline before MMASH).

Last context update:
2026-10-02

---

## 1. Project Identity

PulseEval: Longitudinal Reliability Evaluation for Personal Health Agents.
A research prototype. The **evaluation layer** is the contribution; the agent is a small system under test (SUT).

## 2. Core Thesis

Personal-health agents can reason over longitudinal wearable data, but conventional QA metrics can miss failures involving stale memories, temporal inconsistency, unsupported causal claims, contradictory evidence, missing information, and inappropriate confidence. PulseEval provides a reproducible evaluation layer for detecting these failures.

## 3. Primary Objective

Answer: *How reliably does a personal-health AI agent reason over evolving longitudinal information?* — via deterministic-first evaluators that inspect the agent's structured trace, not only its final answer.

## 4. Explicit Non-Goals

Not a health chatbot, diagnosis/treatment/clinical-decision system, generic RAG app, dashboard, multi-agent framework, SaaS/cloud product, or large frontend. No unsupported clinical claims. No infrastructure (DBs, queues, vector stores, deployment).

## 5. Current Implementation Status

| Component | State |
|---|---|
| Timeline schema (`timeline.py`) | Implemented, tested |
| SUT agent (`agent.py`), 1 question intent (current training goal) | Implemented, tested |
| Agent trace schema | Implemented |
| Temporal-consistency evaluator (`evaluation.py`) | Implemented, tested |
| Scenarios (`scenarios.py`): 4 fixture cases | Implemented |
| CLI report (`python -m pulseeval`) | Implemented |
| Other evaluators, memory lifecycle, real datasets, LLM agent, UI | Not started |

## 6. Current Architecture

```text
Case (timeline + question + as_of + hand-labelled expectation)
  → HealthAgent.answer()            # SUT; tools: retrieve_context, latest_value
  → AgentTrace                      # structured, every tool call recorded
  → evaluate_temporal_consistency() # deterministic checks against case labels + timeline timestamps
  → EvaluationResult (checks + Failures)
  → CLI text report / JSON
```

Evaluators receive the case (ground truth) and the trace. They never call agent code to compute expected values.

## 7. Repository Structure

```text
PROJECT_CONTEXT.md   README.md   pyproject.toml   .gitignore
src/pulseeval/
  __init__.py
  __main__.py      # CLI: runs suite, prints report / JSON
  timeline.py      # Record, MemberTimeline (as-of semantics)
  agent.py         # SUT: tools, HealthAgent, ToolCall, AgentTrace
  evaluation.py    # FailureType, Failure, Check, EvaluationResult, evaluators, run_suite
  scenarios.py     # Case schema + fixture cases
tests/
  test_timeline.py
  test_evaluation.py
```
`data/raw/` and `data/processed/` are git-ignored and created only when a real dataset is ingested.

## 8. Data Sources

| Dataset | Status | Notes |
|---|---|---|
| Hand-written fixture (`scenarios.py`) | **In use** | Synthetic member M001; values are illustrative, not real measurements. |
| MMASH | Planned (Phase 5) | Not downloaded. Source, license, access conditions, and recording duration **not yet verified** — verify before use. Recording length per subject may limit how "longitudinal" derived timelines can be. |
| PHIA benchmark | Planned (Phase 5) | Not downloaded. Availability/license **not yet verified**. |

No raw data is committed to git.

## 9. Data Schemas

`Record`: `record_id, kind, name, value, unit?, event_time, recorded_at, source, confidence?`
- `kind` ∈ physiological, activity, sleep, subjective, context, goal, memory
- `event_time`: when the fact happened / became true. `recorded_at`: when it entered the system.
- **As-of rule:** a record is knowable at `as_of` iff `recorded_at <= as_of`. "Current" value of `name` = knowable record with the latest `event_time` (ties: `recorded_at`, then `record_id`).
- `known_as_of()` filters but does **not** sort; ordering is the agent's job and is what temporal evaluation tests.
- Updates are new records (no in-place mutation). Explicit `supersedes`/expiry deferred to Phase 3.

`MemberTimeline`: `member_id, records` (input order is *not* assumed meaningful).

`AgentTrace`: `agent_version, agent_config, query, member_id, as_of, time_window, retrieved_context, tools_called[ToolCall{name, inputs, outputs}], memories_used, evidence_used, final_answer, uncertainty, abstention`. `tools_called` carries tool inputs/outputs. Unused fields are explicit empty/null.

`EvaluationResult`: `case_id, evaluator, evaluator_version, passed, checks[Check], failures[Failure]`.
`Failure`: `failure_type, severity, query, expected_behavior, actual_behavior, evidence, trace, explanation`.

## 10. System Under Test

`HealthAgent(ordering, respect_as_of)` — deterministic, rule-based (no LLM yet).
- Reference config: `ordering="chronological", respect_as_of=True`.
- Fault-injected configs used to show evaluators discriminate: `input_order` (assumes input is sorted), `no_as_of` (ignores as-of; leaks future data).
- Supported intent: current training goal. Anything else → explicit abstention.

## 11. Evaluation Engine

Deterministic-first. LLM judges only where semantics require it, always with rubric + structured output + documented limitations; never ground truth. Evaluators are versioned (`*_VERSION` constants).

## 12. Evaluation Dimensions

| Dimension | Status |
|---|---|
| Temporal consistency | **Implemented** |
| Numerical/factual correctness | Planned (Phase 2, next) |
| Evidence grounding, contradiction, missing-data, causal restraint, uncertainty/abstention | Planned (Phase 2) |
| Memory validity | Planned (Phase 3) |
| Personalization, tool-call correctness | Planned (Phase 2–4) |

**Temporal consistency checks:**
1. `no_future_evidence` — no retrieved/cited record has `recorded_at` or `event_time` after `as_of`.
2. `uses_current_state` — the hand-labelled current record is among `evidence_used`.
3. `answer_states_current_value` — the final answer contains the expected value (case-insensitive substring).
Each failed check → one `TEMPORAL_FAILURE`. Evidence IDs not present in the timeline are ignored here (owned by the future grounding evaluator).

## 13. Adversarial Test Cases

Implemented (all: "what is my current training goal?", as_of 2026-04-01, expected = weight training):
- `goal_update_chronological` — marathon → weight training, records in order.
- `goal_update_reversed` — same, records reversed (temporal reversal).
- `goal_future_record` — a later goal recorded after as_of exists.
- `goal_late_arriving_record` — goal change with event_time < as_of but recorded_at > as_of.

Planned: stale memory, unsupported causality, contradictory signals, missing context, evidence mismatch, counterfactual.

## 14. Metrics

Per evaluator: pass rate = passed cases / evaluated cases. Plus failure counts by type. All numbers come from actual runs only.

## 15. Development Phases

0 Audit ✅ · 1 Vertical slice ✅ · 2 Core evaluation · 3 Memory evaluation · 4 Adversarial suite · 5 Benchmarking (PHIA/MMASH) · 6 Reporting · 7 UI · 8 Research extensions.

## 16. Completed Work

- Phase 0: empty directory audited; environment: Python 3.11, pydantic 2.9, pytest; no API key; no datasets.
- Phase 1: vertical slice (see §5). Observed run results are in the change log.

## 17. In-Progress Work

None.

## 18. Planned Work

1. Numerical-correctness evaluator + fixture cases with physiological series (tolerance-based).
2. Evidence-grounding evaluator (cited IDs exist and support claimed values).
3. Contradiction, missing-data, causal-restraint, uncertainty/abstention evaluators.
4. Optional LLM-backed agent behind the same `answer() -> AgentTrace` interface (requires API key).

## 19. Deferred Work

Real dataset ingestion (until download approved & licenses verified); LLM judge; memory lifecycle (Phase 3); reporting module (Phase 6); UI (Phase 7); pandas/numpy dependencies (until a numerical tool needs them).

## 20. Known Limitations

- Agent is rule-based; it validates the evaluator pipeline, not LLM behaviour.
- Fixture data is synthetic and tiny (1 member, 4 cases); results say nothing about real agents.
- `answer_states_current_value` is substring matching: a hedged or negated answer containing the value would pass.
- Only one question intent.

## 21. Research References

Mentioned as related work; citations **not yet verified** — verify before citing: PHIA, PHIA+, PH-LLM, Personal Health Agent, WHOOP public AI-evaluation engineering posts. No claim of novelty; no WHOOP internal access.

## 22. Architecture Decisions

### ADR-001 — Flat modules instead of subpackages

Status: Implemented
Date: 2026-10-02
Original approach: `src/pulseeval/{agent,data,evaluation,scenarios,reporting}/` subpackages.
New approach: one module per responsibility (`timeline.py`, `agent.py`, `evaluation.py`, `scenarios.py`); `__main__.py` holds the minimal report.
Reason: each responsibility is <150 lines; subpackages would be empty scaffolding.
Trade-offs: a module becomes a subpackage when it outgrows one file (expected for `evaluation.py`).
Affected components: repository structure.
Scope impact: Minor

### ADR-002 — Deterministic rule-based agent first

Status: Implemented
Date: 2026-10-02
Original approach: lightweight LLM-backed agent.
New approach: deterministic agent with fault-injection configs; LLM agent added later behind the same interface.
Reason: no API key available; deterministic SUT makes the evaluator itself testable (known-good and known-bad behaviour).
Trade-offs: does not exercise real LLM failure modes yet.
Affected components: agent.py
Scope impact: Minor

### ADR-003 — Hand-labelled fixture timeline before MMASH

Status: Implemented
Date: 2026-10-02
Original approach: first slice built on MMASH.
New approach: synthetic fixture in `scenarios.py` matching the canonical `Record` schema.
Reason: no dataset present; downloading requires user approval and license verification.
Trade-offs: no real data yet; schema must be re-validated against MMASH variables at ingestion.
Affected components: scenarios.py, data sources
Scope impact: Minor

## 23. Change Log

### 2026-10-02 — Phase 0 + Phase 1 vertical slice

Status: Implemented
Original plan: Phase 0 audit, then Phase 1 slice on one dataset.
Change: Slice built on fixture data with deterministic agent (ADR-001..003).
Reason: empty repo, no data, no API key.
Impact: During testing, `known_as_of()` initially sorted records, which masked the `input_order` fault (evaluator correctly reported a pass); fixed so retrieval preserves input order. Observed run after fix: reference agent 4/4 temporal consistency; `input_order` 3/4 (fails `goal_update_reversed`); `no_as_of` 2/4 (fails `goal_future_record`, `goal_late_arriving_record`).
Files affected: all initial files.
Scope impact: Minor

## 24. Rules for Future Changes

- Read CURRENT STATUS first; keep it true.
- Plan/architecture/scope changes: update this file (ADR + change log) **before** code.
- New file/dependency only with a concrete current purpose; record it in §7.
- Never report numbers that were not produced by a run.
- Version-bump `AGENT_VERSION` / `*_EVALUATOR_VERSION` / scenario changes when results could change.
