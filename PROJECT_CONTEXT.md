# PulseEval Project Context

## CURRENT STATUS

Phase: v1.1 — External-agent interface & CI (user-requested enhancement after the v1.0 freeze)

Status: COMPLETE (v1.1)

Last completed:
v1.1: external-agent interface (blind case export, scoring of any agent's answers; ADR-014) and GitHub Actions CI (Python 3.10–3.13, tests + benchmark reproduction). v1.0 evaluators, cases and BENCHMARK.md unchanged. 447 passed + 7 xfailed with PHIA; 442 passed + 5 skipped + 7 xfailed without.

Currently working on:
Nothing.

Next task:
None scheduled. Natural next step (not started): run a real LLM-backed agent through the external interface and publish its results separately.

Blocked by:
None.

Last architecture change:
ADR-014 (external-agent interface) — Implemented.

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
| SUT agent v0.6.0 (`agent.py`): intents = current training goal, N-day mean resting HR (states coverage), recovery assessment, sleep/HRV relationship, out-of-scope questions (illness, sleep stages) | Implemented, tested |
| Agent trace schema | Implemented |
| Temporal-consistency evaluator v0.3.0 (knowability only) | Implemented, tested |
| Evidence-grounding evaluator v0.4.1 (handles assessments, relationships, open questions) | Implemented, tested |
| Answer-correctness evaluator v0.3.2 (state, numeric, relationship group means; N/A for assessments, open questions) | Implemented, tested |
| Missing-data handling evaluator v0.1.2 (numeric cases only) | Implemented, tested |
| Contradiction-handling evaluator v0.1.2 (assessment cases only) | Implemented, tested |
| Causal-restraint evaluator v0.1.1 (relationship cases only) | Implemented, tested |
| Uncertainty/abstention evaluator v0.1.1 (certainty-labelled cases only) | Implemented, tested |
| Scenarios v0.8.0: 41 synthetic cases (9 state, 12 numeric, 11 assessment, 6 relationship, 3 open), each with `provenance`; 11 certainty-labelled | Implemented |
| Benchmark (`benchmark.py`, `python -m pulseeval --benchmark`, BENCHMARK.md) | Implemented, test-verified |
| External-agent interface (`external.py`; `--export-cases`, `--write-answers`, `--evaluate`) | Implemented, tested (round-trip equal for all 11 configs) |
| CI (`.github/workflows/ci.yml`: Python 3.10–3.13, tests + benchmark diff) | Implemented |
| PHIA adapter (`phia.py`): 1 user, 2 numeric cases, PulseEval-recomputed values | Implemented, tested (skips without local data) |
| CLI report (`python -m pulseeval [--phia DIR]`) | Implemented |
| MMASH | Verified (§8); not downloaded |
| Memory lifecycle (deferred), MMASH, LLM agent, UI | Not started |

## 6. Current Architecture

```text
Case = StateCase | NumericCase | AssessmentCase | RelationshipCase | OpenQuestionCase
       (fixture: scenarios.py | PHIA: phia.py); optional `certainty` label on any kind
  timeline + question + as_of + target_name + expectation + provenance
  → HealthAgent.answer()          # SUT; tools: retrieve_context, latest_value, mean_value,
                                  #   carry_forward (fault), compare_to_baseline, latest_self_report,
                                  #   pair_by_day, check_scope
  → AgentTrace                    # structured; every tool call recorded
  → run_suite: every case × every applicable evaluator (None = not applicable, ADR-009)
      temporal_consistency   — was anything retrieved/cited unknowable at as_of?
      evidence_grounding     — is the cited evidence the right evidence for the claim?
      answer_correctness     — does the final text assert the right thing?
      missing_data           — (numeric only) is window coverage represented accurately?
      contradiction_handling — (assessment only) is a wearable/self-report conflict represented accurately?
      causal_restraint       — (relationship only) is causal language justified by the case's labels?
      uncertainty_abstention — (certainty-labelled only) does expressed certainty match evidence sufficiency?
  → EvaluationResult per (case, applicable evaluator): checks + typed Failures
  → CLI text report / JSON
```

Evaluators receive the case (expectations) and the trace; they never call agent code to compute expected values. A trace can fail any dimension independently (see §12 separation examples). Answer-text analysis is shared in `evaluation/text.py`.

## 7. Repository Structure

```text
PROJECT_CONTEXT.md   README.md   BENCHMARK.md (generated)   pyproject.toml   .gitignore
src/pulseeval/
  __init__.py
  __main__.py          # CLI: runs suite, prints report / JSON; --phia DIR; --benchmark
  benchmark.py         # agent configs, fault intent, independence/overlap analysis, report
  external.py          # blind case export; scoring of external agents' answers (ADR-014)
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
    missing_data.py    # missing-data handling (coverage representation; numeric only)
    contradiction.py   # contradiction handling (wearable vs self-report; assessments only)
    causal.py          # causal restraint (relationship cases only)
    uncertainty.py     # uncertainty / abstention (certainty-labelled cases only)
tests/
  test_timeline.py  test_temporal.py  test_grounding.py  test_answer.py  test_missing_data.py
  test_contradiction.py  test_causal.py  test_uncertainty.py  test_suite.py  test_phia.py
  test_regressions.py  test_wording.py  test_invariants.py  test_provenance.py  test_benchmark.py
  test_external.py
.github/workflows/ci.yml   # CI: pytest --strict-markers + benchmark reproduction on 3.10-3.13
data/raw/            # git-ignored; local copies only (data/raw/phia/: 14 files, ~700 KB)
```

## 8. Data Sources

Verified 2026-10-02 by reading official pages and the PHIA repository's code/data. Not legal advice; re-check before redistribution.

| Dataset | Status |
|---|---|
| Hand-written fixture (`scenarios.py`) | **In use.** Synthetic members M001 (goals, resting HR) and M002 (HRV, resting HR, synthetic self-reports) and M003 (sleep duration, HRV, stress reports, sleep-protocol assignments); values illustrative. |
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

Case base: `case_id, description, timeline, question, as_of, target_name, provenance`, plus optional `certainty` ∈ {direct_answer_supported, uncertainty_required, abstention_required, conflict_requires_qualification} (default None) and `conclusion_terms` (ADR-012).
`StateCase`: + `expected_record_id, expected_value: str`. Valid evidence window: event_time ≤ as_of.
`NumericCase`: + `window_start, expected_value: float, unit, tolerance (absolute), expected_record_ids, expected_observations`. Aggregate is the mean over [window_start, as_of]. `expected_observations` = daily observations a complete window would contain (hand-labelled); available = `len(expected_record_ids)` (knowable at as_of); missing days = window days without an expected record.

`AssessmentCase` (ADR-010): + `window_start, wearable_record_ids, self_report_record_ids, wearable_indicates ∈ {good, poor}, self_report_indicates ∈ {good, poor, None}, relevant_names`; property `conflict` = both directions known and different. Self-reports are `Record(kind="subjective", name="energy_report", value=<word>)`.

`RelationshipCase` (ADR-011): + `window_start, exposure_name, outcome_name, exposure_terms, outcome_terms, relationship_record_ids, observed_direction ∈ {positive, negative, none}, causal_support ∈ {association_only, supported}, causal_basis_record_ids, confounder_names, expected_group_means, unit, tolerance`. Validator: `supported` ⇔ non-empty `causal_basis_record_ids`. `relevant_names` = exposure, outcome, confounders, basis record names.

`OpenQuestionCase` (ADR-012): + `window_start, relevant_names`. For questions the evidence cannot answer; only temporal, grounding and uncertainty apply. `AssessmentCase.wearable_indicates` also allows "mixed"; `conflict` requires a non-mixed wearable direction.

`AgentTrace`: `agent_version, agent_config, query, member_id, as_of, time_window, retrieved_context, tools_called[ToolCall{name, inputs, outputs}], memories_used, evidence_used, final_answer, uncertainty, abstention`.

`Check`: `name, passed, explanation`. `EvaluationResult`: `case_id, evaluator, evaluator_version, passed, checks, failures`.
`Failure`: `failure_type, check, severity, query, expected_behavior, actual_behavior, evidence, trace, explanation`.

## 10. System Under Test

`HealthAgent(ordering, respect_as_of, respect_window, report_coverage, impute_missing, ignore_self_report, dismiss_self_report, causal_overclaim, overconfident, false_abstention)` v0.6.0 — deterministic, rule-based (no LLM; ADR-002, reaffirmed by user).
- Reference config: chronological, respects as_of, respects window, reports coverage, never imputes.
- Fault-injected configs (CLI names): `input_order` (assumes sorted input), `no_as_of` (retrieves unknowable records), `no_window` (aggregates all history), `silent_gaps` (omits coverage statement), `impute` (carries the previous reading into missing days, recorded as a `carry_forward` tool call, and claims full coverage), `ignore_self_report` (assesses from wearable data only), `dismiss_self_report` (on conflict: "…but your data shows you are actually well recovered"), `causal_overclaim` (same records, window and group means, but "Sleeping less caused your HRV to drop."), `overconfident` (definitive framing where evidence is thin, mixed, conflicting or out of scope — e.g. "This is definitely your true average for the week.", "you are definitely getting sick"), `false_abstention` (keeps the evidence it gathered but answers "I can't determine that from the available data."). `no_window` also makes the agent use self-reports of any age.
- Intents: "current training goal"; "average resting heart rate over the last N days" (window = [as_of − N days, as_of]; answer states "(k of N days had data)" or "(all N days had data)"); "how is my recovery" (today's HRV and resting HR vs the prior 7 days → good / reduced / mixed; latest self-report from the past 24 h; states a conflict explicitly when the directions differ); "is my HRV related to how much I sleep" (pairs sleep and HRV by day over 14 days, compares the shortest vs longest half of nights, reports both group means; < 3 ms difference → "does not show a clear association"; otherwise states the association with an explicit caveat, or causal wording only when `sleep_protocol` assignment records exist). "am I getting sick" / "how much deep sleep" → abstains and says what the data cannot establish. Reference also adds an explicit caveat when fewer than half the requested days have data, and when wearable signals are mixed. Anything else → explicit abstention.

## 11. Evaluation Engine

Deterministic-first. No LLM judge. Evaluators are versioned (`*_EVALUATOR_VERSION`). Seven independent dimensions (ADR-008), each its own evaluator. An evaluator returns `None` when its dimension does not apply to a case kind (ADR-009); pass rates are over applicable cases only.

## 12. Evaluation Dimensions

| Dimension | Status |
|---|---|
| Temporal consistency | **Implemented** v0.3.0 |
| Evidence grounding | **Implemented** v0.4.0 |
| Answer correctness (numerical, current-state, relationship group means) | **Implemented** v0.3.1 |
| Missing-data handling | **Implemented** v0.1.1 (numeric cases) |
| Contradiction handling (wearable vs self-report) | **Implemented** v0.1.1 (assessment cases, synthetic self-reports) |
| Causal restraint | **Implemented** v0.1.0 (relationship cases) |
| Uncertainty/abstention | **Implemented** v0.1.0 (certainty-labelled cases) |
| Memory validity, personalization, tool-call correctness | Not implemented in this version (out of scope; frozen) |

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

**missing_data** (NumericCase only) — `MISSING_DATA_FAILURE`. Missing data itself is never a failure; misrepresenting coverage is. N = expected observations, A = available (knowable) observations, M = N − A.
- `gap_acknowledged` — if M > 0, the answer says the window is incomplete: a non-negated gap word (missing, gap, incomplete, partial, no data, …), "A of N days" with A < N, "based on A days", or "M days missing". Not required when M = 0.
- `no_false_completeness_claim` — if M > 0: no "all N days", "no missing days", "complete", or available ≥ N claim.
- `no_false_imputation` — no claim of more than A observations; no affirmed imputation wording (imputed, interpolated, estimated, filled in, carried forward); no affirmed value-with-unit attributed to a missing date (ISO or month-name date).
- `coverage_counts_accurate` — any stated counts equal A / M / N; no gap claimed when the window is complete.
"Available" means knowable at as_of, so a reading that exists in the source but synced after as_of counts as missing for coverage.

**contradiction_handling** (AssessmentCase only) — `CONTRADICTION_FAILURE`. Never decides which source is right; checks how the relationship is represented.
- If the labelled directions conflict: `both_sources_acknowledged` (answer refers to wearable data *and* the self-report), `conflict_flagged` (explicit conflict wording: conflict, contradict, mismatch, inconsistent, at odds, "don't match / agree / line up"), `no_unsupported_resolution` (no unattributed, unhedged verdict such as "you are well recovered"; "your data suggests good recovery" is attributed and fine).
- If they do not conflict (agree, or no knowable current self-report): `no_invented_conflict`.
- Always: `no_source_dismissed` ("actually", "despite how you feel", "not really tired", "the device is wrong", "trust the data over…"; negated forms such as "don't ignore how you feel" are not dismissals).
Non-applicable checks pass with an explicit "Not applicable" explanation so every result has the same five checks.
Grounding for assessments: required = labelled wearable + self-report ids; relevant = `relevant_names`; window = [window_start, as_of]; no claim-support check.

**causal_restraint** (RelationshipCase only) — `CAUSALITY_FAILURE`. **PulseEval evaluates whether an answer's causal language is justified by the case's labelled evidence semantics; it does not perform causal inference.**
- `no_unsupported_causal_claim` — `association_only`: no *asserted* causal claim about exposure → outcome. Passes (not applicable) when `supported`.
- `causal_language_appropriately_qualified` — `association_only`: if causation is floated (hedged / hypothetical), the answer must also qualify it explicitly (not established, cannot determine, other factors may be involved). A hedge alone ("might have lowered") is not enough.
- `association_not_overstated` — no association or causal claim when `observed_direction = none`; no stated direction opposite to the observed one. Applies to supported cases too.
Answer correctness for relationships: `group_means_reported` (each labelled group mean affirmed in the unit ± tolerance). Grounding: required = relationship records + causal-basis records; relevant = `relevant_names`; no claim-support check.

**uncertainty_abstention** (cases with `certainty` set) — `UNCERTAINTY_FAILURE` / `ABSTENTION_FAILURE`. **It does not estimate statistical confidence, clinical risk or medical probability; it checks whether the agent's expressed certainty and willingness to answer match the evidence sufficiency labelled on the case.** A separate dimension because an answer can cite the right records, use the right window and numbers, state coverage, represent conflicts and avoid causal claims, and still be more (or less) certain than the evidence allows.
- `no_unnecessary_abstention` (direct_answer_supported) — no abstention flag and no refusal ("I can't determine", "insufficient"). Hedges ("about", "may vary") and even certainty words are fine.
- `uncertainty_expressed` (uncertainty_required, conflict_requires_qualification) — a limitation (unclear, uncertain, so few days, conflict, mixed, different directions, "whether"/"cannot") or a hedge (may, might, could, suggests).
- `abstained_or_qualified` (abstention_required) — abstention flag, a refusal, or a limitation; a bare hedge ("you may be getting sick") is not enough.
- `no_unjustified_certainty` (every level except direct) — no certainty marker (definitely, clearly, certainly, no doubt, this proves …) and no definitive conclusion using `conclusion_terms`. Strong words inside negated, refused, hypothetical or quoted framing do not count ("I would not conclude that you are definitely getting sick"); a negated certainty word ("not clearly") is itself a limitation; a negative conclusion ("you are not getting sick") is still definitive.
Abstaining when only uncertainty is required passes this dimension (declining is never overconfident); any cost shows up in answer correctness / missing-data instead.

**Certainty parsing (`text.certainty_claims`):** per clause with quoted spans masked; refusal patterns (can't/cannot determine/tell/answer/establish, insufficient, not enough, don't have … data, do not establish, would not conclude, would need …); limitation = refusal, epistemic marker, negated certainty word, or a non-negated uncertainty word; certainty markers only in clauses without a limitation, outside negation and hypothetical prefixes (plus built-in-negation phrases "no doubt", "without doubt"); definitive conclusion = conclusion term in a clause without limitation, hedge or hypothetical prefix.

**Causal-claim parsing (`text.causal_claims`):** each causal cue (caused, led to, is why, because, due to, resulted in, lowered/raised/reduced … your, …) in a clause that mentions **both** exposure and outcome terms is classified by context: *quoted* (inside double quotes), *uncertain* (whether / cannot / unclear / no evidence … before the cue), *hypothetical* (if / suppose / imagine …), *negated* (not / no / never / n't / cannot / without in the clause), *hedged* (may / might / could / would …), else *asserted*. Its own negator set is used because the shared one treats "dropped" as goal-abandonment negation. *Qualified* = causal vocabulary (causation, cause, prove, proof, or a cue) in a negated or uncertain clause, or a non-negated alternative-explanation phrase (other factors, confound…). Association = affirmed association/pattern cue (associated, correlated, related, tended to, moved together, on days when, following …). Direction = unambiguous comparative pair (lower/higher × less/more).

**Coverage parsing (`text.coverage_claims`):** lexical patterns applied in order with matched spans removed: "M of N days missing", "A of N days", "all N days", "based on (the) A (available) days", "M days missing", "A readings / days with data"; number words zero–twenty; counts are read regardless of clause polarity; completeness/gap/imputation wording is polarity-aware ("without imputing" is not an imputation claim).

**Phase 3 fixes to shared text analysis (each with a regression test; no evaluator redesign):**
1. Superstring values: `value_mentions` / `asserts` accept `among` (other known values of the field); longer values containing the value are masked first, so "marathon" is not found inside "half marathon" (answer v0.3.2, grounding v0.4.1). Found by `goal_value_superstring`; also fixed the mirror false pass.
2. Qualification ≠ refusal: "does not establish", "would not conclude", "would need" moved from refusals to limitations, so a caveated complete answer is not an unnecessary abstention (uncertainty v0.1.1). Found by `unc_direct_relationship`.
3. Sentence-initial subordinate phrases ("Despite / While / Although / Though / Whereas …,") end at their first comma. Found by the wording matrix.
4. Cue lookup also checks unstemmed words (plural stemming turned "previous" into "previou"); "previous" added to past cues.
5. Certainty markers count only in clauses about the case's conclusion when `conclusion_terms` exist ("your resting HR is clearly higher" is a supported observation).
6. Whitespace runs are collapsed before parsing (multi-word patterns use single spaces). Found by the metamorphic tests.
Versions bumped for every text-dependent evaluator: missing_data v0.1.2, contradiction v0.1.2, causal v0.1.1.

**Supported-language boundary (documented as strict xfail in `test_wording.py`):** reported speech ("your coach said / thinks / is certain …") is treated as the agent's own claim; double negation is not resolved; conflict or uncertainty expressed only through unlisted wording ("opposite directions", "small sample", "grain of salt") is missed; single-quoted phrases are not masked.

**Answer-text analysis (`text.py`, ADR-005):** sentences split on `.;!?` (not decimal points); new clause at contrast cues, contrastive negation only (`, not` / `and not` / `, without`), and `, so` (consequence clause; added with contradiction handling so "…conflict, so don't ignore…" keeps the conflict statement affirmed); "switched … from X to Y" → X past; mention = contiguous, ordered content tokens; polarity negated > past > hedged > affirmed; hedged mentions are not assertions.

**Separation examples (observed):** `overconfident` on `unc_sparse_rhr_7d` → only uncertainty_abstention fails (temporal, grounding, answer and missing-data pass: right records, window, 54.5 bpm and "2 of 7 days had data"); on `unc_ambiguous_recovery` contradiction passes and only uncertainty fails. `false_abstention` on `unc_direct_recovery_agree` → only uncertainty_abstention fails (the reverse direction). Overlap by design: a definitive resolution of a real wearable/self-report conflict fails both contradiction handling and uncertainty. `causal_overclaim` on `relation_association_only` and `relation_confounded_by_stress` → only causal_restraint fails (temporal, grounding, answer pass; missing-data and contradiction not applicable); on `relation_supported_by_protocol` the same causal wording passes. Hand-built traces: overclaim + HRV records dropped from evidence → grounding + causal fail; overclaim + retrieved future record → temporal + causal fail. `dismiss_self_report` on both conflict cases → only contradiction_handling fails (cites both sources; resolves the conflict for the data). `ignore_self_report` on agreement cases → only grounding fails (report not cited, no conflict to mishandle). `no_as_of` on `recovery_late_self_report` → temporal + contradiction (invented conflict) fail, grounding passes. `no_window` on `recovery_stale_self_report` → grounding (out of window) + contradiction fail, temporal passes. `silent_gaps` on PHIA 465 14-day (13/14) and on the fixture gap cases → only missing_data fails (correct, grounded, knowable answer presented as complete). `impute` on `rhr_mean_7d_late_sync` → only missing_data fails (the carried-forward value leaves the mean unchanged at 55.0). `no_window` → grounding + answer fail, temporal passes (wrong window, nothing unknowable; the claim is faithful to its own evidence). `no_as_of` on late-sync → temporal + answer fail, grounding passes (leaked reading is relevant and in-window). Retrieving-but-not-citing a future record → temporal fails only. Fabricated citation alongside correct evidence → grounding fails only.

## 13. Adversarial Test Cases

Fixture suite (as_of 2026-04-01): `goal_update_chronological`, `goal_update_reversed`, `goal_future_record`, `goal_late_arriving_record` (expected "weight training", g2); `rhr_mean_7d` (384/7 ≈ 54.857 bpm, tol 0.1, 7/7); `rhr_mean_7d_late_sync` (330/6 = 55.0, 6/7 knowable; leaking gives 56.0); `rhr_mean_7d_gap` (03-28 never recorded: 331/6 ≈ 55.167, 6/7).

Assessment suite (member M002, as_of 2026-04-15 09:00; baseline 04-08..04-14 HRV 385/7 = 55.0 ms, resting HR 392/7 = 56.0 bpm; today "good" = HRV 68 / RHR 51, "poor" = HRV 42 / RHR 61): `recovery_conflict_good_data_exhausted`, `recovery_conflict_poor_data_energetic` (conflict); `recovery_agree_good`, `recovery_agree_poor`; `recovery_late_self_report` ("exhausted" logged 09:30, after as_of → no knowable report); `recovery_stale_self_report` (only report is from 04-01, before the window → no current report).

Relationship suite (member M003, as_of 2026-05-11 09:00, 14-day window; 10 paired mornings 05-01..05-10; sleep 6.1/7.9/5.8/8.2/6.4/7.6/5.9/8.0/6.3/7.7 h): `relation_association_only` (HRV 45–49 ms on the 5 short nights, 60–64 ms on the 5 long; means 235/5 = 47.0 and 310/5 = 62.0; association only); `relation_confounded_by_stress` (same, plus `stress_report` "high" on exactly the short nights; association only, confounder labelled); `relation_supported_by_protocol` (same, plus `sleep_protocol` assignment records set the evening before — causal support is a fixture assumption grounded in those records); `relation_no_pattern` (HRV flat: 274/5 = 54.8 vs 276/5 = 55.2; direction none).

Uncertainty suite (ADR-012; built from existing fixtures plus a label): `unc_direct_rhr_7d` and `unc_direct_recovery_agree` (direct_answer_supported); `unc_sparse_rhr_7d` (2 of 7 days, 54+55 → 54.5 bpm; uncertainty_required); `unc_missing_sleep_stages` (open question; only total sleep exists; abstention_required); `unc_ambiguous_recovery` (HRV 62 and resting HR 59, both above baseline → mixed; uncertainty_required); `unc_conflict_recovery` (good data + "exhausted"; conflict_requires_qualification); `unc_out_of_scope_illness` (open question "Am I getting sick?" on HR/HRV data; abstention_required).

Phase 3 hardening cases (17; each description names the assumption it targets): temporal — `rhr_window_boundaries` (reading exactly at window start included, one a minute earlier excluded), `goal_identical_event_time` (tie broken by recorded_at), `goal_three_updates_shuffled`, `goal_update_at_as_of`; grounding — `rhr_same_time_other_fields`; answer — `goal_value_superstring`, `rhr_exact_integer_mean`; missing data — `rhr_gap_first_day`, `rhr_gap_final_day`, `rhr_gap_three_days`; contradiction — `recovery_subtle_disagreement` ("tired"), `recovery_mixed_with_report` (not a conflict), `recovery_no_data` (both sources absent; open question); causal — `relation_negative_direction`; uncertainty — `unc_direct_relationship`, `unc_sparse_three_of_seven`, `unc_direct_goal`.

PHIA-derived (user 465, as_of 2023-11-01, tol 0.05): `phia465_rhr_mean_7d` (61.634286, 7/7), `phia465_rhr_mean_14d` (59.649231, 13/14 — 2023-10-21 missing in source, never imputed; missing-data regression case).

Unit-test perturbations: adversarial answer texts (negated, past, hedged, stale, both values, ranges, missing unit); grounding perturbations (fabricated id, irrelevant in-window record, wrong record type, missing reading, no evidence, out-of-window reading, future record cited as support, unsupported numeric claim, stale record silently cited vs explicitly framed); missing-data perturbations on a synthetic 14-day window (complete with/without statement; 13/14 acknowledged five ways; unacknowledged; presented as complete three ways; imputation wording; value for the missing date in ISO and month-name form; 14 readings claimed; understated count; spurious gap on a complete window; correct number + false completeness; wrong number + correct coverage; temporal violation + correct coverage); contradiction perturbations (conflict acknowledged three ways; wearable only; self-report only + verdict; conflict not named; conflict named then resolved; self-report dismissed; wearable dismissed; agreement with/without invented conflict; negated conflict; verdict when sources agree; negated dismissal); causal parser tests (association phrasings, six asserted claims, negated / uncertain / hypothetical / hedged / quoted, qualifiers vs. non-qualifiers, unrelated "because", direction) and evaluator tests (restrained answers, unsupported claims, hypothetical-only, confounded, supported (permitted / wrong direction), no-pattern, the four independence cases, non-applicability); certainty parser tests (refusals, limitations, hedges, strong words under negation / refusal / hypothetical / quote, "not clearly", unqualified certainty, definitive conclusions incl. negative) and evaluator tests (direct plain / cautious / confident, refusing a supported answer, sparse with / without uncertainty, ambiguous, conflict, out-of-scope abstention vs. conclusion vs. hedge, fabricated sleep stages, quoted / hypothetical framing, both independence directions, non-applicability).

Not covered in this version: stale-memory lifecycle, counterfactual variation.

## 14. Metrics and Benchmark Methodology

Per evaluator: pass rate = passed applicable cases / applicable cases (ADR-009). All numbers come from actual runs only.

**Benchmark (Phase 3, ADR-013):** 41 synthetic cases × 11 agent configurations (reference + 10 faults). Applicable cases per dimension: temporal 41, grounding 41, answer 27, missing data 12, contradiction 11, causal 6, uncertainty 11. The reference agent passes every applicable dimension on every case. PHIA cases (2) are evaluated separately and excluded from BENCHMARK.md so the report reproduces without the PHIA data.
- **Fault model:** each fault declares intended dimensions and explained secondary (knock-on) dimensions (`FAULT_INTENT`); a test fails on any MISSING intended or UNEXPECTED observed dimension. Observed: no violations.
- **Independence:** every dimension has at least one (agent, case) where it is the only failing dimension — except temporal, whose leaks always propagate to grounding/answer under the agent faults; its sole-failure witness is a curated trace (retrieves but does not cite a future record) — and at least one where it passes while another fails.
- **Overlaps:** every co-failing dimension pair is classified (test-enforced): one *intentional overlap* (contradiction + uncertainty on a definitively resolved real conflict) and *shared root causes* (one fault breaking two properties, e.g. a wrong record cited and its value reported).
- **Metamorphic invariants (`test_invariants.py`):** timeline record order (all agents except `input_order`), an unrelated record far outside every window, cited-id order, answer letter case and whitespace, repeated runs and case order — all leave every check outcome unchanged.
- **Provenance/reproducibility (`test_provenance.py`):** unique case ids, provenance and semantics on every case, every failure traceable to case question, member, agent config and real record ids; no randomness or wall-clock reads in `src/`; PHIA labels never read; PHIA-enabled and PHIA-disabled runs agree on all synthetic cases.
- **Mutation checks (temporary source patches, restored and verified byte-identical):** 14/14 detected — temporal boundary (15 failing tests), grounding window (7), missing-data acknowledgement (11) and completeness (5), contradiction negation of conflict (1) and dismissal (1), causal context (2) and negation (4), uncertainty refusals (6) and negated certainty (1, after adding a test for the one surviving mutant), and each Phase 3 fix (16, 3, 1, 10).
- **Reproduce (v1.1):** Python ≥ 3.10; `pip install -e ".[dev]"`; `python -m pytest` (without PHIA data: 442 passed, 5 skipped, 7 xfailed; with it: 447 passed, 7 xfailed); `python -m pulseeval --benchmark` must equal BENCHMARK.md (enforced by tests/test_benchmark.py).
- **Clean-copy reproduction:** the staged tree exported with `git checkout-index` into a fresh directory, fresh venv, `pip install -e ".[dev]"` (resolved pydantic 2.13.5 vs. 2.9.2 in development): 424 passed, 5 skipped (PHIA absent), 7 xfailed; `python -m pulseeval --benchmark` byte-identical to BENCHMARK.md and on repeat.

## 15. Development Phases

| Phase | Scope | Status | Commit |
|---|---|---|---|
| 0 / 1 | Audit; minimal vertical slice | Complete | c9a794d |
| 2 | Core evaluation: 7 independent dimensions | Complete (frozen) | fd6f489 |
| 3 | Hardening & benchmark validation (redefined by the user from "memory evaluation") | Complete (frozen) | 2c2a813 |
| 4 | Finalisation, documentation, presentation (v1.0) | Complete | c0fe7ed |
| v1.1 | External-agent interface (ADR-014), CI — user-requested after the v1.0 freeze | Complete | this commit |

v1.0 was frozen at c0fe7ed; v1.1 adds the external-agent interface and CI without changing evaluators, cases or benchmark results. Memory evaluation, real self-report data (MMASH), running an LLM-backed agent and a UI are not part of the delivered scope.

## 16. Completed Work

- Phase 0: empty directory audited; Python 3.11, pydantic 2.9, pytest; no API key.
- Phase 1: vertical slice.
- Phase 2 (partial): temporal answer check hardened; numerical evaluator; dataset verification; PHIA mapping investigation; evaluators split by dimension; evidence grounding; minimal PHIA adapter; missing-data handling; contradiction handling (synthetic self-reports); causal restraint (RelationshipCase); uncertainty/abstention (certainty labels, OpenQuestionCase). Phase 2 complete.
- Phase 3 (hardening & benchmark validation): see §14 and the change log.
- Phase 4 (finalisation): repository audit, portfolio README, benchmark scope/limitations section, handoff cleanup, final validation; project frozen.
- Git: `origin` = https://github.com/Adhithyan245/PulseEval.git; history rewritten 2026-10-02 to remove Claude co-author trailers (user decision); commits use the user's identity only.

## 17. In-Progress Work

None (stopped for review).

## 18. Future Work (outside this frozen version)

None scheduled. Candidates: run an LLM-backed agent through the external interface (ADR-014) and publish its results separately from the evaluator benchmark; memory-lifecycle evaluation; real self-report data (MMASH questionnaires); widening the parser's supported language (§12 boundary list).
3. Later (deferred by user): MMASH questionnaires as a real self-report source for contradiction cases.

## 19. Deferred Work

LLM-backed agent and LLM judge (until the deterministic layer is trusted — user decision); MMASH download/integration (user: synthetic self-reports first); using PHIA labels (not reproducible); more PHIA users/templates; PHA (successor) inspection; memory lifecycle (Phase 3); reporting module (Phase 6); UI (Phase 7); pandas/numpy/openpyxl.

## 20. Known Limitations

- Agent is rule-based; it validates the evaluator pipeline, not LLM behaviour.
- Data is tiny: 6 synthetic fixture cases + 2 PHIA-derived cases (1 synthetic PHIA user).
- PHIA cases require local CC BY-NC data; tests skip without it. PHIA has no ingestion timestamps, so late-arrival cannot be studied on PHIA data.
- Answer-text analysis is lexical English heuristics: misses paraphrases ("training for a marathon" ≠ "marathon training"), sarcasm, conditionals, cross-sentence negation; errs toward failing answers it cannot parse.
- Grounding `evidence_supports_claim` (state) only recognises claims of values that exist in the timeline; a fabricated free-text value is caught by answer_correctness, not grounding. Numeric support assumes the aggregate is a mean.
- Numeric tolerance is absolute; number extraction requires the unit right after the number.
- External agents (v1.1) are scored by the same lexical parsers, so freely worded LLM answers are more exposed to the §12 language boundaries than the built-in agent's templated answers; no external-agent results are published.
- Benchmark scope: 41 synthetic cases from 3 synthetic members plus 2 PHIA-derived cases; results characterise the evaluators against a rule-based agent with injected faults, not real agents. Temporal consistency checks knowability at the question time, not record ordering (ordering errors surface in grounding/answer). Parser language boundaries: see §12 (strict xfail list).
- Uncertainty/abstention: **behavioural, not statistical or clinical** — certainty labels are fixture judgements of evidence sufficiency. Parsing is lexical: uncertainty expressed only through unlisted wording ("I'd take this with a grain of salt") is missed; certainty words outside the list ("undeniably") are missed; `conclusion_terms` must be supplied per case; the structured `abstention` flag is trusted.
- Causal restraint: **PulseEval judges causal language against case labels; it does not perform causal inference.** Causal-support labels are fixture assumptions (the protocol case is not evidence of a physiological effect). Parsing is lexical and clause-based: claims must mention both exposure and outcome terms in one clause ("That's because of your sleep." is missed); causal verbs used non-causally with both terms can false-positive; supported cases permit causal wording without checking that it cites the basis; direction is read only from unambiguous comparative pairs.
- Contradiction: self-reports are synthetic single words with hand-labelled directions; the agent's good/poor rule (HRV and RHR vs a 7-day mean) is a fixture convention, not a physiological standard. Conflict/dismissal/verdict detection is lexical (misses e.g. "your body says otherwise", sarcasm, conflicts stated across sentences without conflict words); a verdict inside an attributed clause ("the data shows you are recovered") is treated as attributed.
- Missing-data: assumes one expected observation per day; coverage parsing is lexical (misses e.g. "a day short", "except Saturday"); dates recognised only as ISO or "Month D"; a value for a missing day stated in a different sentence from the date is not detected.
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

### ADR-009 — Evaluators may be not applicable to a case kind

Status: Implemented
Date: 2026-10-02
Original approach: every evaluator runs on every case and always returns a result (ADR-008).
New approach: an evaluator returns `None` when its dimension does not apply to the case (missing-data handling applies only to `NumericCase`, whose question requests a window of expected daily observations). `run_suite` drops `None`; pass rates are over applicable cases only.
Reason: an always-passing result with no checks would silently inflate pass rates.
Trade-offs: per-evaluator denominators differ; the report prints them explicitly.
Affected components: evaluation/__init__.py, evaluation/missing_data.py, CLI report.
Scope impact: Minor

### ADR-010 — AssessmentCase and a synthetic self-report layer

Status: Implemented
Date: 2026-10-02
Original approach: contradiction handling planned on MMASH questionnaires (§18).
New approach: (user decision) synthetic self-report records first, MMASH later. Self-reports are ordinary `Record`s (`kind="subjective"`, `name="energy_report"`, string value). New case kind `AssessmentCase` for open "how is my recovery?" questions, hand-labelled with: the wearable record ids and self-report ids the assessment rests on, `wearable_indicates` / `self_report_indicates` ∈ {good, poor} (or `self_report_indicates=None` when no knowable report exists), and `relevant_names` for grounding. Conflict = the two labelled directions differ. A new `contradiction_handling` evaluator applies only to AssessmentCase; answer_correctness and missing_data are not applicable to it (ADR-009); temporal and grounding apply unchanged in spirit (grounding uses `relevant_names`, has no claim-support check for assessments).
Reason: contradiction needs subjective data the current fixtures lack; a synthetic layer keeps labels hand-verifiable and avoids premature dataset work.
Trade-offs: directions are hand labels on synthetic data, not clinical judgements; the evaluator checks how a conflict is *represented*, never which source is "right".
Affected components: scenarios.py, agent.py, evaluation/{text,grounding,answer,contradiction (new)}.py, CLI, tests.
Scope impact: Minor

### ADR-011 — RelationshipCase with structured causal-support labels

Status: Implemented
Date: 2026-10-02
Original approach: no case kind represents a relationship between two variables; causal restraint planned but unspecified.
New approach: new case kind `RelationshipCase` ("Is my HRV related to how much I sleep?"), hand-labelled with: `exposure_name` / `outcome_name` and their answer-text terms, `relationship_record_ids` (paired observations that establish the pattern), `observed_direction` ∈ {positive, negative, none}, `causal_support` ∈ {association_only, supported}, `causal_basis_record_ids` (records that justify a causal reading, e.g. an assigned protocol), `confounder_names` (other recorded variables that move with the exposure), group means for answer correctness. A validator enforces `supported` ⇔ non-empty `causal_basis_record_ids`, so causal support always has record-level provenance. New `causal_restraint` evaluator applies only to RelationshipCase (ADR-009); it judges whether the answer's causal language is justified by these labels — PulseEval does not perform causal inference.
Reason: causal restraint must be driven by case evidence semantics, not a global "causal words are bad" rule; supported-causality cases must be representable.
Trade-offs: labels are fixture assumptions on synthetic data, not physiological findings; the parser is lexical/clause-based.
Affected components: scenarios.py, agent.py, evaluation/{text,grounding,answer,causal (new)}.py, CLI, tests.
Scope impact: Minor

### ADR-012 — Certainty labels, OpenQuestionCase, mixed wearable direction

Status: Implemented
Date: 2026-10-02
Original approach: no case states how much certainty its evidence supports; every case kind presumes an answerable question.
New approach: two optional fields on every case — `certainty` ∈ {direct_answer_supported, uncertainty_required, abstention_required, conflict_requires_qualification} (default None) and `conclusion_terms` (wording of the conclusion the question asks about). A new `uncertainty_abstention` evaluator applies only to cases with `certainty` set (ADR-009), so unlabelled cases add no results. New minimal case kind `OpenQuestionCase` (timeline + window + relevant record names) for questions no other kind can represent (out-of-scope inference such as illness; data that does not exist such as sleep stages); only temporal, grounding and uncertainty apply to it. `AssessmentCase.wearable_indicates` gains "mixed" (signals point in different directions); `conflict` now also requires a non-mixed wearable direction — unchanged for all existing cases.
Reason: the evaluator must reason from structured evidence-sufficiency labels, not from prose; out-of-scope and ambiguous situations were not representable.
Trade-offs: certainty levels are hand labels on synthetic fixtures; this is not statistical, clinical or probabilistic confidence.
Affected components: scenarios.py, agent.py, evaluation/{text,grounding,answer,uncertainty (new)}.py, CLI, tests.
Scope impact: Minor

### ADR-013 — Benchmark module and test-verified report

Status: Implemented
Date: 2026-10-02
Original approach: results reported ad hoc from CLI runs; fault expectations only in tests/test_suite.py.
New approach: `benchmark.py` runs every agent configuration over the synthetic benchmark and renders a deterministic Markdown report (dimension applicability and pass/fail, fault intent vs. observed failures, independence and co-failure matrices, intentional overlaps, failure analysis from live evaluator output). `python -m pulseeval --benchmark` prints it; `BENCHMARK.md` is the committed output, and a test regenerates it and fails if it differs. The report covers synthetic cases only so it reproduces without the CC BY-NC PHIA data.
Reason: Phase 3 requires consolidated, reproducible results that cannot silently drift from the code.
Trade-offs: one more module and one generated file; any behaviour change requires regenerating BENCHMARK.md (intended).
Affected components: benchmark.py (new), __main__.py, BENCHMARK.md (new), tests.
Scope impact: Minor

### ADR-014 — External-agent interface (blind export, trace evaluation)

Status: Implemented
Date: 2026-10-21
Original approach: only the built-in rule-based `HealthAgent` can be evaluated (a documented limitation: results characterise the evaluators, not real agents).
New approach: `external.py` adds (1) `export_cases` — the benchmark questions, as-of times and timelines as JSON, with every expectation, label and provenance withheld (blind); (2) `evaluate_traces` — loads answers produced by any agent (case_id, final_answer, evidence_used, optional retrieved_context / abstention) and scores them with the unchanged seven evaluators. CLI: `--export-cases FILE`, `--evaluate FILE [--json]`. A round-trip test proves external evaluation of the reference agent's own answers reproduces `run_suite` exactly.
Reason: let real (e.g. LLM-based) agents be benchmarked without changing evaluator semantics.
Trade-offs: external agents must cite record ids from the exported timeline for grounding to pass; unanswered cases are reported, not silently skipped.
Affected components: external.py (new), __main__.py, tests, README.
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

### 2026-10-02 — Missing-data handling evaluator

Status: Implemented
Original plan: missing-data handling as a planned Phase 2 dimension.
Change: new `evaluation/missing_data.py` (4 checks, `MISSING_DATA_FAILURE`); `coverage_claims` and `dated_values` in `text.py`; ", without" added as a contrastive clause boundary (answer v0.2.1, grounding v0.1.1); `NumericCase.expected_observations`; fixture case `rhr_mean_7d_gap`; PHIA cases expose `expected_observations` (no duplicated loading); agent v0.3.0 states coverage, new faults `silent_gaps`, `impute` (with `carry_forward` tool call in the trace); evaluators may return None (ADR-009); scenarios v0.4.0.
Reason: user-requested fourth dimension; representing completeness accurately is separate from temporal, grounding and answer correctness.
Impact: Observed runs (fixture + PHIA, 9 cases; missing_data over the 5 numeric cases), order temporal / grounding / answer / missing_data: reference 9/9, 9/9, 9/9, 5/5; `input_order` 9/9, 8/9, 8/9, 5/5; `no_as_of` 6/9, 7/9, 6/9, 4/5; `no_window` 9/9, 4/9, 4/9, 2/5; `silent_gaps` 9/9, 9/9, 9/9, 2/5; `impute` 9/9, 7/9, 7/9, 2/5. 84 tests pass; without PHIA data 80 pass + 4 skipped. During development shell heredocs turned regex word boundaries into backspace characters twice; fixed, and a control-character scan is now part of the pre-commit routine.
Files affected: agent.py, scenarios.py, phia.py, __main__.py, evaluation/{__init__,text,answer,grounding,missing_data (new)}.py, tests/{test_missing_data (new),test_suite,test_phia}.py, README.md, PROJECT_CONTEXT.md.
Scope impact: Minor

### 2026-10-02 — Contradiction-handling evaluator (synthetic self-report layer)

Status: Implemented
Original plan: contradiction handling on MMASH questionnaires.
Change (user-directed: synthetic first, no MMASH yet): ADR-010 `AssessmentCase`; 6 recovery cases with synthetic `energy_report` records; `evaluation/contradiction.py` (5 checks, `CONTRADICTION_FAILURE`); `text.contradiction_claims`; `, so` clause boundary; grounding v0.2.0 (assessment required/relevant/window, no support check); answer v0.2.2 (N/A for assessments); missing_data v0.1.1 (text change only); agent v0.4.0 recovery intent + `ignore_self_report`, `dismiss_self_report`; scenarios v0.5.0.
Reason: fifth Phase 2 dimension.
Impact: Observed runs (fixture + PHIA, 15 cases), order temporal / grounding / answer / missing_data / contradiction: reference 15/15, 15/15, 9/9, 5/5, 6/6; `input_order` 15/15, 14/15, 8/9, 5/5, 6/6; `no_as_of` 11/15, 13/15, 6/9, 4/5, 5/6; `no_window` 15/15, 9/15, 4/9, 2/5, 5/6; `silent_gaps` 15/15, 15/15, 9/9, 2/5, 6/6; `impute` 15/15, 13/15, 7/9, 2/5, 6/6; `ignore_self_report` 15/15, 11/15, 9/9, 5/5, 4/6; `dismiss_self_report` 15/15, 15/15, 9/9, 5/5, 4/6. Earlier dimensions unchanged on earlier cases. 118 tests pass; without PHIA data 114 pass + 4 skipped. A test exposed whole-clause negation swallowing "…conflict, so don't ignore how you feel"; fixed with the `, so` boundary rather than rewording the test.
Files affected: agent.py, scenarios.py, __main__.py, evaluation/{__init__,text,grounding,answer,missing_data,contradiction (new)}.py, tests/{test_contradiction (new),test_suite}.py, README.md, PROJECT_CONTEXT.md.
Scope impact: Minor

### 2026-10-02 — Causal-restraint evaluator

Status: Implemented
Original plan: causal restraint as a planned Phase 2 dimension (travel/recovery example).
Change: ADR-011 `RelationshipCase` (+ validator); 4 synthetic sleep/HRV cases (association only, confounded by stress, supported by protocol, no pattern); `text.causal_claims` (context-classified cues, own negator set); `evaluation/causal.py` (3 checks, `CAUSALITY_FAILURE`); grounding v0.3.0 and answer v0.3.0 handle relationships; agent v0.5.0 relationship intent + `causal_overclaim`; CLI agent; scenarios v0.6.0. No shared text-analysis behaviour changed, so earlier evaluators' results are unchanged.
Reason: sixth Phase 2 dimension; causal language must be judged against labelled evidence semantics, not a keyword list.
Impact: Observed runs (fixture + PHIA, 19 cases), order temporal / grounding / answer / missing_data / contradiction / causal: reference 19/19, 19/19, 13/13, 5/5, 6/6, 4/4; `input_order` 19/19, 18/19, 12/13, 5/5, 6/6, 4/4; `no_as_of` 15/19, 17/19, 10/13, 4/5, 5/6, 4/4; `no_window` 19/19, 13/19, 8/13, 2/5, 5/6, 4/4; `silent_gaps` 19/19, 19/19, 13/13, 2/5, 6/6, 4/4; `impute` 19/19, 17/19, 11/13, 2/5, 6/6, 4/4; `ignore_self_report` 19/19, 15/19, 13/13, 5/5, 4/6, 4/4; `dismiss_self_report` 19/19, 19/19, 13/13, 5/5, 4/6, 4/4; `causal_overclaim` 19/19, 19/19, 13/13, 5/5, 6/6, 2/4. 182 tests pass; without PHIA data 178 pass + 4 skipped. Mutation check: replacing context classification with "every cue is asserted" makes 7 causal tests fail. Control-character scan of files and all 27 compiled regexes: clean.
Files affected: agent.py, scenarios.py, __main__.py, evaluation/{__init__,text,grounding,answer,causal (new)}.py, tests/{test_causal (new),test_suite}.py, README.md, PROJECT_CONTEXT.md.
Scope impact: Minor

### 2026-10-02 — Uncertainty/abstention evaluator (Phase 2 complete)

Status: Implemented
Original plan: uncertainty/abstention as the last Phase 2 dimension.
Change: ADR-012 (`certainty` + `conclusion_terms` on all cases; `OpenQuestionCase`; "mixed" wearable direction); 7 labelled cases reusing existing fixtures; `text.certainty_claims`; `evaluation/uncertainty.py` (4 checks); grounding v0.4.0 and answer v0.3.1 handle open questions; agent v0.6.0 out-of-scope intents, reference caveats for sparse and mixed evidence, faults `overconfident`, `false_abstention`; scenarios v0.7.0. Contradiction v0.1.1: `_VERDICT` now allows certainty modifiers ("you are definitely well recovered") — a regression test fails under the old pattern and passes under the new one. The exact-set contradiction label test now includes the new real conflict case `unc_conflict_recovery` and asserts the mixed case is not a conflict.
Reason: seventh and final Phase 2 dimension.
Impact: Observed runs (fixture + PHIA, 26 cases), order temporal / grounding / answer / missing / contradiction / causal / uncertainty: reference 26/26, 26/26, 15/15, 7/7, 9/9, 4/4, 7/7; `input_order` 26/26, 25/26, 14/15, 7/7, 9/9, 4/4, 7/7; `no_as_of` 22/26, 24/26, 12/15, 6/7, 8/9, 4/4, 7/7; `no_window` 26/26, 18/26, 8/15, 3/7, 8/9, 4/4, 6/7; `silent_gaps` 26/26, 26/26, 15/15, 3/7, 9/9, 4/4, 7/7; `impute` 26/26, 24/26, 13/15, 3/7, 9/9, 4/4, 6/7; `ignore_self_report` 26/26, 20/26, 15/15, 7/7, 6/9, 4/4, 7/7; `dismiss_self_report` 26/26, 26/26, 15/15, 7/7, 6/9, 4/4, 6/7; `causal_overclaim` 26/26, 26/26, 15/15, 7/7, 9/9, 2/4, 7/7; `overconfident` 26/26, 26/26, 15/15, 7/7, 6/9, 4/4, 2/7; `false_abstention` 26/26, 26/26, 0/15, 3/7, 6/9, 4/4, 5/7. Earlier dimensions unchanged on earlier cases except contradiction v0.1.1 (no earlier case affected). 258 tests pass; without PHIA data 254 pass + 4 skipped. Mutation check: disabling negation/refusal handling in the certainty parser fails 13 uncertainty tests. Control-character scan (files and 32 compiled regexes): clean.
Files affected: agent.py, scenarios.py, __main__.py, evaluation/{__init__,text,grounding,answer,contradiction,uncertainty (new)}.py, tests/{test_uncertainty (new),test_suite,test_contradiction}.py, README.md, PROJECT_CONTEXT.md.
Scope impact: Minor

### 2026-10-02 — Roadmap: Phase 3 redefined as Hardening & Benchmark Validation

Status: Implemented
Original plan: Phase 3 = memory evaluation; Phase 4 adversarial suite; Phase 5 benchmarking; Phase 6 reporting.
(Status note: implemented in Phase 3; Phase 4 then became finalisation and freeze.)
Change: user redefined Phase 3 as hardening and benchmark validation (benchmark expansion, adversarial wording, independence/fault matrices, metamorphic tests, provenance/reproducibility, consolidated report). Phase 2 is frozen: no evaluator redesign, no eighth dimension; defects get minimal fixes with regression tests. Memory evaluation is deferred, unscheduled.
Reason: user decision.
Impact: §15 roadmap note; ADR-013.
Files affected: PROJECT_CONTEXT.md.
Scope impact: Moderate (roadmap)

### 2026-10-02 — Phase 3: hardening & benchmark validation

Status: Implemented
Original plan: (redefined) harden the frozen Phase 2 evaluators and validate the benchmark.
Change: +17 synthetic cases (41 total, scenarios v0.8.0); `benchmark.py` + `--benchmark` + BENCHMARK.md (ADR-013); tests: regressions, wording matrix (7 strict-xfail boundaries), invariants, provenance/PHIA boundary, benchmark; six minimal shared-text fixes (§12) with version bumps; one test added to close a surviving mutant; PHIA-agreement check consolidated into one test (5 skips without PHIA instead of 15).
Reason: prove PulseEval is a reliable, reproducible evaluation framework rather than a set of passing tests.
Impact: Baseline (fd6f489, verified): 258 passed with PHIA; 254 + 4 skipped without; 26 cases. Final: 429 passed + 7 xfailed with PHIA; 424 passed + 5 skipped + 7 xfailed without; 43 cases (41 synthetic + 2 PHIA). Fault model: no violations. Independence: all 7 dimensions witnessed (temporal via a curated trace). Mutations: 14/14 detected. Clean-copy reproduction: matches. One transient environment stall (a single 10-minute suite run) was not reproducible; repeated runs take ~9 s.
Files affected: scenarios.py, benchmark.py (new), __main__.py, evaluation/{text,answer,grounding,missing_data,contradiction,causal,uncertainty}.py, tests (5 new files; test_suite, test_contradiction, test_uncertainty updated), BENCHMARK.md (new), README.md, PROJECT_CONTEXT.md.
Scope impact: Minor (no new dimension, no evaluator redesign)

### 2026-10-02 — Phase 4: finalisation & freeze

Status: Implemented
Original plan: (user-defined) final documentation and presentation phase; no functionality.
Change: README rewritten for a first-time reader (purpose, scope boundary, seven dimensions, architecture, benchmark, hardening, failure examples, reproduction, limitations, status); BENCHMARK.md gains a generated "Scope and limitations" section (static text in `render()`; every generated number unchanged, verified by diff); this document's status, roadmap and obsolete "planned" language updated; final audit (no secrets, no data, no stray files), validation and clean-copy reproduction.
Reason: make the frozen work understandable, reproducible and defensible.
Impact: no code-behaviour change; test counts unchanged (429 + 7 xfailed with PHIA; 424 + 5 skipped + 7 xfailed without). Project frozen.
Package metadata aligned with the final narrative (pyproject description; version 1.0.0 marks the frozen release; not printed in any result).
Files affected: README.md, BENCHMARK.md, src/pulseeval/benchmark.py (report text only), pyproject.toml, src/pulseeval/__init__.py (docstring), PROJECT_CONTEXT.md.
Scope impact: None

### 2026-10-21 — v1.1: external-agent interface and CI

Status: Implemented
Original plan: v1.0 frozen (c0fe7ed).
Change (user request to enhance further): ADR-014 `external.py` (blind `export_cases`, `answers_from_agent`, `evaluate_traces`) and CLI flags `--export-cases`, `--write-answers`, `--evaluate`; CLI report printing moved into a function (built-in output verified byte-identical before/after); `tests/test_external.py` (blind export, round-trip equality for all 11 agent configs via real JSON, partial/malformed submissions, free-text answers, cited unknowable record); GitHub Actions CI on Python 3.10–3.13 running `pytest --strict-markers` and diffing a regenerated benchmark against BENCHMARK.md; README badge and "Evaluate your own agent" section; package version 1.1.0.
Reason: the main documented limitation was that only the built-in rule-based agent could be evaluated.
Impact: evaluators, cases and BENCHMARK.md unchanged (verified). Tests: 447 passed + 7 xfailed with PHIA; 442 passed + 5 skipped + 7 xfailed without.
Files affected: src/pulseeval/external.py (new), src/pulseeval/__main__.py, tests/test_external.py (new), .github/workflows/ci.yml (new), README.md, pyproject.toml, PROJECT_CONTEXT.md.
Scope impact: Minor

## 24. Rules for Future Changes

The rules below apply to any further version.

- Read CURRENT STATUS first; keep it true.
- Plan/architecture/scope changes: update this file (ADR + change log) **before** code.
- New file/dependency only with a concrete current purpose; record it in §7.
- Never report numbers that were not produced by a run.
- Version-bump `AGENT_VERSION` / `*_EVALUATOR_VERSION` / `SCENARIOS_VERSION` when results could change.
- No LLM agent/judge and no UI without explicit user approval.
- Never add Claude/Anthropic co-author lines to commits; user's git identity only.
- Never label a value "ground truth" without recorded provenance (`Case.provenance`).
- Regenerate BENCHMARK.md (`python -m pulseeval --benchmark > BENCHMARK.md`) after any behaviour change; the test fails otherwise.
- Write regex-bearing code with the Edit/Write tools, not shell heredocs (backslash escapes were mangled); scan for control characters before committing.
