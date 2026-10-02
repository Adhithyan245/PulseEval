# PulseEval Project Context

## CURRENT STATUS

Phase: 2 — Core Evaluation

Status: IN PROGRESS (stopped for review)

Last completed:
PHIA mapping investigation (persona↔user supported; labels not reproducible → not ground truth); evaluators split into temporal / evidence grounding / answer; evidence-grounding evaluator; minimal PHIA adapter with 2 recomputed cases. 56 tests pass (53 without local PHIA data).

Currently working on:
Nothing — awaiting review.

Next task:
Missing-data handling evaluator (Phase 2), using PHIA user 465's natural gaps plus fixture cases.

Blocked by:
None.

Last architecture change:
ADR-007 (PHIA labels not ground truth; minimal adapter), ADR-008 (one evaluator per dimension; evidence grounding) — Implemented.

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
| Temporal-consistency evaluator v0.3.0 (knowability only) | Implemented, tested |
| Evidence-grounding evaluator v0.1.0 | Implemented, tested |
| Answer-correctness evaluator v0.2.0 (state + numeric) | Implemented, tested |
| Scenarios v0.3.0: 4 state + 2 numeric fixture cases, each with `provenance` | Implemented |
| PHIA adapter (`phia.py`): 1 user, 2 numeric cases, PulseEval-recomputed values | Implemented, tested (skips without local data) |
| CLI report (`python -m pulseeval [--phia DIR]`) | Implemented |
| MMASH | Verified (§8); not downloaded |
| Contradiction/causal/missing-data/uncertainty evaluators, memory lifecycle, LLM agent, UI | Not started |

## 6. Current Architecture

```text
Case = StateCase | NumericCase   (fixture: scenarios.py | PHIA-derived: phia.py)
  timeline + question + as_of + target_name + expectation + provenance
  → HealthAgent.answer()          # SUT; tools: retrieve_context, latest_value, mean_value
  → AgentTrace                    # structured; every tool call recorded
  → run_suite: every case × every evaluator
      temporal_consistency   — was anything retrieved/cited unknowable at as_of?
      evidence_grounding     — is the cited evidence the right evidence for the claim?
      answer_correctness     — does the final text assert the right thing?
  → EvaluationResult per (case, evaluator): checks + typed Failures
  → CLI text report / JSON
```

Evaluators receive the case (expectations) and the trace; they never call agent code to compute expected values. A trace can fail any dimension independently (see §12 separation examples). Answer-text analysis is shared in `evaluation/text.py`.

## 7. Repository Structure

```text
PROJECT_CONTEXT.md   README.md   pyproject.toml   .gitignore
src/pulseeval/
  __init__.py
  __main__.py          # CLI: runs suite, prints report / JSON; --phia DIR adds PHIA cases
  timeline.py          # Record, MemberTimeline (as-of semantics)
  agent.py             # SUT: tools, HealthAgent, ToolCall, AgentTrace
  scenarios.py         # StateCase, NumericCase, fixture cases
  phia.py              # minimal PHIA adapter: summary CSV -> MemberTimeline + 2 NumericCases
  evaluation/
    __init__.py        # EVALUATORS, run_suite
    schemas.py         # FailureType, Check, Failure, EvaluationResult, CheckSpec, build_result
    text.py            # deterministic answer-text analysis (clauses, polarity, numbers+unit)
    temporal.py        # temporal consistency (knowability)
    grounding.py       # evidence grounding
    answer.py          # answer correctness (state + numeric)
tests/
  test_timeline.py  test_temporal.py  test_grounding.py  test_answer.py  test_suite.py  test_phia.py
data/raw/            # git-ignored; local copies only (data/raw/phia/: 14 files, ~700 KB)
```

## 8. Data Sources

Verified 2026-10-02 by reading official pages and the PHIA repository's code/data. Not legal advice; re-check before redistribution.

| Dataset | Status |
|---|---|
| Hand-written fixture (`scenarios.py`) | **In use.** Synthetic member M001; values illustrative. |
| PHIA | **In use (limited).** Local sample in `data/raw/phia/` (git-ignored). PHIA labels are *not* used as ground truth (ADR-007). |
| MMASH | Verified from PhysioNet page; **not downloaded**. Priority 2. |

### PHIA — Personal Health Insights Agent

- **Source:** https://github.com/yahskapar/personal-health-insights-agent (a co-author's account; README calls it "the official repository for the paper"). Paper: Merrill et al., arXiv:2406.06464 (verified). Nature Communications version (DOI 10.1038/s41467-025-67922-y) seen only via a search snippet — details **unverified**. README notes a successor, Personal Health Agent (PHA): https://github.com/Google-Health/consumer-health-research/tree/main/personal_health_agent, arXiv:2508.20148 — not inspected.
- **License:** CC BY-NC 4.0 (repo `LICENSE` file and README). Attribution, **non-commercial only**. GitHub's detector reports `NOASSERTION`.
- **Access:** public GitHub, no login; individual files fetchable via raw.githubusercontent.com.
- **Local sample (`data/raw/phia/`, git-ignored, downloaded 2026-10-02):** `objective_queries.xlsx`, `open_ended_queries.xlsx`, `{health_behavior,sedentary_sleeper,inactive_insomniacs,active_achiver}_final_v2.csv`, `summary_df_{465,333,171,41}.csv`, `exercise_df_{465,333,171,41}.csv`.

**Question → user → data mapping investigation (2026-10-02):**
1. `Objective Query - PHIA.xlsx`: columns `Question`, `Answer` only; 4000 rows; no user column. It is *not* an ordered or exact (question,label) concatenation of the four persona files (only 2204/4000 positional label matches) — its provenance relative to them is unresolved.
2. `data/auto_eval/<persona>_final_v2.csv` (4 files × 1000 rows): columns `question`, `label`, `code` (the pandas expression that generated the label). `figs/3a.ipynb` loads each as the ground-truth file (`gt_path`) for that persona.
3. No PHIA code maps persona → user id. README: "Subject 465, 333, 171, and 41 are used in evaluation". Filenames in `data/human_label_experiments/` pair ids with persona names (`465_HealthBehaviorChampions`, `333_SedentarySleepers`, `171_InactiveInsomniacs`, `41_ActiveAchieversLowZzzs`).
4. **Empirical check (PHIA code strings never executed):** for the narrow template `daily_metrics.during('last N days')[col].{mean,sum,max,min,median,std}()`, labels were recomputed independently from each candidate user's `summary_df` using PHIA's own window rule (`data_utils.py`: reference = last date in data; window = N days ending there, inclusive). Matches (|Δ| ≤ 0.01 at 2 dp):

   | persona file | 465 | 333 | 171 | 41 |
   |---|---|---|---|---|
   | health_behavior | **113/278** | 0 | 0 | 0 |
   | sedentary_sleeper | 1 | **121/335** | 0 | 0 |
   | inactive_insomniacs | 0 | 0 | **221/364** | 3 |
   | active_achiver | 0 | 0 | 2 | **121/350** |

   → persona ↔ user mapping is **supported** (unique diagonal, agrees with filenames).
5. **But labels are not reproducible**: even for the matched user, most mean/sum/median/std labels disagree; min/max mostly agree. Alternative window rules (PHIA `last_days_alt`; last N rows) do not fix it (best 66%). Example: user 465, 7-day mean resting HR, all 7 readings present → 61.634 recomputed vs **61.18** PHIA label. Most likely the labels were computed on data that differs from the published CSVs — **unverified**; cause unknown.

**Decision (ADR-007):** PHIA labels are a reference resource, **not ground truth** in PulseEval. PHIA timelines are used with expected values recomputed by PulseEval, provenance recorded on each case.

- **Structure:** `synthetic_wearable_users/` (117 files): `summary_df_<id>.csv` daily (resting_heart_rate, heart_rate_variability, AZM, steps, sleep stage minutes/percents, bed/wake time, stress_management_score, demographics) and `exercise_df_<id>.csv` per session. Evaluation users span 2023-10-01/02 → 2023-10-31 with gaps: 465 = 29 days (missing 10-12, 10-21), 333 = 28, 171 = 21, 41 = 28. `data/auto_eval/*shots*.csv` are 13–40 MB model outputs (not downloaded).
- **Contribution to PulseEval:** realistic daily timelines with natural gaps (missing-data cases); question templates; persona variety.
- **Limitations:** ~1 month daily aggregates; no ingestion timestamps (adapter assumes recorded_at = event_time); no goals/subjective/context events; synthetic users model-generated; non-commercial license; published labels not reproducible.

### MMASH — Multilevel Monitoring of Activity and Sleep in Healthy people

- **Source:** https://physionet.org/content/mmash/1.0.0/ (v1.0.0, 2020-06-19), DOI 10.13026/cerq-fc86. Citation: Rossi A, Da Pozzo E, Menicagli D, Tremolanti C, Priami C, Sirbu A, Clifton D, Martini C, Morelli D. (2020).
- **License/access:** Open Data Commons ODbL v1.0; PhysioNet Open Access (no login/DUA). ODbL permits redistribution with attribution and share-alike for derived databases (general ODbL terms).
- **Download:** automatic possible — 22.7 MB ZIP, or `wget -r -N -c -np https://physionet.org/files/mmash/1.0.0/`. Not downloaded.
- **Structure:** 22 healthy young adult males; ~24 h per subject. Per-user `user_info.csv`, `RR.csv`, `Actigraph.csv`, `sleep.csv`, `Activity.csv`, `questionnaire.csv`, `saliva.csv`.
- **Contribution:** wearable vs self-report contradiction and missing-context scenarios; intraday ordering.
- **Limitations:** ~1 day per subject — not longitudinal across days; small, homogeneous cohort.

## 9. Data Schemas

`Record`: `record_id, kind, name, value, unit?, event_time, recorded_at, source, confidence?`
- `kind` ∈ physiological, activity, sleep, subjective, context, goal, memory
- `event_time`: when the fact happened / became true. `recorded_at`: when it entered the system.
- **As-of rule:** knowable at `as_of` iff `recorded_at <= as_of`. "Current" value of `name` = knowable record with the latest `event_time` (ties: `recorded_at`, then `record_id`).
- `known_as_of()` filters but does **not** sort.
- Updates are new records. `supersedes`/expiry deferred to Phase 3.

`MemberTimeline`: `member_id, records` (input order not meaningful).

Case base: `case_id, description, timeline, question, as_of, target_name, provenance`.
`StateCase`: + `expected_record_id, expected_value: str`. Valid evidence window: event_time ≤ as_of.
`NumericCase`: + `window_start, expected_value: float, unit, tolerance (absolute), expected_record_ids`. Aggregate is the mean over [window_start, as_of].

`AgentTrace`: `agent_version, agent_config, query, member_id, as_of, time_window, retrieved_context, tools_called[ToolCall{name, inputs, outputs}], memories_used, evidence_used, final_answer, uncertainty, abstention`.

`Check`: `name, passed, explanation`. `EvaluationResult`: `case_id, evaluator, evaluator_version, passed, checks, failures`.
`Failure`: `failure_type, check, severity, query, expected_behavior, actual_behavior, evidence, trace, explanation`.

## 10. System Under Test

`HealthAgent(ordering, respect_as_of, respect_window)` v0.2.0 — deterministic, rule-based (no LLM; ADR-002, reaffirmed by user).
- Reference config: chronological, respects as_of, respects window.
- Fault-injected configs: `input_order` (assumes sorted input), `no_as_of` (retrieves unknowable records), `no_window` (aggregates all history).
- Intents: "current training goal"; "average resting heart rate over the last N days" (window = [as_of − N days, as_of]). Anything else → explicit abstention.

## 11. Evaluation Engine

Deterministic-first. No LLM judge. Evaluators are versioned (`*_EVALUATOR_VERSION`). Three independent dimensions (ADR-008), each its own evaluator, all run on every case.

## 12. Evaluation Dimensions

| Dimension | Status |
|---|---|
| Temporal consistency | **Implemented** v0.3.0 |
| Evidence grounding | **Implemented** v0.1.0 |
| Answer correctness (numerical + current-state) | **Implemented** v0.2.0 |
| Contradiction handling (wearable vs self-report), missing-data, causal restraint, uncertainty/abstention | Planned (Phase 2) |
| Memory validity | Planned (Phase 3) |
| Personalization, tool-call correctness | Planned (Phase 2–4) |

**temporal_consistency** — `TEMPORAL_FAILURE`:
- `no_unknowable_records` — nothing retrieved or cited has `recorded_at` or `event_time` after as_of.

**evidence_grounding** — `GROUNDING_FAILURE`:
- `cited_records_exist` — no fabricated ids.
- `cites_required_records` — labelled required records are all cited (missing evidence).
- `cited_records_relevant` — cited records are `target_name` (and the case unit, for numeric) (wrong evidence).
- `cited_records_within_window` — cited event_times in [window_start, as_of] (numeric) or ≤ as_of (state) (temporally invalid evidence).
- `evidence_supports_claim` — numeric: affirmed value = mean of cited relevant readings ± tolerance; state: every value asserted as current appears in a cited record. Passes vacuously when there is no single claim (answer_correctness owns that).
- `no_contradicting_evidence` (state only) — no cited relevant record whose value the answer neither asserts nor explicitly frames (past/negated) while a claim is made.

**answer_correctness**:
- State (`TEMPORAL_FAILURE`): `answer_asserts_current_value`; `answer_does_not_assert_other_value`.
- Numeric (`NUMERICAL_FAILURE`): `value_extracted` (exactly one distinct affirmed number + unit); `value_within_tolerance` (absolute + 1e-9 epsilon).

**Answer-text analysis (`text.py`, ADR-005):** sentences split on `.;!?` (not decimal points); new clause at contrast cues and contrastive negation only; "switched … from X to Y" → X past; mention = contiguous, ordered content tokens; polarity negated > past > hedged > affirmed; hedged mentions are not assertions.

**Separation examples (observed):** `no_window` → grounding + answer fail, temporal passes (wrong window, nothing unknowable; the claim is faithful to its own evidence). `no_as_of` on late-sync → temporal + answer fail, grounding passes (leaked reading is relevant and in-window). Retrieving-but-not-citing a future record → temporal fails only. Fabricated citation alongside correct evidence → grounding fails only.

## 13. Adversarial Test Cases

Fixture suite (as_of 2026-04-01): `goal_update_chronological`, `goal_update_reversed`, `goal_future_record`, `goal_late_arriving_record` (expected "weight training", g2); `rhr_mean_7d` (384/7 ≈ 54.857 bpm, tol 0.1); `rhr_mean_7d_late_sync` (330/6 = 55.0; leaking gives 56.0).

PHIA-derived (user 465, as_of 2023-11-01, tol 0.05): `phia465_rhr_mean_7d` (61.634286, 7 readings), `phia465_rhr_mean_14d` (59.649231, 13 readings — 2023-10-21 missing in source, not imputed).

Unit-test perturbations: adversarial answer texts (negated, past, hedged, stale, both values, ranges, missing unit); grounding perturbations (fabricated id, irrelevant in-window record, wrong record type, missing reading, no evidence, out-of-window reading, future record cited as support, unsupported numeric claim, stale record silently cited vs explicitly framed).

Planned: stale memory, unsupported causality, contradictory signals (wearable vs self-report), missing context, counterfactual.

## 14. Metrics

Per evaluator: pass rate = passed cases / evaluated cases; failures by type and check. All numbers come from actual runs only.

## 15. Development Phases

0 Audit ✅ · 1 Vertical slice ✅ · 2 Core evaluation (in progress: temporal ✅, grounding ✅, answer/numerical ✅; remaining: contradiction, missing-data, causal restraint, uncertainty/abstention) · 3 Memory evaluation · 4 Adversarial suite · 5 Benchmarking (PHIA/MMASH) · 6 Reporting · 7 UI · 8 Research extensions.

## 16. Completed Work

- Phase 0: empty directory audited; Python 3.11, pydantic 2.9, pytest; no API key.
- Phase 1: vertical slice.
- Phase 2 (partial): temporal answer check hardened; numerical evaluator; dataset verification; PHIA mapping investigation; evaluators split by dimension; evidence grounding; minimal PHIA adapter.
- Git: `origin` = https://github.com/Adhithyan245/PulseEval.git; history rewritten 2026-10-02 to remove Claude co-author trailers (user decision); commits use the user's identity only.

## 17. In-Progress Work

None (stopped for review).

## 18. Planned Work

1. Missing-data handling evaluator (agent must report/acknowledge gaps, e.g. "13 of 14 days"; no imputation claims) — PHIA user 465's missing days give a natural case.
2. Contradiction handling (wearable vs self-report), causal restraint, uncertainty/abstention evaluators.

## 19. Deferred Work

LLM-backed agent and LLM judge (until the deterministic layer is trusted — user decision); MMASH download; using PHIA labels (not reproducible); more PHIA users/templates; PHA (successor) inspection; memory lifecycle (Phase 3); reporting module (Phase 6); UI (Phase 7); pandas/numpy/openpyxl.

## 20. Known Limitations

- Agent is rule-based; it validates the evaluator pipeline, not LLM behaviour.
- Data is tiny: 6 synthetic fixture cases + 2 PHIA-derived cases (1 synthetic PHIA user).
- PHIA cases require local CC BY-NC data; tests skip without it. PHIA has no ingestion timestamps, so late-arrival cannot be studied on PHIA data.
- Answer-text analysis is lexical English heuristics: misses paraphrases ("training for a marathon" ≠ "marathon training"), sarcasm, conditionals, cross-sentence negation; errs toward failing answers it cannot parse.
- Grounding `evidence_supports_claim` (state) only recognises claims of values that exist in the timeline; a fabricated free-text value is caught by answer_correctness, not grounding. Numeric support assumes the aggregate is a mean.
- Numeric tolerance is absolute; number extraction requires the unit right after the number.
- Two question intents.

## 21. Research References

- PHIA: Merrill MA, Paruchuri A, Rezaei N, et al. "Transforming wearable data into personal health insights using large language model agents." arXiv:2406.06464 (verified). Journal version — details unverified.
- PHA (successor to PHIA): arXiv:2508.20148 — linked from PHIA README; not read.
- MMASH: Rossi A et al. (2020), PhysioNet, DOI 10.13026/cerq-fc86 (verified).
- Not yet verified — verify before citing: PHIA+, PH-LLM, WHOOP public AI-evaluation engineering posts. No claim of novelty; no WHOOP internal access.

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

Status: Implemented (file layout partly superseded by ADR-008)
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

Status: Implemented (dispatch superseded by ADR-008: all evaluators run on all cases)
Date: 2026-10-02
Original approach: one `Case` model for current-state questions.
New approach: `StateCase` and `NumericCase` (discriminated by `kind`); `run_suite` dispatches the temporal vs numerical evaluator by kind.
Reason: numeric cases need expected float, unit, tolerance, expected readings.
Trade-offs: none significant.
Affected components: scenarios.py, evaluation.
Scope impact: Minor

### ADR-007 — PHIA labels are not ground truth; minimal adapter with recomputed values

Status: Implemented
Date: 2026-10-02
Original approach: use PHIA objective answers as numeric ground truth via a `summary_df` → `MemberTimeline` adapter.
New approach: PHIA labels are kept as a reference resource only. A single small module (`phia.py`) loads a local PHIA `summary_df_<id>.csv` into a `MemberTimeline` and defines a few `NumericCase`s whose expected values PulseEval recomputed independently from the published CSV (literal values in code, provenance recorded on each case, re-verified by a test that reads the CSV with the stdlib). Every case now carries a `provenance` string.
Reason: mapping investigation (§8) shows persona files map to users, but labels are not reproducible from the published CSVs (e.g. user 465 7-day mean RHR: 61.634 recomputed vs 61.18 PHIA label, with all 7 readings present).
Trade-offs: PHIA cases only run when the CC BY-NC data is present locally (tests skip otherwise); no claim of comparability with PHIA's published scores.
Affected components: new `phia.py`, scenarios.py (provenance), CLI (`--phia DIR`), tests.
Scope impact: Minor

### ADR-008 — One evaluator per dimension; evidence-grounding evaluator

Status: Implemented
Date: 2026-10-02
Original approach: temporal and numerical evaluators each mixed temporal / evidence / answer checks (tagged by `aspect`).
New approach: three independent evaluators run on every case: `temporal_consistency` (nothing retrieved/cited was unknowable at as_of), `evidence_grounding` (cited records exist, include the required ones, are relevant, lie in the question's valid window, support the claim, and none contradicts it), `answer_correctness` (state: current value affirmed, no other value affirmed; numeric: one affirmed value within tolerance). `aspect` removed (the evaluator is the dimension). `numerical.py` → `answer.py`; new `grounding.py`. Cases gain `target_name`, `window_start` (numeric) so grounding can be checked.
Reason: user requirement that a trace can fail one dimension while passing the others; grounding was previously folded into other evaluators.
Trade-offs: three results per case; small duplication of claim extraction between answer and grounding (shared via `text.py`).
Affected components: evaluation/*, scenarios.py, CLI, tests.
Scope impact: Moderate

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

### 2026-10-02 — Git remote + history cleanup

Status: Implemented
Original plan: n/a.
Change: `origin` set to https://github.com/Adhithyan245/PulseEval.git (user's repo, only remote); commits rewritten to remove Claude co-author trailers (trees unchanged; new hashes c9a794d, 804fcd8) and force-pushed with lease at the user's explicit request.
Reason: user wants only their identity in attribution.
Impact: standing rule — no Claude/Anthropic co-author lines on PulseEval commits.
Files affected: none (history only).
Scope impact: None

### 2026-10-02 — PHIA mapping investigation, evidence grounding, evaluator split

Status: Implemented
Original plan: build PHIA adapter if a question→user mapping exists; then evidence grounding.
Change: mapping investigated (§8): persona↔user supported empirically, but PHIA labels are not reproducible from published CSVs → not used as ground truth (ADR-007); minimal `phia.py` adapter + 2 recomputed cases with provenance; evaluators restructured into temporal / evidence grounding / answer (ADR-008); `numerical.py` → `answer.py`; new `grounding.py`; `aspect` removed; cases gain `target_name`, `provenance`, `window_start`; CLI `--phia DIR`; scenarios v0.3.0.
Reason: user requirement that ground truth have established provenance and that grounding be independent of temporal and answer correctness.
Impact: Observed runs (fixture + PHIA, 8 cases): reference 8/8 on all three; `input_order` temporal 8/8, grounding 7/8, answer 7/8; `no_as_of` 5/8, 6/8, 5/8; `no_window` 8/8, 4/8, 4/8. 56 tests pass with PHIA data present, 53 pass + 3 skipped without.
Files affected: scenarios.py, phia.py (new), __main__.py, evaluation/{__init__,schemas,text,temporal,grounding (new),answer (renamed from numerical)}.py, tests/{test_temporal,test_answer (renamed from test_numerical),test_grounding,test_suite,test_phia}.py, README.md, PROJECT_CONTEXT.md.
Scope impact: Moderate

## 24. Rules for Future Changes

- Read CURRENT STATUS first; keep it true.
- Plan/architecture/scope changes: update this file (ADR + change log) **before** code.
- New file/dependency only with a concrete current purpose; record it in §7.
- Never report numbers that were not produced by a run.
- Version-bump `AGENT_VERSION` / `*_EVALUATOR_VERSION` / `SCENARIOS_VERSION` when results could change.
- No LLM agent/judge and no UI without explicit user approval.
- Never add Claude/Anthropic co-author lines to commits; user's git identity only.
- Never label a value "ground truth" without recorded provenance (`Case.provenance`).
