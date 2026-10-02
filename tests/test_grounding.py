"""Evidence grounding: good, wrong, missing, temporally invalid, unsupported, contradictory."""

from datetime import datetime

import pytest

from pulseeval.agent import HealthAgent
from pulseeval.evaluation.answer import evaluate_answer_correctness
from pulseeval.evaluation.grounding import evaluate_evidence_grounding
from pulseeval.evaluation.schemas import FailureType
from pulseeval.evaluation.temporal import evaluate_temporal_consistency
from pulseeval.scenarios import CASES
from pulseeval.timeline import Record

BY_ID = {c.case_id: c for c in CASES}
NUM = BY_ID["rhr_mean_7d"]  # evidence r0325..r0331, mean 54.857, answer "54.9 bpm", tol 0.1
STATE = BY_ID["goal_update_chronological"]  # evidence g2, answer "weight training"
WEEK = [f"r03{d}" for d in range(25, 32)]


def _ground(case, **update):
    trace = HealthAgent().answer(case.timeline, case.question, case.as_of)
    trace = trace.model_copy(update=update)
    return evaluate_evidence_grounding(case, trace), trace


def _failed(result):
    return {c.name for c in result.checks if not c.passed}


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_reference_agent_evidence_is_grounded(case):
    assert _ground(case)[0].passed


def test_fabricated_record_id_fails_only_existence():
    result, trace = _ground(NUM, evidence_used=WEEK + ["r9999"])
    assert _failed(result) == {"cited_records_exist"}
    assert all(f.failure_type is FailureType.GROUNDING_FAILURE for f in result.failures)
    # The other dimensions are unaffected by a bad citation alone.
    assert evaluate_temporal_consistency(NUM, trace).passed
    assert evaluate_answer_correctness(NUM, trace).passed


def test_irrelevant_record_in_window_fails_relevance():
    sleep = Record(record_id="s0328", kind="sleep", name="sleep_duration", value=7.0, unit="h",
                   event_time=datetime(2026, 3, 28), recorded_at=datetime(2026, 3, 28),
                   source="fixture")
    case = NUM.model_copy(update={"timeline": NUM.timeline.model_copy(
        update={"records": NUM.timeline.records + [sleep]})})
    result, _ = _ground(case, evidence_used=WEEK + ["s0328"])
    assert _failed(result) == {"cited_records_relevant"}


def test_wrong_record_for_state_claim():
    result, _ = _ground(STATE, evidence_used=["o1"])  # a resting-HR reading, not a goal
    assert _failed(result) == {"cites_required_records", "cited_records_relevant",
                               "evidence_supports_claim"}


def test_missing_reading_fails_required_records():
    result, _ = _ground(NUM, evidence_used=WEEK[1:])  # mean of the other 6 = 54.83, still ~54.9
    assert _failed(result) == {"cites_required_records"}
    assert result.failures[0].evidence == ["r0325"]


def test_claim_with_no_evidence_is_unsupported():
    result, _ = _ground(STATE, evidence_used=[])
    assert _failed(result) == {"cites_required_records", "evidence_supports_claim"}


def test_reading_outside_window_fails_window_check():
    result, _ = _ground(NUM, evidence_used=WEEK + ["o3"])  # o3 is 2026-03-15
    assert _failed(result) == {"cited_records_within_window"}


def test_future_record_cited_as_support_is_invalid_and_contradictory():
    case = BY_ID["goal_future_record"]  # g3 = "half marathon", 2026-05-01
    result, _ = _ground(case, evidence_used=["g2", "g3"])
    assert _failed(result) == {"cited_records_within_window", "no_contradicting_evidence"}


def test_numeric_claim_not_supported_by_cited_readings():
    result, _ = _ground(NUM, final_answer="Your average was 60 bpm.")
    assert _failed(result) == {"evidence_supports_claim"}


def test_faithful_answer_over_wrong_window_is_grounded_in_its_evidence_but_out_of_window():
    trace = HealthAgent(respect_window=False).answer(NUM.timeline, NUM.question, NUM.as_of)
    result = evaluate_evidence_grounding(NUM, trace)
    assert _failed(result) == {"cited_records_within_window"}  # claim matches its own evidence
    assert not evaluate_answer_correctness(NUM, trace).passed  # ...but it is the wrong number
    assert evaluate_temporal_consistency(NUM, trace).passed  # ...and nothing was unknowable


def test_stale_record_silently_cited_as_support_is_contradictory():
    result, _ = _ground(STATE, evidence_used=["g1", "g2"])
    assert _failed(result) == {"no_contradicting_evidence"}
    assert result.failures[0].evidence == ["g1"]


def test_stale_record_cited_and_explicitly_framed_as_past_is_fine():
    result, _ = _ground(STATE, evidence_used=["g1", "g2"],
                        final_answer="You switched from marathon training to weight training.")
    assert result.passed
