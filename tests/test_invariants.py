"""Metamorphic / invariant tests (Phase 3): transformations that must not change outcomes.

Only invariants that are part of PulseEval's intended semantics are encoded:
  - record order in the timeline is not meaningful (except for the `input_order` fault,
    whose whole point is to depend on it)
  - an unrelated record far outside every window changes nothing
  - the order of cited record ids is not meaningful
  - letter case and runs of whitespace in the answer are not meaningful
  - the same inputs always give the same results (no hidden state, randomness or ordering)
"""

import json
from datetime import datetime

import pytest

from pulseeval.benchmark import AGENT_CONFIGS
from pulseeval.evaluation import EVALUATORS, run_suite
from pulseeval.scenarios import CASES
from pulseeval.timeline import Record

ORDER_FREE = {k: v for k, v in AGENT_CONFIGS.items() if k != "input_order"}


def _outcome(case, trace):
    """Per evaluator: the set of failing check names (None = not applicable)."""
    out = {}
    for evaluate in EVALUATORS:
        result = evaluate(case, trace)
        out[evaluate.__name__] = (None if result is None else
                                  frozenset(c.name for c in result.checks if not c.passed))
    return out


def _with_timeline(case, records):
    return case.model_copy(update={"timeline": case.timeline.model_copy(
        update={"records": records}), "certainty": case.certainty})


@pytest.mark.parametrize("agent_name", ORDER_FREE)
def test_timeline_record_order_does_not_matter(agent_name):
    agent = ORDER_FREE[agent_name]
    for case in CASES:
        flipped = _with_timeline(case, list(reversed(case.timeline.records)))
        assert (_outcome(case, agent.answer(case.timeline, case.question, case.as_of))
                == _outcome(flipped, agent.answer(flipped.timeline, flipped.question,
                                                  flipped.as_of))), case.case_id


@pytest.mark.parametrize("agent_name", AGENT_CONFIGS)
def test_unrelated_record_outside_every_window_changes_nothing(agent_name):
    agent = AGENT_CONFIGS[agent_name]
    noise = Record(record_id="noise", kind="context", name="unrelated_note", value="n/a",
                   event_time=datetime(2020, 1, 1), recorded_at=datetime(2020, 1, 1),
                   source="test-fixture")
    for case in CASES:
        noisy = _with_timeline(case, case.timeline.records + [noise])
        base = _outcome(case, agent.answer(case.timeline, case.question, case.as_of))
        assert base == _outcome(noisy, agent.answer(noisy.timeline, noisy.question,
                                                    noisy.as_of)), case.case_id


@pytest.mark.parametrize("agent_name", AGENT_CONFIGS)
def test_citation_order_does_not_matter(agent_name):
    agent = AGENT_CONFIGS[agent_name]
    for case in CASES:
        trace = agent.answer(case.timeline, case.question, case.as_of)
        flipped = trace.model_copy(update={"evidence_used": list(reversed(trace.evidence_used)),
                                           "retrieved_context": list(reversed(
                                               trace.retrieved_context))})
        assert _outcome(case, trace) == _outcome(case, flipped), case.case_id


@pytest.mark.parametrize("transform", [str.upper, str.lower,
                                       lambda s: s.replace(" ", "   "),
                                       lambda s: "  " + s.replace(". ", ".\n") + "  "],
                         ids=["upper", "lower", "spaces", "newlines"])
@pytest.mark.parametrize("agent_name", AGENT_CONFIGS)
def test_answer_case_and_whitespace_do_not_matter(agent_name, transform):
    agent = AGENT_CONFIGS[agent_name]
    for case in CASES:
        trace = agent.answer(case.timeline, case.question, case.as_of)
        varied = trace.model_copy(update={"final_answer": transform(trace.final_answer)})
        assert _outcome(case, trace) == _outcome(case, varied), (case.case_id, varied.final_answer)


@pytest.mark.parametrize("agent_name", AGENT_CONFIGS)
def test_repeated_runs_and_case_order_give_identical_results(agent_name):
    agent = AGENT_CONFIGS[agent_name]

    def dump(cases):
        return {r.case_id + "/" + r.evaluator: json.dumps(r.model_dump(mode="json"),
                                                         sort_keys=True)
                for r in run_suite(agent, cases)}

    first = dump(CASES)
    assert first == dump(CASES)
    assert first == dump(list(reversed(CASES)))
