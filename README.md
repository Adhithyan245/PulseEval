# PulseEval

[![CI](https://github.com/Adhithyan245/PulseEval/actions/workflows/ci.yml/badge.svg)](https://github.com/Adhithyan245/PulseEval/actions/workflows/ci.yml)

**A deterministic evaluation framework for testing longitudinal health-agent behaviour across temporal consistency, evidence grounding, answer correctness, missing-data handling, contradiction handling, causal restraint, and uncertainty/abstention.**

> **Scope:** PulseEval evaluates whether an agent's answer is behaviourally consistent with structured longitudinal evidence and the semantics of the evaluation case. It does **not** establish clinical truth, estimate clinical risk, perform causal inference, or provide medical advice. It is an evaluation framework, not a medical system.

## Why

Evaluating a health agent that reasons over weeks of wearable data is not just a question of whether its answer contains the right number. An agent can produce a plausible answer and still:

- use the wrong time window, or data it could not yet have known;
- cite stale or irrelevant evidence;
- silently treat an incomplete window as complete, or fill in missing days;
- ignore or dismiss a self-report that conflicts with the wearable data;
- turn an observed association into an unsupported causal claim;
- sound certain when the evidence is thin, or refuse when it is sufficient.

PulseEval evaluates each of these behaviours **separately**, so that a single failure is attributed to the property it actually violates.

## Evaluation dimensions

| # | Dimension | What it checks | Applies to |
|---|---|---|---|
| 1 | Temporal consistency | Nothing retrieved or cited was unknowable at the question time (recorded later, or in the future). | every case |
| 2 | Evidence grounding | Cited records exist, include the required ones, are the relevant field, fall inside the valid window, support the claim, and are not silently contradictory. | every case |
| 3 | Answer correctness | The text affirms the correct current value (not a negated, hedged or stale one), or a number within tolerance. | value questions |
| 4 | Missing-data handling | Coverage is represented accurately: gaps acknowledged, no false "complete window", no imputed or invented observations. Missing data itself is not a failure. | windowed numeric questions |
| 5 | Contradiction handling | When wearable data and self-report disagree, both are acknowledged, the conflict is named, neither is dismissed, and it is not resolved by fiat; no conflict is invented when they agree. | recovery assessments |
| 6 | Causal restraint | Causal language is used only when the case labels causal support (backed by specific records); association, negated, hypothetical and quoted causal wording are not claims. | relationship questions |
| 7 | Uncertainty / abstention | Expressed certainty matches the case's labelled evidence sufficiency: answer when supported, qualify when evidence is thin, ambiguous or conflicting, abstain when the conclusion cannot be established. | certainty-labelled cases |

A dimension that does not apply to a case returns no result and is not counted in its pass rate. The dimensions are **separately evaluated behavioural properties**, not statistically independent measures; their overlaps are measured and documented (see [BENCHMARK.md](BENCHMARK.md)).

## Architecture

```text
Longitudinal case  (timeline of timestamped records + question + as-of time)
        |
Structured provenance + expected semantics  (hand-labelled, never computed by the agent)
        |
Deterministic agent response  ->  AgentTrace  (retrieved records, tool calls,
        |                                       cited evidence, answer, abstention)
        v
+-----------------------------------------+
|  Separately evaluated behavioural       |
|  dimensions (deterministic checks)      |
|    temporal        grounding            |
|    answer          missing data         |
|    contradiction   causal restraint     |
|    uncertainty / abstention             |
+-----------------------------------------+
        |
Per-dimension PASS / FAIL / N/A, each failure typed and explained
        |
Benchmark: every agent configuration x every case  ->  BENCHMARK.md
```

| Module | Responsibility |
|---|---|
| `timeline.py` | Records with `event_time` vs `recorded_at` as-of semantics |
| `scenarios.py` | Synthetic cases with hand-derived expectations and provenance |
| `phia.py` | Optional PHIA adapter: one local CSV → timeline + recomputed cases |
| `agent.py` | Small rule-based agent (the system under test) with fault switches |
| `evaluation/` | One module per dimension, plus `text.py` (clause-level answer-text analysis) and `schemas.py` |
| `benchmark.py` | Runs all agent configurations, analyses faults/independence/overlaps, renders `BENCHMARK.md` |
| `external.py` | Blind case export and scoring of any external agent's answers |

## Benchmark

The authoritative, generated results are in **[BENCHMARK.md](BENCHMARK.md)**.

- **43 cases:** 41 synthetic (in the benchmark report) and 2 PHIA-derived (checked by the test suite when the PHIA data is present locally).
- **7 dimensions.** Applicable synthetic cases per dimension:

  | temporal | grounding | answer | missing data | contradiction | causal | uncertainty |
  |---|---|---|---|---|---|---|
  | 41 | 41 | 27 | 12 | 11 | 6 | 11 |

- **11 agent configurations:** a reference agent plus 10 injected faults (`input_order`, `no_as_of`, `no_window`, `silent_gaps`, `impute`, `ignore_self_report`, `dismiss_self_report`, `causal_overclaim`, `overconfident`, `false_abstention`).
  - The reference agent passes every applicable dimension on every case.
  - Each fault declares which dimensions it should fail and which knock-on failures are acceptable. The benchmark verifies this: no fault produces a missing or unexpected failure.
- **Independence:** every dimension has a case where it is the only failure, and a case where it passes while another fails. For temporal consistency, the only-failure witness is a constructed trace, because under the agent faults a temporal leak always also breaks grounding or the answer.
- **Overlaps:** every pair of dimensions that ever fails together is classified as either an intentional overlap or a shared root cause.
  - The one intentional overlap: resolving a genuine wearable/self-report conflict definitively fails both contradiction handling and uncertainty.

A pass means the answer is consistent with the case's labelled evidence semantics on that dimension. It does not mean the answer is medically correct. Because the agent is rule-based, the benchmark characterises the **evaluators**, not real agents.

### Representative failures

All examples are from the generated benchmark.

| Agent behaviour (case) | Caught by | What else happened |
|---|---|---|
| Ignores the member's self-report and cites only wearable data (`recovery_agree_good`) | grounding | Temporally correct, and no conflict to mishandle: only grounding fails. |
| Correctly reports a 2-of-7-day average with its coverage, then calls it "definitely your true average" (`unc_sparse_rhr_7d`) | uncertainty | Grounded, correct value, gap acknowledged: only the certainty level is wrong. |
| Fills a missing first day with an older reading and claims full coverage (`rhr_gap_first_day`) | missing data | Mean still within tolerance and supported by the cited readings: only coverage is misrepresented. |
| Right records and group means, but "sleeping less caused your HRV to drop" (`relation_association_only`) | causal restraint | Everything else passes; the case labels association only. |
| Cites both sources, then "you are actually well recovered" despite reported exhaustion (`recovery_conflict_good_data_exhausted`) | contradiction | Grounding passes (both sources cited); the conflict is dismissed. |
| Uses a reading synced after the question time (`rhr_mean_7d_late_sync`) | temporal | Answer and missing data fail as consequences; grounding passes (the reading is relevant and in-window). |

## Evaluate your own agent

PulseEval can score any agent (LLM-based, rule-based, or a human), not only the built-in one.

**1. Export the cases.** This writes each case's question, question time and full timeline to JSON. It is *blind*: expected values, labels and provenance are withheld.

```bash
python -m pulseeval --export-cases cases.json
```

**2. Answer them with your agent.** Return one entry per case, and cite the `record_id`s you relied on:

```json
{"format": "pulseeval-answers/1", "agent": "my-agent", "answers": [
  {"case_id": "rhr_mean_7d",
   "final_answer": "Your average resting heart rate over the last 7 days was 54.9 bpm (all 7 days had data).",
   "evidence_used": ["r0325", "r0326", "r0327", "r0328", "r0329", "r0330", "r0331"],
   "abstention": false}
]}
```

`retrieved_context` is optional and defaults to `evidence_used`.

The timeline deliberately includes records that were only logged *after* the question time. Using them is scored as a temporal failure, exactly as for the built-in agent.

**3. Score them.** This prints the same per-dimension report; add `--json` for full results. Cases you didn't answer are listed rather than silently skipped.

```bash
python -m pulseeval --evaluate answers.json
```

To see a complete, valid answers file, write the built-in agent's answers in the same format:

```bash
python -m pulseeval --agent reference --write-answers answers.json
```

A test checks the path end to end: for every built-in agent configuration, exporting its answers and evaluating them externally reproduces its built-in results check-for-check.

## Hardening (Phase 3)

The seven evaluators were stress-tested rather than only unit-tested:

- **Adversarial wording matrix:** negation, hypotheticals, quotes, concessive clauses ("despite", "while"), mixed certainty within one answer, capitalisation. Unsupported patterns are kept as strict expected-failures, so the boundary is explicit.
- **Fault-model and independence validation**, as described above.
- **Metamorphic invariants:** none of these change any outcome:
  - record order (except for the agent fault that depends on it by design);
  - unrelated records outside every window;
  - citation order;
  - letter case and whitespace;
  - repeated runs and case order.
- **Mutation testing:** 14 of 14 deliberate breakages of critical rules were caught. The rules covered temporal boundaries, grounding windows, missing-data and contradiction detection, and causal and uncertainty negation and refusal handling.
- **Provenance checks:**
  - every failure traces back to a case, an agent configuration and real records;
  - there is no randomness or wall-clock dependence;
  - PHIA labels are never read;
  - runs with and without PHIA agree on all synthetic cases.
- **Clean-copy reproduction** in a fresh virtual environment.

The hardening found and fixed **six genuine evaluator defects**, each now pinned by a regression test:
1. A current value containing a stale value ("half marathon" vs "marathon") was misread.
2. A caveat ("does not establish …") was treated as a refusal.
3. A leading concessive clause swallowed the main clause.
4. Word stemming hid a cue word.
5. Certainty about a supported observation was penalised.
6. Extra whitespace broke multi-word patterns.

## Reproducing

Requires **Python 3.10 or later**. The only runtime dependency is pydantic; pytest is used for the tests.

```bash
python -m venv .venv
```

Activate it with `.venv\Scripts\activate` on Windows or `source .venv/bin/activate` elsewhere, then:

```bash
pip install -e ".[dev]"
```

```bash
python -m pytest
```

Without the optional PHIA data, expect **442 passed, 5 skipped, 7 xfailed**:
- **5 skipped:** the tests that need PHIA data.
- **7 xfailed:** the documented parser language boundaries.

With PHIA data present, expect 447 passed and 7 xfailed. Both also hold with `--strict-markers`.

```bash
python -m pulseeval --benchmark
```

This prints the benchmark report, and its output is byte-identical to the committed `BENCHMARK.md`. A test regenerates the report and fails if they differ. The run is deterministic and needs no network access.

Other commands:

```bash
python -m pulseeval --agent reference
```

```bash
python -m pulseeval --agent overconfident --json
```

`--agent` accepts any of the 11 configurations; `--json` prints the full results. See [Evaluate your own agent](#evaluate-your-own-agent) for `--export-cases`, `--write-answers` and `--evaluate`.

CI runs the full suite on Python 3.10–3.13 for every push. It also regenerates the benchmark and fails if the output differs from `BENCHMARK.md`.

**Optional PHIA data:** to include the two PHIA-derived cases, place PHIA's `synthetic_wearable_users/summary_df_465.csv` in `data/raw/phia/`. The file is not distributed with this repository and is git-ignored. Then run:

```bash
python -m pulseeval --phia data/raw/phia
```

## Data and provenance

- **Synthetic fixtures (41 cases):** hand-written timelines for three synthetic members, covering goals, resting HR, HRV, sleep, stress reports and recovery self-reports.
  - Every expected value is derived by hand and written into the case, with its provenance.
  - Labels such as causal support or evidence sufficiency are fixture judgements, not physiological findings.
- **PHIA (2 cases):** two cases on synthetic user 465 from the PHIA repository (Merrill et al., arXiv:2406.06464, CC BY-NC 4.0): the 7- and 14-day mean resting HR, where the 14-day window has a missing day in the source data.
  - **PHIA's published labels are not used as ground truth.** They could not be reproduced from the published CSVs; for example, user 465's 7-day mean resting HR recomputes to 61.63, while PHIA's label is 61.18.
  - Expected values are recomputed by PulseEval, and each case records this.
- **MMASH:** source and license were verified, but it is not used in this version.

## Limitations

- **Rule-based system under test:** the built-in agent is deterministic and rule-based, so the published benchmark characterises the evaluators, not real (for example, LLM-based) agents.
  - Real agents can be scored through [Evaluate your own agent](#evaluate-your-own-agent), but no such results are published here.
  - Their scores will also inherit the parser language boundaries below, which matter more for freely worded LLM answers.
- **Synthetic, small benchmark:** 41 synthetic cases plus 2 PHIA-derived ones. The self-reports, relationships and certainty labels are synthetic.
- **Parser language boundaries** (strict expected-failures in `tests/test_wording.py`):
  - reported speech ("your coach said …") is treated as the agent's own claim;
  - double negation is not resolved;
  - conflict or uncertainty expressed only through unlisted wording ("opposite directions", "grain of salt") is missed;
  - single-quoted phrases are not masked.
- **Lexical analysis:** answer-text analysis uses English heuristics at the clause level. It misses paraphrases and cross-sentence negation, and it fails answers it cannot parse rather than passing them.
  - A causal claim must name both variables in one clause to be detected.
- **Temporal consistency versus record ordering:** temporal consistency checks knowability at the question time, not record ordering. Ordering mistakes surface in grounding and answer correctness.
- **Missing-data handling** assumes one expected observation per day.
- **Contradiction handling's "good / poor recovery" labels** are a fixture convention, not a physiological standard.
- **Causal restraint** judges wording against labels. It is not causal inference.
- **Uncertainty / abstention** is a behavioural check against labels. It is not a statistical, clinical or probabilistic confidence estimate.

## Status

**v1.1.** The evaluators, cases and benchmark results are unchanged since v1.0. v1.1 adds the external-agent interface and CI.

| Version / phase | Scope | Commit |
|---|---|---|
| Phase 1 | Minimal vertical slice | `c9a794d` |
| Phase 2 | Seven evaluation dimensions | `fd6f489` |
| Phase 3 | Hardening and benchmark validation | `2c2a813` |
| v1.0 (Phase 4) | Finalisation and presentation | `c0fe7ed` |
| v1.1 | External-agent interface, CI | `b31860c` |

Engineering history, design decisions (ADR-001 to ADR-014) and validation details are in [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).

## License

The PulseEval code is released under the [MIT License](LICENSE).

The license does not cover PHIA data. PHIA is a third-party dataset under CC BY-NC 4.0 (Merrill et al.). It is not included in this repository, and anyone who uses it must follow its own terms.
