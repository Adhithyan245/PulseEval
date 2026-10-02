from statistics import mean

import pytest

from pulseeval.agent import HealthAgent
from pulseeval.evaluation.answer import evaluate_answer_correctness
from pulseeval.evaluation.temporal import evaluate_temporal_consistency
from pulseeval.scenarios import CASES, NumericCase, StateCase

NUMERIC_CASES = [c for c in CASES if isinstance(c, NumericCase)]
CASE = NUMERIC_CASES[0]  # rhr_mean_7d, expected 54.857 bpm, tolerance 0.1
STATE = next(c for c in CASES if isinstance(c, StateCase))  # current = weight training


@pytest.mark.parametrize("case", NUMERIC_CASES, ids=lambda c: c.case_id)
def test_hand_labelled_expectations_match_labelled_readings(case):
    values = [float(case.timeline.get(rid).value) for rid in case.expected_record_ids]
    assert mean(values) == pytest.approx(case.expected_value, abs=1e-3)


def _evaluate_answer(answer, case=CASE):
    trace = HealthAgent().answer(case.timeline, case.question, case.as_of)
    return evaluate_answer_correctness(case, trace.model_copy(update={"final_answer": answer}))


@pytest.mark.parametrize("answer", [
    "Your average was 54.9 bpm.",
    "Over the last 7 days you averaged 54.86 bpm.",
    "Not 60 bpm, but 54.9 bpm.",
])
def test_correct_answers_pass(answer):
    assert _evaluate_answer(answer).passed


@pytest.mark.parametrize("answer, failing_checks", [
    ("Your average was 55 bpm.", {"value_within_tolerance"}),
    ("Your average was 60 bpm.", {"value_within_tolerance"}),
    ("Your average was 54.9.", {"value_extracted", "value_within_tolerance"}),
    ("It was between 54 bpm and 56 bpm.", {"value_extracted", "value_within_tolerance"}),
    ("Your average might be 54.9 bpm.", {"value_extracted", "value_within_tolerance"}),
    ("Your average was not 54.9 bpm.", {"value_extracted", "value_within_tolerance"}),
])
def test_incorrect_answers_fail(answer, failing_checks):
    result = _evaluate_answer(answer)
    assert {c.name for c in result.checks if not c.passed} == failing_checks
    assert "failed" in result.failures[0].explanation


def test_value_exactly_at_tolerance_passes():
    assert _evaluate_answer("Your average was 54.957 bpm.").passed  # error == 0.1


def test_tolerance_is_configurable():
    loose = CASE.model_copy(update={"tolerance": 0.2})
    assert not _evaluate_answer("Your average was 55 bpm.").passed
    assert _evaluate_answer("Your average was 55 bpm.", loose).passed


# --- state answers ------------------------------------------------------------

def _state_answer(answer):
    trace = HealthAgent().answer(STATE.timeline, STATE.question, STATE.as_of)
    trace = trace.model_copy(update={"final_answer": answer})
    return evaluate_answer_correctness(STATE, trace), evaluate_temporal_consistency(STATE, trace)


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
def test_wrong_state_answers_fail_answer_but_not_temporal(answer, failing_checks):
    answer_result, temporal_result = _state_answer(answer)
    assert {c.name for c in answer_result.checks if not c.passed} == failing_checks
    assert temporal_result.passed


@pytest.mark.parametrize("answer", [
    "Your current training goal is weight training (set 2026-03-10).",
    "The current goal is weight training, not marathon training.",
    "You switched from marathon training to weight training.",
    "Your current goal is weight training. You are no longer training for a marathon.",
    "Previously marathon training; now weight training.",
])
def test_correct_state_answers_pass_even_when_stale_value_is_mentioned(answer):
    assert _state_answer(answer)[0].passed


def test_template_words_do_not_create_false_stale_mentions():
    # "training goal" must not count as a mention of "marathon training".
    case = next(c for c in CASES if c.case_id == "goal_future_record")
    trace = HealthAgent(respect_as_of=False).answer(case.timeline, case.question, case.as_of)
    check = next(c for c in evaluate_answer_correctness(case, trace).checks
                 if c.name == "answer_does_not_assert_other_value")
    assert check.explanation == "Asserted as current: ['half marathon']."
