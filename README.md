# PulseEval

**Longitudinal reliability evaluation for personal-health agents.**

Personal-health agents reason over wearable and contextual data that changes over time. Standard QA metrics only grade the final answer. That misses failures such as citing a goal that has since been superseded, leaking data the agent could not yet have known, or averaging over the wrong window. PulseEval is a small, deterministic-first evaluation layer. It inspects an agent's **structured trace** and scores every case on three independent dimensions:

- **temporal consistency:** was anything retrieved or cited unknowable at the time of the question?
- **evidence grounding:** is the cited evidence the right evidence for the claim? It checks that records exist, are required, relevant and in the window, support the claim, and don't contradict it.
- **answer correctness:** does the final text assert the right thing? Negated, hedged and stale values don't count.

A trace can fail one dimension and pass the others. For example, an agent that averages over the wrong window fails grounding and answer correctness but passes temporal consistency.

> Research/engineering prototype. Not a medical device. It makes no diagnostic, treatment, or clinical claims.

## Architecture

```text
Case (timeline + question + as_of + expectation + provenance)
  → HealthAgent.answer()       system under test
  → AgentTrace                 retrieved context, tool calls, evidence, answer, abstention
  → temporal_consistency | evidence_grounding | answer_correctness
  → EvaluationResult           checks + typed failures, per case and evaluator
```

| Module | Responsibility |
|---|---|
| `timeline.py` | Canonical `Record` / `MemberTimeline` with `event_time` vs `recorded_at` as-of semantics |
| `agent.py` | Small deterministic agent (the system under test) and its `AgentTrace` |
| `scenarios.py` | Synthetic fixture cases with hand-derived expectations |
| `phia.py` | Minimal PHIA adapter: one local synthetic-user CSV → timeline + recomputed numeric cases |
| `evaluation/temporal.py` | Temporal consistency (knowability at as_of) |
| `evaluation/grounding.py` | Evidence grounding |
| `evaluation/answer.py` | Answer correctness for current-state and numeric questions |
| `evaluation/text.py` | Deterministic answer-text analysis: clauses, negated/past/hedged/affirmed mentions, number+unit extraction |

## Setup

```bash
pip install -e ".[dev]"
```

## Usage

```bash
python -m pulseeval --agent reference
```

```bash
python -m pulseeval --agent no_window --json
```

`input_order`, `no_as_of` and `no_window` are fault-injected agent configs. They exist to show that each evaluator detects the behaviour it should.

To include PHIA-derived cases, place PHIA's `synthetic_wearable_users/summary_df_465.csv` in `data/raw/phia/` (it is not distributed with this repo) and run:

```bash
python -m pulseeval --phia data/raw/phia
```

```bash
python -m pytest
```

## Example evaluation (actual output, truncated)

```text
Agent: no_window (v0.2.0) | Scenarios: v0.3.0
Cases evaluated: 8
temporal_consistency (v0.3.0): 8/8 (100%)
evidence_grounding (v0.1.0): 4/8 (50%)
answer_correctness (v0.2.0): 4/8 (50%)

[FAIL] rhr_mean_7d  (temporal=PASS evidence=FAIL answer=FAIL)
    GROUNDING_FAILURE [evidence_grounding/cited_records_within_window] (high): Cited outside the window: ['o1', 'o3'].
    NUMERICAL_FAILURE [answer_correctness/value_within_tolerance] (high): actual=54.6, expected=54.857, error=0.257 bpm.
```

## Data and ground truth

- **Fixture:** six hand-written synthetic cases (goal update, temporal reversal, future record, late-arriving record, 7-day mean, late-synced reading).
- **PHIA:** two cases on PHIA synthetic user 465, the 7- and 14-day mean resting HR. The 14-day window has a missing day in the source data. Expected values were **recomputed by PulseEval** from the published CSV, and every case records its provenance.
  - PHIA's own objective-query labels are *not* used as ground truth. They could not be reproduced from the published CSVs; for example, user 465's 7-day mean resting HR recomputes to 61.63, while PHIA's label is 61.18. Details are in `PROJECT_CONTEXT.md` §8.
  - PHIA is CC BY-NC 4.0 (Merrill et al., arXiv:2406.06464).
- **MMASH:** source and license verified, not yet used.

## Limitations

- The agent is rule-based, not an LLM. It validates the evaluation pipeline and does not measure real agent behaviour.
- There are only eight cases. Results say nothing about real agents.
- Answer analysis uses lexical English heuristics. It misses paraphrases and cross-sentence negation, and fails answers it cannot parse rather than passing them.
- Not yet implemented: missing-data handling, contradiction handling (wearable vs self-report), causal restraint, uncertainty/abstention, memory.
