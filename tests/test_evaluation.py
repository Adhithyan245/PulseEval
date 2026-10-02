import pytest

from pulseeval.agent import HealthAgent
from pulseeval.evaluation import FailureType, evaluate_temporal_consistency, run_suite
from pulseeval.scenarios import CASES


def _failed(agent):
    return {r.case_id for r in run_suite(agent, CASES) if not r.passed}


def test_reference_agent_passes_all_cases():
    assert _failed(HealthAgent()) == set()


def test_input_order_fault_is_detected_on_reversed_timeline():
    assert _failed(HealthAgent(ordering="input_order")) == {"goal_update_reversed"}


def test_ignoring_as_of_is_detected_as_future_leakage():
    results = {r.case_id: r for r in run_suite(HealthAgent(respect_as_of=False), CASES)}
    assert {cid for cid, r in results.items() if not r.passed} == {
        "goal_future_record", "goal_late_arriving_record"}
    checks = {c.name: c.passed for c in results["goal_future_record"].checks}
    assert checks["no_future_evidence"] is False


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_failures_carry_required_fields(case):
    trace = HealthAgent(ordering="input_order", respect_as_of=False).answer(
        case.timeline, case.question, case.as_of)
    result = evaluate_temporal_consistency(case, trace)
    for f in result.failures:
        assert f.failure_type is FailureType.TEMPORAL_FAILURE
        assert f.query == case.question and f.trace == trace
        assert f.expected_behavior and f.actual_behavior and f.explanation
    assert result.passed == (not result.failures)


def test_abstention_fails_current_state_checks():
    case = CASES[0]
    trace = HealthAgent().answer(case.timeline, "How did I sleep?", case.as_of)
    assert trace.abstention and trace.evidence_used == []
    result = evaluate_temporal_consistency(case, trace)
    assert {c.name for c in result.checks if not c.passed} == {
        "uses_current_state", "answer_states_current_value"}
