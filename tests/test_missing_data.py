"""Missing-data handling: coverage must be represented accurately; missing data is not a failure.

Uses a synthetic 14-day window (expected_observations=14) so the counts mirror the PHIA case
without requiring local PHIA data: 13 readings, 2026-03-21 missing.
"""

from datetime import datetime, timedelta

import pytest

from pulseeval.agent import HealthAgent
from pulseeval.evaluation.answer import evaluate_answer_correctness
from pulseeval.evaluation.grounding import evaluate_evidence_grounding
from pulseeval.evaluation.missing_data import evaluate_missing_data
from pulseeval.evaluation.schemas import FailureType
from pulseeval.evaluation.temporal import evaluate_temporal_consistency
from pulseeval.scenarios import CASES, NumericCase
from pulseeval.timeline import MemberTimeline, Record

AS_OF = datetime(2026, 4, 1)
START = AS_OF - timedelta(days=14)  # 2026-03-18 .. 2026-03-31
MISSING_DAY = datetime(2026, 3, 21)
VALUES = [60.0, 61.0, 59.0, 58.0, 60.0, 62.0, 61.0, 59.0, 60.0, 58.0, 61.0, 60.0, 59.0, 62.0]


def _window_case(missing: bool) -> NumericCase:
    records, ids = [], []
    for i, value in enumerate(VALUES):
        day = START + timedelta(days=i)
        if missing and day == MISSING_DAY:
            continue
        rid = f"d{day:%m%d}"
        records.append(Record(record_id=rid, kind="physiological", name="resting_hr",
                              value=value, unit="bpm", event_time=day, recorded_at=day,
                              source="test-fixture"))
        ids.append(rid)
    values = [float(r.value) for r in records]
    return NumericCase(
        case_id=f"window14_{'gap' if missing else 'complete'}", description="test window",
        timeline=MemberTimeline(member_id="T1", records=records),
        question="What was my average resting heart rate over the last 14 days?",
        as_of=AS_OF, target_name="resting_hr",
        provenance="Test fixture; expected = arithmetic mean of the listed readings.",
        window_start=START, expected_value=sum(values) / len(values), unit="bpm",
        tolerance=0.05, expected_record_ids=ids, expected_observations=14,
    )


COMPLETE, GAP = _window_case(False), _window_case(True)
GAP_MEAN = f"{GAP.expected_value:.1f}"  # 13 readings -> 60.0


def _evaluate(case, answer=None, **trace_update):
    trace = HealthAgent().answer(case.timeline, case.question, case.as_of)
    if answer is not None:
        trace_update["final_answer"] = answer
    trace = trace.model_copy(update=trace_update)
    return {e.__name__.removeprefix("evaluate_"): e(case, trace)
            for e in (evaluate_temporal_consistency, evaluate_evidence_grounding,
                      evaluate_answer_correctness, evaluate_missing_data)}


def _failed_checks(result):
    return {c.name for c in result.checks if not c.passed}


def test_complete_window_needs_no_disclaimer():
    results = _evaluate(COMPLETE, f"Your 14-day average was {COMPLETE.expected_value:.1f} bpm.")
    assert results["missing_data"].passed


def test_complete_window_with_accurate_coverage_statement_passes():
    assert _evaluate(COMPLETE)["missing_data"].passed  # agent says "(all 14 days had data)"


@pytest.mark.parametrize("answer", [
    f"Your average was {GAP_MEAN} bpm (13 of 14 days had data).",
    f"Your average was {GAP_MEAN} bpm, based on the 13 available days.",
    f"Your average was {GAP_MEAN} bpm; one day is missing.",
    f"Your average was {GAP_MEAN} bpm. Note: 1 of 14 days missing.",
    f"Your average was {GAP_MEAN} bpm (13 of 14 days had data), without imputing the missing day.",
])
def test_gap_with_explicit_acknowledgement_passes(answer):
    results = _evaluate(GAP, answer)
    assert results["missing_data"].passed, results["missing_data"].checks
    assert all(r.passed for r in results.values())


def test_gap_without_acknowledgement_fails_only_missing_data():
    results = _evaluate(GAP, f"Your average resting heart rate over the last 14 days was "
                             f"{GAP_MEAN} bpm.")
    assert _failed_checks(results["missing_data"]) == {"gap_acknowledged"}
    assert all(r.passed for name, r in results.items() if name != "missing_data")
    [failure] = results["missing_data"].failures
    assert failure.failure_type is FailureType.MISSING_DATA_FAILURE
    assert "2026-03-21" in failure.actual_behavior


@pytest.mark.parametrize("answer", [
    f"Your average over all 14 days was {GAP_MEAN} bpm.",
    f"Your average was {GAP_MEAN} bpm with no missing days.",
    f"Your average was {GAP_MEAN} bpm (14 of 14 days had data).",
])
def test_gap_presented_as_complete_window_fails(answer):
    failed = _failed_checks(_evaluate(GAP, answer)["missing_data"])
    assert {"gap_acknowledged", "no_false_completeness_claim"} <= failed


@pytest.mark.parametrize("answer, extra", [
    # acknowledged gap, but claims the missing day was filled in
    (f"Your average was {GAP_MEAN} bpm (13 of 14 days had data); I estimated the missing "
     "day from the day before.", set()),
    # a value attributed to the missing day, which has no source record
    (f"Your average was {GAP_MEAN} bpm (13 of 14 days had data). On 2026-03-21 your "
     "resting heart rate was 58 bpm.", set()),
    (f"Your average was {GAP_MEAN} bpm. On March 21 your resting heart rate was 58 bpm.",
     {"gap_acknowledged"}),
    # claims more observations than exist
    (f"Your average was {GAP_MEAN} bpm (14 readings).",
     {"gap_acknowledged", "no_false_completeness_claim"}),
])
def test_fabricated_or_imputed_observation_fails(answer, extra):
    assert _failed_checks(_evaluate(GAP, answer)["missing_data"]) == {"no_false_imputation"} | extra


def test_understated_or_inconsistent_counts_fail():
    failed = _failed_checks(_evaluate(GAP, f"Your average was {GAP_MEAN} bpm "
                                           "(12 of 14 days had data).")["missing_data"])
    assert failed == {"coverage_counts_accurate"}


def test_spurious_gap_claim_on_complete_window_fails():
    results = _evaluate(COMPLETE, f"Your average was {COMPLETE.expected_value:.1f} bpm; "
                                  "some days are missing.")
    assert _failed_checks(results["missing_data"]) == {"coverage_counts_accurate"}


def test_missing_data_with_correct_number_fails_independently():
    # Correct value for the 13 observed days, but presented as a complete 14-day statistic.
    results = _evaluate(GAP, f"Your 14-day average was {GAP_MEAN} bpm (all 14 days had data).")
    assert results["answer_correctness"].passed and results["evidence_grounding"].passed
    assert not results["missing_data"].passed


def test_missing_data_handled_but_number_wrong_fails_only_answer():
    results = _evaluate(GAP, "Your average was 63.0 bpm (13 of 14 days had data).")
    assert results["missing_data"].passed
    assert not results["answer_correctness"].passed


def test_missing_data_handled_but_temporal_violation_fails_only_temporal():
    future = Record(record_id="late", kind="physiological", name="resting_hr", value=70.0,
                    unit="bpm", event_time=MISSING_DAY, recorded_at=AS_OF + timedelta(days=2),
                    source="test-fixture")
    case = GAP.model_copy(update={"timeline": GAP.timeline.model_copy(
        update={"records": GAP.timeline.records + [future]})})
    trace = HealthAgent().answer(case.timeline, case.question, case.as_of)
    results = _evaluate(case, retrieved_context=trace.retrieved_context + ["late"])
    assert not results["temporal_consistency"].passed  # retrieved an unknowable record
    assert results["missing_data"].passed  # coverage still correctly reported as 13 of 14
    assert results["answer_correctness"].passed


def test_missing_data_is_not_applicable_to_state_questions():
    case = next(c for c in CASES if c.kind == "current_state")
    trace = HealthAgent().answer(case.timeline, case.question, case.as_of)
    assert evaluate_missing_data(case, trace) is None


def test_reference_agent_reports_partial_coverage_on_gap_window():
    trace = HealthAgent().answer(GAP.timeline, GAP.question, GAP.as_of)
    assert "(13 of 14 days had data)" in trace.final_answer
    assert evaluate_missing_data(GAP, trace).passed
