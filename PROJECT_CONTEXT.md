# PulseEval Project Context

## CURRENT STATUS

Phase: 2 — Core Evaluation

Status: IN PROGRESS (stopped for review)

Last completed:
Hardened temporal evaluator (clause-polarity answer check), numerical-correctness evaluator, MMASH/PHIA verification; 40 tests passing.

Currently working on:
Nothing — awaiting review.

Next task:
Proposed (needs approval; moves part of Phase 5 earlier): resolve PHIA answer→user mapping, then a minimal PHIA `summary_df` → `MemberTimeline` adapter feeding numeric cases. Alternative within current plan: evidence-grounding evaluator.

Blocked by:
None. Open question: PHIA objective answers have no user column — which synthetic user each answer refers to is unverified.

Last architecture change:
ADR-004 (evaluation subpackage), ADR-005 (clause-polarity answer check), ADR-006 (typed case union) — Implemented.

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

Not a health chatbot, diagnosis/treatment/clinical-decision system, generic RAG app, dashboard, multi-agent framework, SaaS/cloud product, or large frontend. No unsupported clinical claims. No infrastructure (DBs, queues, vector stores, deployment). No LLM agent or LLM judge until the deterministic evaluation layer is trustworthy (user decision, 2026-10-02).

## 5. Current Implementation Status

| Component | State |
|---|---|
| Timeline schema (`timeline.py`) | Implemented, tested |
| SUT agent v0.2.0 (`agent.py`): intents = current training goal, N-day mean resting HR | Implemented, tested |
| Agent trace schema | Implemented |
| Temporal-consistency evaluator v0.2.0 | Implemented, tested (incl. adversarial answer texts) |
| Numerical-correctness evaluator v0.1.0 | Implemented, tested |
| Scenarios v0.2.0: 4 state + 2 numeric fixture cases | Implemented |
| CLI report (`python -m pulseeval`) | Implemented |
| PHIA / MMASH | Verified (§8); PHIA sample inspected locally; no loader |
| Other evaluators, memory lifecycle, LLM agent, UI | Not started |

## 6. Current Architecture

```text
Case = StateCase | NumericCase (timeline + question + as_of + hand-labelled expectation)
  → HealthAgent.answer()          # SUT; tools: retrieve_context, latest_value, mean_value
  → AgentTrace                    # structured; every tool call recorded
  → run_suite dispatch by kind:
      StateCase   → evaluate_temporal_consistency()
      NumericCase → evaluate_numerical_correctness()
  → EvaluationResult (checks tagged by aspect: temporal / evidence / answer; typed Failures)
  → CLI text report / JSON
```

Evaluators receive the case (ground truth) and the trace. They never call agent code to compute expected values. Answer-text analysis is shared in `evaluation/text.py`.

## 7. Repository Structure

```text
PROJECT_CONTEXT.md   README.md   pyproject.toml   .gitignore
src/pulseeval/
  __init__.py
  __main__.py          # CLI: runs suite, prints report / JSON
  timeline.py          # Record, MemberTimeline (as-of semantics)
  agent.py             # SUT: tools, HealthAgent, ToolCall, AgentTrace
  scenarios.py         # StateCase, NumericCase, fixture cases
  evaluation/
    __init__.py        # run_suite (dispatch by case kind)
    schemas.py         # FailureType, Check, Failure, EvaluationResult, CheckSpec, build_result
    text.py            # deterministic answer-text analysis (clauses, polarity, numbers+unit)
    temporal.py        # temporal-consistency evaluator, unknowable_records helper
    numerical.py       # numerical-correctness evaluator
tests/
  test_timeline.py   test_temporal.py   test_numerical.py
data/raw/            # git-ignored; local copies only (currently: data/raw/phia/ sample)
```

## 8. Data Sources

Verified 2026-10-02 by reading official pages (and, for PHIA, inspecting a 4-file local sample). Not legal advice; re-check before redistribution.

| Dataset | Status |
|---|---|
| Hand-written fixture (`scenarios.py`) | **In use.** Synthetic member M001; values illustrative. |
| PHIA | Verified; small sample in `data/raw/phia/` (git-ignored). No loader. Priority 1. |
| MMASH | Verified from PhysioNet page; **not downloaded**. Priority 2. |

### PHIA — Personal Health Insights Agent

- **Source:** https://github.com/yahskapar/personal-health-insights-agent (a co-author's personal account; web research found the paper's availability statement points here). Paper: Merrill et al., "Transforming wearable data into personal health insights using large language model agents", arXiv:2406.06464 (verified). Nature Communications version (DOI 10.1038/s41467-025-67922-y) seen only via a search snippet — details **unverified**.
- **License:** repo `LICENSE` file is "Attribution-NonCommercial 4.0 International" (CC BY-NC 4.0) — read directly. GitHub's license detector reports `NOASSERTION`. Redistribution with attribution, **non-commercial only**. No separate data terms found.
- **Access:** public GitHub, no login; individual files fetchable via raw.githubusercontent.com. Repo ≈ 29 MB (GitHub API), incl. an 11.9 MB `teaser.gif`.
- **Structure (inspected locally):**
  - `Objective Query - PHIA.xlsx` (90 KB): one sheet, columns `Question`, `Answer`; 4000 questions; 3943 numeric answers (400 exactly 0.0), 57 non-numeric (activity names, e.g. "Run"); 855 duplicate question strings. **No user-id column** → which user each answer refers to is unverified.
  - `Open-Ended Query - PHIA.xlsx` (11 KB): 172 questions, no ground truth.
  - `synthetic_wearable_users/` (117 files, 295 KB): `summary_df_<id>.csv` (daily: resting_heart_rate, heart_rate_variability, active zone minutes, steps, sleep stage minutes/percents, bed/wake time, stress_management_score, demographics) and `exercise_df_<id>.csv` (per session: activityName, start/end, duration, averageHeartRate, distance, calories, …).
  - User 465 sample: 29 daily rows spanning 2023-10-01 → 2023-10-31 (**2 missing days**), 16 empty cells; 11 exercise sessions.
  - Also `real_wearable_users/` (4 de-identified users) and `data/` (human-eval / labeling sheets, up to 4.3 MB) — not downloaded.
- **Contribution to PulseEval:** numeric objective questions for the numerical evaluator; daily summaries map naturally onto `Record` (kind physiological/sleep/activity, event_time = date); natural gaps support missing-data cases.
- **Limitations:** ~1 month of daily aggregates per user; no intraday data; no goals/subjective reports/context events (stale-memory and contradiction scenarios still need synthetic overlays); answer→user mapping unknown; synthetic users are model-generated; non-commercial license.

### MMASH — Multilevel Monitoring of Activity and Sleep in Healthy people

- **Source:** https://physionet.org/content/mmash/1.0.0/ (v1.0.0, 2020-06-19), DOI 10.13026/cerq-fc86. Citation: Rossi A, Da Pozzo E, Menicagli D, Tremolanti C, Priami C, Sirbu A, Clifton D, Martini C, Morelli D. (2020).
- **License/access:** Open Data Commons ODbL v1.0; PhysioNet Open Access (no login/DUA). ODbL permits redistribution with attribution and share-alike for derived databases (general ODbL terms).
- **Download:** automatic possible — 22.7 MB ZIP, or `wget -r -N -c -np https://physionet.org/files/mmash/1.0.0/`. Not downloaded yet.
- **Structure:** 22 healthy young adult males; ~24 h per subject (spanning 2 calendar days). Per-user files: `user_info.csv`, `RR.csv` (ibi_s, day, time), `Actigraph.csv` (axes, steps, HR, inclinometer), `sleep.csv` (onset, efficiency, TST, WASO, …), `Activity.csv` (coded activities incl. caffeine/alcohol/screen), `questionnaire.csv` (MEQ, STAI, PSQI, PANAS, daily stress), `saliva.csv` (cortisol/melatonin; missing for user_21).
- **Contribution to PulseEval:** high-resolution physiology + subjective questionnaires + activity/context log → contradiction (wearable vs self-report) and missing-context scenarios; intraday temporal ordering.
- **Limitations:** ~1 day per subject — **not longitudinal across days**; small, homogeneous cohort.

## 9. Data Schemas

`Record`: `record_id, kind, name, value, unit?, event_time, recorded_at, source, confidence?`
- `kind` ∈ physiological, activity, sleep, subjective, context, goal, memory
- `event_time`: when the fact happened / became true. `recorded_at`: when it entered the system.
- **As-of rule:** a record is knowable at `as_of` iff `recorded_at <= as_of`. "Current" value of `name` = knowable record with the latest `event_time` (ties: `recorded_at`, then `record_id`).
- `known_as_of()` filters but does **not** sort; ordering is the agent's job and is what temporal evaluation tests.
- Updates are new records (no in-place mutation). Explicit `supersedes`/expiry deferred to Phase 3.

`MemberTimeline`: `member_id, records` (input order is *not* assumed meaningful).

`StateCase`: `case_id, description, timeline, question, as_of, target_name, expected_record_id, expected_value`.
`NumericCase`: same base + `expected_value: float, unit, tolerance (absolute), expected_record_ids`.

`AgentTrace`: `agent_version, agent_config, query, member_id, as_of, time_window, retrieved_context, tools_called[ToolCall{name, inputs, outputs}], memories_used, evidence_used, final_answer, uncertainty, abstention`.

`Check`: `name, aspect, passed, explanation`. `EvaluationResult`: `case_id, evaluator, evaluator_version, passed, checks, failures`.
`Failure`: `failure_type, check, aspect, severity, query, expected_behavior, actual_behavior, evidence, trace, explanation`.

## 10. System Under Test

`HealthAgent(ordering, respect_as_of, respect_window)` v0.2.0 — deterministic, rule-based (no LLM; ADR-002, reaffirmed by user).
- Reference config: chronological, respects as_of, respects window.
- Fault-injected configs: `input_order` (assumes sorted input), `no_as_of` (retrieves unknowable records), `no_window` (aggregates all history).
- Intents: "current training goal"; "average resting heart rate over the last N days". Anything else → explicit abstention.

## 11. Evaluation Engine

Deterministic-first. No LLM judge yet. Evaluators are versioned (`*_EVALUATOR_VERSION`). Every check is tagged with an **aspect** so failures separate:
- **temporal** — was anything used that was unknowable at as_of?
- **evidence** — did the agent cite the right records?
- **answer** — does the final text assert the right thing?

## 12. Evaluation Dimensions

| Dimension | Status |
|---|---|
| Temporal consistency | **Implemented** v0.2.0 |
| Numerical/factual correctness | **Implemented** v0.1.0 |
| Evidence grounding, contradiction, missing-data, causal restraint, uncertainty/abstention | Planned (Phase 2) |
| Memory validity | Planned (Phase 3) |
| Personalization, tool-call correctness | Planned (Phase 2–4) |

**Temporal consistency (StateCase)** — all failures `TEMPORAL_FAILURE`:
1. `no_future_evidence` [temporal] — no retrieved/cited record has `recorded_at` or `event_time` after as_of.
2. `evidence_includes_current_record` [evidence] — the labelled current record is in `evidence_used`.
3. `answer_asserts_current_value` [answer] — the current value is *affirmed* in some clause.
4. `answer_does_not_assert_other_value` [answer] — no other value of the same field (from the timeline) is affirmed.

**Answer-text analysis (`text.py`, ADR-005):** sentences split on `.;!?` (not decimal points); a new clause starts at contrast cues (but, however, although, instead of, rather than, …) and at *contrastive* negation only (`, not` / `and not` / `, no longer`); otherwise negation scopes over its whole clause. "switched/changed … from X to Y" → X is past. Mention = the value's content tokens appear contiguously and in order (light plural stemming). Polarity priority: negated > past > hedged > affirmed. Hedged mentions do not count as assertions.

**Numerical correctness (NumericCase):**
1. `no_future_evidence` [temporal] → `TEMPORAL_FAILURE`.
2. `evidence_matches_expected_readings` [evidence] → `NUMERICAL_FAILURE`; cited ids == labelled ids.
3. `value_extracted` [answer] → `NUMERICAL_FAILURE`; exactly one distinct *affirmed* number immediately followed by the unit.
4. `value_within_tolerance` [answer] → `NUMERICAL_FAILURE`; `|actual − expected| ≤ tolerance` (absolute, + 1e-9 float epsilon).

## 13. Adversarial Test Cases

Suite cases (as_of 2026-04-01):
- `goal_update_chronological`, `goal_update_reversed`, `goal_future_record`, `goal_late_arriving_record` — expected current goal "weight training" (g2).
- `rhr_mean_7d` — 7 daily readings, older readings outside the window; expected 384/7 ≈ 54.857 bpm, tolerance 0.1.
- `rhr_mean_7d_late_sync` — last reading (62 bpm) recorded after as_of; expected 330/6 = 55.0 bpm (leaking it gives 56.0).

Adversarial answer texts (unit tests, injected into an otherwise-correct trace): negated, past-framed, hedged, stale, both values, "X is not your goal; it is Y" → fail; "Y, not X", "switched from X to Y", "Y. No longer X", "Previously X; now Y" → pass. Numeric: wrong value, no unit, range, hedged, negated → fail; "Not 60 bpm, but 54.9 bpm" → pass.

Planned: stale memory, unsupported causality, contradictory signals, missing context, evidence mismatch, counterfactual.

## 14. Metrics

Per evaluator: pass rate = passed cases / evaluated cases. Plus failures by type and aspect. All numbers come from actual runs only.

## 15. Development Phases

0 Audit ✅ · 1 Vertical slice ✅ · 2 Core evaluation (in progress: temporal hardened ✅, numerical ✅) · 3 Memory evaluation · 4 Adversarial suite · 5 Benchmarking (PHIA/MMASH) · 6 Reporting · 7 UI · 8 Research extensions.

## 16. Completed Work

- Phase 0: empty directory audited; Python 3.11, pydantic 2.9, pytest; no API key; no datasets.
- Phase 1: vertical slice. Committed `b40e90c`.
- Phase 2 (partial): temporal evaluator hardened; numerical evaluator; dataset verification.

## 17. In-Progress Work

None (stopped for review).

## 18. Planned Work

1. (Proposed, needs approval — moves part of Phase 5 earlier) Resolve PHIA answer→user mapping from the repo's code (`data_utils.py`, `phia_demo.ipynb`); if unresolvable, recompute ground truth for a few template questions ourselves. Then a minimal `summary_df` → `MemberTimeline` adapter feeding `NumericCase`s.
2. Evidence-grounding evaluator (cited IDs exist and support claimed values).
3. Contradiction, missing-data, causal-restraint, uncertainty/abstention evaluators.

## 19. Deferred Work

LLM-backed agent and LLM judge (until the deterministic layer is trusted — user decision); MMASH download (priority 2); full PHIA download/loader; memory lifecycle (Phase 3); reporting module (Phase 6); UI (Phase 7); pandas/numpy/openpyxl dependencies (PHIA xlsx was inspected with stdlib `zipfile`; add `openpyxl` only if a loader needs it).

## 20. Known Limitations

- Agent is rule-based; it validates the evaluator pipeline, not LLM behaviour.
- Fixture data is synthetic and tiny (1 member, 6 cases); results say nothing about real agents.
- Answer-text analysis is lexical English heuristics: misses paraphrases of values ("training for a marathon" ≠ "marathon training"), sarcasm, conditionals, cross-sentence negation ("That's not it." referring back), and cue words used in non-negating senses. It errs toward failing answers it cannot parse.
- Number extraction requires the unit immediately after the number ("54.9 bpm"); spelled-out numbers are not supported.
- Numeric tolerance is absolute only.
- Two question intents.

## 21. Research References

- PHIA: Merrill MA, Paruchuri A, Rezaei N, et al. "Transforming wearable data into personal health insights using large language model agents." arXiv:2406.06464 (verified). Journal version in Nature Communications — details unverified.
- MMASH: Rossi A et al. (2020), PhysioNet, DOI 10.13026/cerq-fc86 (verified).
- Not yet verified — verify before citing: PHIA+, PH-LLM, Personal Health Agent, WHOOP public AI-evaluation engineering posts. No claim of novelty; no WHOOP internal access.

## 22. Architecture Decisions

### ADR-001 — Flat modules instead of subpackages

Status: Implemented (partly superseded by ADR-004)
Date: 2026-10-02
Original approach: `src/pulseeval/{agent,data,evaluation,scenarios,reporting}/` subpackages.
New approach: one module per responsibility (`timeline.py`, `agent.py`, `evaluation.py`, `scenarios.py`); `__main__.py` holds the minimal report.
Reason: each responsibility is <150 lines; subpackages would be empty scaffolding.
Trade-offs: a module becomes a subpackage when it outgrows one file (expected for `evaluation.py`).
Affected components: repository structure.
Scope impact: Minor

### ADR-002 — Deterministic rule-based agent first

Status: Implemented (reaffirmed by user 2026-10-02)
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
Trade-offs: no real data yet; schema must be re-validated against dataset variables at ingestion.
Affected components: scenarios.py, data sources
Scope impact: Minor

### ADR-004 — Split evaluation into a subpackage

Status: Implemented
Date: 2026-10-02
Original approach: single `evaluation.py` (ADR-001).
New approach: `evaluation/` with `schemas.py` (taxonomy + result models), `text.py` (deterministic answer-text analysis), `temporal.py`, `numerical.py`; `__init__.py` holds `run_suite` (dispatch by case kind).
Reason: second evaluator + shared text analysis would push one file past readability; anticipated by ADR-001.
Trade-offs: more files; each has one responsibility.
Affected components: evaluation, tests, CLI.
Scope impact: Minor

### ADR-005 — Clause-polarity answer check replaces substring match

Status: Implemented
Date: 2026-10-02
Original approach: answer passes if the expected value is a case-insensitive substring.
New approach: split the answer into clauses (sentence punctuation + contrast cues + contrastive negation only); a value is *mentioned* in a clause when its content tokens occur there contiguously and in order; each mention is classified negated / past / hedged / affirmed by cue words. Answer correct iff the current value is affirmed somewhere and no other known value of the same field is affirmed. "switched from X to Y" is rewritten so X is past. Two revisions during implementation: splitting before every "not" mis-scoped "Weight training is not your goal"; unordered token-subset matching falsely matched "marathon training" in "training goal is half marathon".
Reason: substring passed negated/hedged/stale answers (real evaluator weakness).
Trade-offs: lexical heuristics, English-only, no NLP library/LLM judge. Known gaps in §20; hedged answers deliberately fail (an answer must assert the current state).
Affected components: evaluation/text.py, evaluation/temporal.py, evaluation/numerical.py.
Scope impact: Minor

### ADR-006 — Typed case union

Status: Implemented
Date: 2026-10-02
Original approach: one `Case` model for current-state questions.
New approach: `StateCase` and `NumericCase` (discriminated by `kind`); `run_suite` dispatches the temporal vs numerical evaluator by kind.
Reason: numeric cases need expected float, unit, tolerance, expected readings.
Trade-offs: none significant.
Affected components: scenarios.py, evaluation.
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

### 2026-10-02 — Hardened temporal evaluator, numerical evaluator, dataset verification

Status: Implemented
Original plan: Phase 2 starts with numerical correctness; temporal answer check = substring.
Change (user-directed): temporal answer check hardened first (ADR-005); checks tagged by aspect temporal/evidence/answer; numerical evaluator added; evaluation split into a subpackage (ADR-004); case union (ADR-006); agent v0.2.0 adds mean-RHR intent + `no_window` fault; scenarios v0.2.0 add 2 numeric cases; MMASH and PHIA verified; PHIA sample (4 small files) stored in git-ignored `data/raw/phia/`.
Reason: substring check passed negated/hedged/stale answers.
Impact: Bugs found and fixed during this work: (1) clause splitting before every "not" mis-scoped subject negation; (2) unordered token matching gave a false stale-value match from template text "training goal"; (3) the first late-sync case was detected only via float noise at the tolerance boundary — case value changed to 62 bpm and a 1e-9 epsilon added. Observed runs: reference temporal 4/4, numerical 2/2; `input_order` 3/4, 2/2; `no_as_of` 2/4, 1/2; `no_window` 4/4, 0/2. 40 tests pass.
Files affected: agent.py, scenarios.py, __main__.py, evaluation/* (new), tests/test_temporal.py (renamed from test_evaluation.py), tests/test_numerical.py (new), README.md, PROJECT_CONTEXT.md.
Scope impact: Minor

## 24. Rules for Future Changes

- Read CURRENT STATUS first; keep it true.
- Plan/architecture/scope changes: update this file (ADR + change log) **before** code.
- New file/dependency only with a concrete current purpose; record it in §7.
- Never report numbers that were not produced by a run.
- Version-bump `AGENT_VERSION` / `*_EVALUATOR_VERSION` / `SCENARIOS_VERSION` when results could change.
- No LLM agent/judge and no UI without explicit user approval.
