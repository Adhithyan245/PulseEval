from pulseeval.agent import HealthAgent
from pulseeval.evaluation.answer import evaluate_answer_correctness
from pulseeval.evaluation.grounding import evaluate_evidence_grounding
from pulseeval.evaluation.schemas import FailureType
from pulseeval.evaluation.temporal import evaluate_temporal_consistency
from pulseeval.scenarios import CASES

BY_ID = {c.case_id: c for c in CASES}


def test_reference_agent_uses_only_knowable_records():
    agent = HealthAgent()
    for case in CASES:
        trace = agent.answer(case.timeline, case.question, case.as_of)
        assert evaluate_temporal_consistency(case, trace).passed, case.case_id


def test_future_and_late_records_are_flagged():
    agent = HealthAgent(respect_as_of=False)
    for case_id, leaked in [("goal_future_record", ["g3"]), ("goal_late_arriving_record", ["g4"]),
                            ("rhr_mean_7d_late_sync", ["r0331"])]:
        case = BY_ID[case_id]
        result = evaluate_temporal_consistency(case, agent.answer(case.timeline, case.question,
                                                                  case.as_of))
        [failure] = result.failures
        assert failure.failure_type is FailureType.TEMPORAL_FAILURE
        assert failure.evidence == leaked and failure.trace.query == case.question


def test_retrieving_without_citing_unknowable_record_fails_only_temporal():
    case = BY_ID["goal_future_record"]
    trace = HealthAgent().answer(case.timeline, case.question, case.as_of)
    trace = trace.model_copy(update={"retrieved_context": trace.retrieved_context + ["g3"]})
    assert not evaluate_temporal_consistency(case, trace).passed
    assert evaluate_evidence_grounding(case, trace).passed
    assert evaluate_answer_correctness(case, trace).passed
