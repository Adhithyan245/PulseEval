"""Contradiction handling: wearable signals vs. synthetic self-reports (ADR-010)."""

import pytest

from pulseeval.agent import HealthAgent
from pulseeval.evaluation import run_suite
from pulseeval.evaluation.contradiction import evaluate_contradiction_handling
from pulseeval.evaluation.grounding import evaluate_evidence_grounding
from pulseeval.evaluation.schemas import FailureType
from pulseeval.evaluation.temporal import evaluate_temporal_consistency
from pulseeval.scenarios import CASES, AssessmentCase

BY_ID = {c.case_id: c for c in CASES}
ASSESSMENTS = [c for c in CASES if isinstance(c, AssessmentCase)]
CONFLICT = BY_ID["recovery_conflict_good_data_exhausted"]
AGREE = BY_ID["recovery_agree_good"]
WEARABLE = ("Your wearable data suggests good recovery today (HRV 68 ms vs a 7-day average "
            "of 55 ms; resting heart rate 51 bpm vs 56 bpm).")


def _results(case, answer=None, agent=None):
    trace = (agent or HealthAgent()).answer(case.timeline, case.question, case.as_of)
    if answer is not None:
        trace = trace.model_copy(update={"final_answer": answer})
    return {"contradiction": evaluate_contradiction_handling(case, trace),
            "grounding": evaluate_evidence_grounding(case, trace),
            "temporal": evaluate_temporal_consistency(case, trace)}


def _failed(result):
    return {c.name for c in result.checks if not c.passed}


def test_hand_labels_mark_exactly_the_conflict_cases():
    assert {c.case_id for c in ASSESSMENTS if c.conflict} == {
        "recovery_conflict_good_data_exhausted", "recovery_conflict_poor_data_energetic",
        "unc_conflict_recovery"}
    # mixed wearable signals with no self-report are ambiguous, not a conflict (ADR-012)
    assert not BY_ID["unc_ambiguous_recovery"].conflict


def test_intensified_verdict_after_flagging_conflict_is_unsupported_resolution():
    # regression (contradiction v0.1.1): "definitely" between "you are" and the verdict
    # previously hid the verdict from no_unsupported_resolution
    answer = (WEARABLE + " You reported feeling exhausted this morning. These two signals "
                         "conflict, but you are definitely well recovered.")
    assert _failed(_results(CONFLICT, answer)["contradiction"]) == {"no_unsupported_resolution"}


@pytest.mark.parametrize("case", ASSESSMENTS, ids=lambda c: c.case_id)
def test_reference_agent_handles_every_assessment(case):
    assert all(r.passed for r in _results(case).values())


@pytest.mark.parametrize("answer", [
    WEARABLE + " You reported feeling exhausted this morning. These two signals conflict.",
    WEARABLE + " However, you said you feel exhausted, so your data and how you feel "
               "don't match.",
    WEARABLE + " You reported feeling exhausted, which is inconsistent with the data; "
               "your recovery may be lower than the numbers suggest.",
])
def test_conflict_acknowledged_without_resolution_passes(answer):
    assert _results(CONFLICT, answer)["contradiction"].passed


@pytest.mark.parametrize("answer, failing", [
    # wearable only: the self-report is ignored
    (WEARABLE, {"both_sources_acknowledged", "conflict_flagged"}),
    # self-report only, with a verdict built on it
    ("You reported feeling exhausted, so you are poorly recovered.",
     {"both_sources_acknowledged", "conflict_flagged", "no_unsupported_resolution"}),
    # both mentioned, conflict never named
    (WEARABLE + " You reported feeling exhausted this morning.", {"conflict_flagged"}),
    # conflict named, then resolved by fiat
    (WEARABLE + " You reported feeling exhausted. These signals conflict. You are well "
                "recovered.", {"no_unsupported_resolution"}),
    # self-report dismissed
    (WEARABLE + " You reported feeling exhausted, but you are actually fine.",
     {"conflict_flagged", "no_source_dismissed"}),
    # wearable dismissed
    (WEARABLE + " You reported feeling exhausted. These signals conflict, and the device "
                "is wrong.", {"no_source_dismissed"}),
])
def test_mishandled_conflicts_fail_specific_checks(answer, failing):
    result = _results(CONFLICT, answer)["contradiction"]
    assert _failed(result) == failing
    assert all(f.failure_type is FailureType.CONTRADICTION_FAILURE for f in result.failures)


def test_agreement_needs_no_conflict_statement():
    assert _results(AGREE, WEARABLE)["contradiction"].passed


def test_agreement_with_invented_conflict_fails():
    answer = WEARABLE + " You reported feeling rested. These two signals conflict."
    assert _failed(_results(AGREE, answer)["contradiction"]) == {"no_invented_conflict"}


def test_negated_conflict_is_not_a_conflict_claim():
    answer = WEARABLE + " You reported feeling rested; your report and your data do not conflict."
    assert _results(AGREE, answer)["contradiction"].passed


def test_definitive_verdict_is_fine_when_sources_agree():
    answer = WEARABLE + " You reported feeling rested, and you are well recovered."
    assert _results(AGREE, answer)["contradiction"].passed


def test_negated_dismissal_is_not_a_dismissal():
    answer = (WEARABLE + " You reported feeling exhausted. These signals conflict, so don't "
                         "ignore how you feel.")
    assert _results(CONFLICT, answer)["contradiction"].passed


def test_dismissing_agent_fails_only_contradiction():
    results = _results(CONFLICT, agent=HealthAgent(dismiss_self_report=True))
    assert _failed(results["contradiction"]) == {"conflict_flagged", "no_source_dismissed"}
    assert results["grounding"].passed and results["temporal"].passed


def test_ignoring_agent_fails_grounding_and_contradiction():
    results = _results(CONFLICT, agent=HealthAgent(ignore_self_report=True))
    assert _failed(results["grounding"]) == {"cites_required_records"}
    assert _failed(results["contradiction"]) == {"both_sources_acknowledged", "conflict_flagged"}
    assert results["temporal"].passed


def test_late_self_report_is_temporal_leak_and_invented_conflict():
    case = BY_ID["recovery_late_self_report"]
    results = _results(case, agent=HealthAgent(respect_as_of=False))
    assert not results["temporal"].passed
    assert _failed(results["contradiction"]) == {"no_invented_conflict"}
    assert results["grounding"].passed  # the report is relevant and in-window, just unknowable


def test_stale_self_report_is_out_of_window_and_invented_conflict():
    case = BY_ID["recovery_stale_self_report"]
    results = _results(case, agent=HealthAgent(respect_window=False))
    assert _failed(results["grounding"]) == {"cited_records_within_window"}
    assert _failed(results["contradiction"]) == {"no_invented_conflict"}
    assert results["temporal"].passed


def test_only_assessments_are_evaluated_for_contradiction():
    evaluated = {r.case_id for r in run_suite(HealthAgent(), CASES)
                 if r.evaluator == "contradiction_handling"}
    assert evaluated == {c.case_id for c in ASSESSMENTS}
    assert not {r.case_id for r in run_suite(HealthAgent(), ASSESSMENTS)
                if r.evaluator in ("answer_correctness", "missing_data")}
