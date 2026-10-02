import pytest

from pulseeval.agent import HealthAgent
from pulseeval.evaluation import run_suite
from pulseeval.evaluation.schemas import FailureType
from pulseeval.evaluation.temporal import evaluate_temporal_consistency
from pulseeval.scenarios import CASES, StateCase

STATE_CASES = [c for c in CASES if isinstance(c, StateCase)]
CASE = STATE_CASES[0]  # goal_update_chronological; current = weight training, stale = marathon


def _failed(agent):
    return {r.case_id for r in run_suite(agent, STATE_CASES) if not r.passed}


def test_reference_agent_passes_all_cases():
    assert _failed(HealthAgent()) == set()


def test_input_order_fault_is_detected_on_reversed_timeline():
    assert _failed(HealthAgent(ordering="input_order")) == {"goal_update_reversed"}


def test_ignoring_as_of_is_detected_as_future_leakage():
    results = {r.case_id: r for r in run_suite(HealthAgent(respect_as_of=False), STATE_CASES)}
    assert {cid for cid, r in results.items() if not r.passed} == {
        "goal_future_record", "goal_late_arriving_record"}
    checks = {c.name: c.passed for c in results["goal_future_record"].checks}
    assert checks["no_future_evidence"] is False


def _evaluate_answer(answer):
    trace = HealthAgent().answer(CASE.timeline, CASE.question, CASE.as_of)
    return evaluate_temporal_consistency(CASE, trace.model_copy(update={"final_answer": answer}))


@pytest.mark.parametrize("answer, failing_checks", [
    ("I am not currently training for a marathon.", {"answer_asserts_current_value"}),
    ("The user previously had a marathon goal, but that is no longer current.",
     {"answer_asserts_current_value"}),
    ("Your goal might be weight training.", {"answer_asserts_current_value"}),
    ("You are not doing weight training.", {"answer_asserts_current_value"}),
    ("Your current training goal is marathon training.",
     {"answer_asserts_current_value", "answer_does_not_assert_other_value"}),
    ("Weight training is not your goal; it is marathon training.",
     {"answer_asserts_current_value", "answer_does_not_assert_other_value"}),
    ("Your goals are weight training and marathon training.",
     {"answer_does_not_assert_other_value"}),
])
def test_wrong_answers_fail_only_answer_aspect(answer, failing_checks):
    result = _evaluate_answer(answer)
    assert {c.name for c in result.checks if not c.passed} == failing_checks
    assert all(c.passed for c in result.checks if c.aspect in ("temporal", "evidence"))


@pytest.mark.parametrize("answer", [
    "Your current training goal is weight training (set 2026-03-10).",
    "The current goal is weight training, not marathon training.",
    "You switched from marathon training to weight training.",
    "Your current goal is weight training. You are no longer training for a marathon.",
    "Previously marathon training; now weight training.",
])
def test_correct_answers_pass_even_when_stale_value_is_mentioned(answer):
    assert _evaluate_answer(answer).passed


def test_wrong_evidence_with_correct_text_fails_only_evidence_aspect():
    trace = HealthAgent().answer(CASE.timeline, CASE.question, CASE.as_of)
    result = evaluate_temporal_consistency(CASE, trace.model_copy(update={"evidence_used": ["g1"]}))
    assert {c.aspect for c in result.checks if not c.passed} == {"evidence"}


def test_abstention_fails_evidence_and_answer_checks():
    trace = HealthAgent().answer(CASE.timeline, "How did I sleep?", CASE.as_of)
    assert trace.abstention and trace.evidence_used == []
    result = evaluate_temporal_consistency(CASE, trace)
    assert {c.name for c in result.checks if not c.passed} == {
        "evidence_includes_current_record", "answer_asserts_current_value"}


@pytest.mark.parametrize("case", STATE_CASES, ids=lambda c: c.case_id)
def test_failures_carry_required_fields(case):
    trace = HealthAgent(ordering="input_order", respect_as_of=False).answer(
        case.timeline, case.question, case.as_of)
    result = evaluate_temporal_consistency(case, trace)
    for f in result.failures:
        assert f.failure_type is FailureType.TEMPORAL_FAILURE
        assert f.query == case.question and f.trace == trace
        assert f.expected_behavior and f.actual_behavior and f.explanation
    assert result.passed == (not result.failures)


def test_template_words_do_not_create_false_stale_mentions():
    # "training goal" must not count as a mention of "marathon training".
    case = next(c for c in STATE_CASES if c.case_id == "goal_future_record")
    trace = HealthAgent(respect_as_of=False).answer(case.timeline, case.question, case.as_of)
    result = evaluate_temporal_consistency(case, trace)
    check = next(c for c in result.checks if c.name == "answer_does_not_assert_other_value")
    assert check.explanation == "Asserted as current: ['half marathon']."
