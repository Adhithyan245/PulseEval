from statistics import mean

import pytest

from pulseeval.agent import HealthAgent
from pulseeval.evaluation import run_suite
from pulseeval.evaluation.numerical import evaluate_numerical_correctness
from pulseeval.scenarios import CASES, NumericCase

NUMERIC_CASES = [c for c in CASES if isinstance(c, NumericCase)]
CASE = NUMERIC_CASES[0]  # rhr_mean_7d, expected 54.857 bpm, tolerance 0.1


@pytest.mark.parametrize("case", NUMERIC_CASES, ids=lambda c: c.case_id)
def test_hand_labelled_expectations_match_labelled_readings(case):
    values = [float(case.timeline.get(rid).value) for rid in case.expected_record_ids]
    assert mean(values) == pytest.approx(case.expected_value, abs=1e-3)


def _failed_checks(agent):
    return {r.case_id: {c.name for c in r.checks if not c.passed}
            for r in run_suite(agent, NUMERIC_CASES) if not r.passed}


def test_reference_and_input_order_agents_pass():
    assert _failed_checks(HealthAgent()) == {}
    assert _failed_checks(HealthAgent(ordering="input_order")) == {}


def test_ignoring_window_is_detected():
    assert _failed_checks(HealthAgent(respect_window=False)) == {
        "rhr_mean_7d": {"evidence_matches_expected_readings", "value_within_tolerance"},
        "rhr_mean_7d_late_sync": {"evidence_matches_expected_readings", "value_within_tolerance"},
    }


def test_late_synced_reading_is_detected():
    assert _failed_checks(HealthAgent(respect_as_of=False)) == {
        "rhr_mean_7d_late_sync": {"no_future_evidence", "evidence_matches_expected_readings",
                                  "value_within_tolerance"},
    }


def _evaluate_answer(answer, case=CASE):
    trace = HealthAgent().answer(case.timeline, case.question, case.as_of)
    return evaluate_numerical_correctness(case, trace.model_copy(update={"final_answer": answer}))


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
