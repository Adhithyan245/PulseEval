"""Temporal-consistency evaluator for current-state questions.

Separates three aspects:
  temporal - nothing retrieved/cited was unknowable at as_of
  evidence - the cited evidence includes the current record
  answer   - the answer asserts the current value and no other value of that field

Ground truth comes from case labels and timeline timestamps, never from agent code.
Evidence ids missing from the timeline are ignored here (owned by a grounding evaluator).
"""

from __future__ import annotations

from pulseeval.agent import AgentTrace
from pulseeval.evaluation.schemas import CheckSpec, EvaluationResult, FailureType, build_result
from pulseeval.evaluation.text import asserts, value_mentions
from pulseeval.scenarios import Case, StateCase

TEMPORAL_EVALUATOR_VERSION = "0.2.0"


def unknowable_records(case: Case, trace: AgentTrace) -> list[str]:
    """Retrieved or cited record ids that were not knowable at case.as_of."""
    cited = [case.timeline.get(rid)
             for rid in dict.fromkeys(trace.retrieved_context + trace.evidence_used)]
    return [r.record_id for r in cited
            if r is not None and (r.recorded_at > case.as_of or r.event_time > case.as_of)]


def evaluate_temporal_consistency(case: StateCase, trace: AgentTrace) -> EvaluationResult:
    as_of = case.as_of
    future = unknowable_records(case, trace)
    expected = case.timeline.get(case.expected_record_id)
    other_values = sorted({str(r.value) for r in case.timeline.records
                           if r.name == case.target_name and str(r.value) != case.expected_value})
    stale_asserted = [v for v in other_values if asserts(trace.final_answer, v)]
    current_mentions = value_mentions(trace.final_answer, case.expected_value)

    specs = [
        CheckSpec(
            name="no_future_evidence", aspect="temporal",
            failure_type=FailureType.TEMPORAL_FAILURE, passed=not future, severity="high",
            expected_behavior=f"Only records knowable at {as_of:%Y-%m-%d} are retrieved or cited.",
            actual_behavior=(f"Retrieved/cited records not knowable at as_of: {future}." if future
                             else "All retrieved/cited records were knowable at as_of."),
            evidence=future,
        ),
        CheckSpec(
            name="evidence_includes_current_record", aspect="evidence",
            failure_type=FailureType.TEMPORAL_FAILURE,
            passed=case.expected_record_id in trace.evidence_used, severity="high",
            expected_behavior=(f"Evidence includes the current '{case.target_name}' record "
                               f"{case.expected_record_id} ({expected.value!r})."),
            actual_behavior=f"Evidence used: {trace.evidence_used}.",
            evidence=trace.evidence_used,
        ),
        CheckSpec(
            name="answer_asserts_current_value", aspect="answer",
            failure_type=FailureType.TEMPORAL_FAILURE,
            passed="affirmed" in current_mentions, severity="medium",
            expected_behavior=f"Answer affirms the current value {case.expected_value!r}.",
            actual_behavior=(f"Mentions of {case.expected_value!r}: {current_mentions or 'none'}. "
                             f"Answer: {trace.final_answer!r}."),
            evidence=trace.evidence_used,
        ),
        CheckSpec(
            name="answer_does_not_assert_other_value", aspect="answer",
            failure_type=FailureType.TEMPORAL_FAILURE,
            passed=not stale_asserted, severity="high",
            expected_behavior=f"Answer does not present any of {other_values} as current.",
            actual_behavior=(f"Asserted as current: {stale_asserted}." if stale_asserted
                             else "No other value asserted as current."),
            evidence=trace.evidence_used,
        ),
    ]
    return build_result(case.case_id, "temporal_consistency", TEMPORAL_EVALUATOR_VERSION,
                        trace, specs)
