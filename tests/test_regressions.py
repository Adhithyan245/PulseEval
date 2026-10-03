"""Phase 3 regression tests: defects found by the hardening benchmark, each with its fix."""

from pulseeval.agent import HealthAgent
from pulseeval.evaluation.answer import evaluate_answer_correctness
from pulseeval.evaluation.grounding import evaluate_evidence_grounding
from pulseeval.evaluation.text import certainty_claims
from pulseeval.evaluation.uncertainty import evaluate_uncertainty_abstention
from pulseeval.scenarios import CASES

BY_ID = {c.case_id: c for c in CASES}


def _trace(case, **update):
    trace = HealthAgent().answer(case.timeline, case.question, case.as_of)
    return trace.model_copy(update=update)


# Defect 1 (answer v0.3.2, grounding v0.4.1): a value that is a substring of another known value
# of the same field ("marathon" inside "half marathon") was counted as mentioned by the longer one.

def test_current_value_containing_stale_value_is_not_a_stale_assertion():
    case = BY_ID["goal_value_superstring"]  # current "half marathon", stale "marathon"
    trace = _trace(case)
    assert evaluate_answer_correctness(case, trace).passed
    assert evaluate_evidence_grounding(case, trace).passed


def test_longer_wrong_value_does_not_count_as_the_shorter_current_value():
    # mirror image: current "marathon", stale "half marathon"; answering the stale value must fail
    case = BY_ID["goal_value_superstring"].model_copy(update={
        "timeline": BY_ID["goal_value_superstring"].timeline.model_copy(update={"records": [
            r.model_copy(update={"value": {"g1": "half marathon", "g2": "marathon"}[r.record_id]})
            for r in BY_ID["goal_value_superstring"].timeline.records]}),
        "expected_value": "marathon"})
    trace = _trace(case, final_answer="Your current training goal is half marathon.")
    failed = {c.name for c in evaluate_answer_correctness(case, trace).checks if not c.passed}
    assert failed == {"answer_asserts_current_value", "answer_does_not_assert_other_value"}


# Defect 2 (uncertainty v0.1.1): qualifications ("does not establish", "would not conclude",
# "would need") were classified as refusals, so a supported, caveated answer looked like an
# unnecessary abstention.

def test_caveated_supported_answer_is_not_an_abstention():
    case = BY_ID["unc_direct_relationship"]
    assert evaluate_uncertainty_abstention(case, _trace(case)).passed


def test_qualifications_are_limitations_not_refusals():
    for text in ("This association does not establish that sleep caused the difference.",
                 "I would not conclude that you are definitely getting sick.",
                 "To answer this I would need symptom data."):
        claims = certainty_claims(text, ["sick"])
        assert claims.limitations and not claims.refusals, text


def test_genuine_refusal_of_supported_question_still_fails():
    case = BY_ID["unc_direct_relationship"]
    trace = _trace(case, final_answer="I can't determine that from the available data.",
                   abstention=True)
    assert not evaluate_uncertainty_abstention(case, trace).passed
