# PulseEval

**Longitudinal reliability evaluation for personal-health agents.**

Personal-health agents reason over wearable and contextual data that changes over time. Standard QA metrics only grade the final answer. That misses failures such as using a goal that has since been superseded, leaking data the agent could not yet have known, or getting events out of order. PulseEval is a small, deterministic-first evaluation layer that inspects an agent's **structured trace** and reports these failures.

> Research/engineering prototype. Not a medical device. It makes no diagnostic, treatment, or clinical claims.

## Architecture

```text
Case (timeline + question + as_of + hand-labelled expectation)
  → HealthAgent.answer()             system under test
  → AgentTrace                       retrieved context, tool calls, evidence, answer, abstention
  → evaluate_temporal_consistency()  deterministic checks
  → EvaluationResult                 checks + typed failures
```

| Module | Responsibility |
|---|---|
| `timeline.py` | Canonical `Record` / `MemberTimeline` with `event_time` vs `recorded_at` as-of semantics |
| `agent.py` | Small deterministic agent (the system under test) and its `AgentTrace` |
| `evaluation.py` | Failure taxonomy, result schemas, evaluators |
| `scenarios.py` | Evaluation cases with hand-labelled ground truth |

## Setup

```bash
pip install -e ".[dev]"
```

## Usage

```bash
python -m pulseeval --agent reference
```

```bash
python -m pulseeval --agent input_order --json
```

`input_order` and `no_as_of` are fault-injected agent configs. They exist to show that the evaluator detects known-bad behaviour.

```bash
python -m pytest
```

## Example evaluation (actual output)

```text
Agent: input_order (v0.1.0) | Evaluator: temporal_consistency (v0.1.0) | Scenarios: v0.1.0
Cases evaluated: 4
Temporal consistency: 3/4 (75%)

[PASS] goal_update_chronological
[FAIL] goal_update_reversed
    TEMPORAL_FAILURE (high): Evidence used: ['g1'].
    TEMPORAL_FAILURE (medium): Answer: 'Your current training goal is marathon training (set 2026-01-05).'.
[PASS] goal_future_record
[PASS] goal_late_arriving_record
```

## Current capabilities

- Temporal-consistency evaluator with three checks: no future or late-arriving evidence, use of the current state, and an answer consistent with that state.
- Four synthetic cases covering a goal update, temporal reversal, a future record, and a late-arriving record.

## Limitations

- The agent is rule-based, not an LLM. It validates the evaluation pipeline and does not measure real agent behaviour.
- The data is a tiny synthetic fixture (one member, four cases). No real dataset (MMASH, PHIA) is integrated yet.
- The answer check uses substring matching.
- Only temporal consistency is implemented. Other dimensions (numerical, grounding, contradiction, causal restraint, missing data, uncertainty/abstention, memory) are planned.
