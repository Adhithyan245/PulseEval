# PulseEval

**Longitudinal reliability evaluation for personal-health agents.**

Personal-health agents reason over wearable and contextual data that changes over time. Standard QA metrics only grade the final answer. That misses failures such as using a goal that has since been superseded, leaking data the agent could not yet have known, or averaging over the wrong window. PulseEval is a small, deterministic-first evaluation layer. It inspects an agent's **structured trace** and separates three kinds of error:

- **temporal:** the agent used something that was not knowable at the time of the question
- **evidence:** the agent cited the wrong records
- **answer:** the final text asserts the wrong thing, for example a negated, hedged or stale value

> Research/engineering prototype. Not a medical device. It makes no diagnostic, treatment, or clinical claims.

## Architecture

```text
Case (timeline + question + as_of + hand-labelled expectation)
  → HealthAgent.answer()      system under test
  → AgentTrace                retrieved context, tool calls, evidence, answer, abstention
  → evaluator (by case kind)  temporal consistency | numerical correctness
  → EvaluationResult          aspect-tagged checks + typed failures
```

| Module | Responsibility |
|---|---|
| `timeline.py` | Canonical `Record` / `MemberTimeline` with `event_time` vs `recorded_at` as-of semantics |
| `agent.py` | Small deterministic agent (the system under test) and its `AgentTrace` |
| `scenarios.py` | Evaluation cases with hand-labelled ground truth |
| `evaluation/temporal.py` | Temporal consistency for "what is my current X?" questions |
| `evaluation/numerical.py` | Tolerance-based numerical correctness for aggregate questions |
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

`input_order`, `no_as_of` and `no_window` are fault-injected agent configs. They exist to show that the evaluators detect known-bad behaviour.

```bash
python -m pytest
```

## Example evaluation (actual output, truncated)

```text
Agent: no_as_of (v0.2.0) | Scenarios: v0.2.0
Cases evaluated: 6
temporal_consistency (v0.2.0): 2/4 (50%)
numerical_correctness (v0.1.0): 1/2 (50%)

[FAIL] goal_future_record
    TEMPORAL_FAILURE [temporal/no_future_evidence] (high): Retrieved/cited records not knowable at as_of: ['g3'].
    TEMPORAL_FAILURE [evidence/evidence_includes_current_record] (high): Evidence used: ['g3'].
    TEMPORAL_FAILURE [answer/answer_does_not_assert_other_value] (high): Asserted as current: ['half marathon'].
[FAIL] rhr_mean_7d_late_sync
    TEMPORAL_FAILURE [temporal/no_future_evidence] (high): Retrieved/cited records not knowable at as_of: ['r0331'].
    NUMERICAL_FAILURE [evidence/evidence_matches_expected_readings] (high): Missing: []; extra: ['r0331'].
    NUMERICAL_FAILURE [answer/value_within_tolerance] (high): actual=56, expected=55, error=1 bpm.
```

## Current capabilities

- **Temporal consistency:** no future or late-arriving evidence, the current record is cited, the current value is affirmed, and no other value is asserted as current.
- **Numerical correctness:** no unknowable readings, the cited readings match the labelled window, exactly one affirmed value with the unit, and that value is within an absolute tolerance.
- **Cases:** six synthetic cases covering a goal update, temporal reversal, a future record, a late-arriving record, a 7-day mean, and a late-synced reading.
- **Adversarial answer tests:** negated, past-framed, hedged and stale answers, plus ranges and missing units.

## Data

The suite currently runs only on a hand-written synthetic fixture. PHIA and MMASH have been checked for source, license and structure (see `PROJECT_CONTEXT.md` §8), but neither is integrated yet. Raw data stays in a git-ignored `data/raw/`.

## Limitations

- The agent is rule-based, not an LLM. It validates the evaluation pipeline and does not measure real agent behaviour.
- The data is tiny and synthetic: one member, six cases.
- Answer analysis uses lexical English heuristics. It misses paraphrases and cross-sentence negation, and fails answers it cannot parse rather than passing them.
- Not yet implemented: evidence grounding, contradiction, causal restraint, missing data, uncertainty/abstention, memory.
