"""Temporal-consistency evaluator: did the agent use anything it could not have known?

A record is knowable at as_of iff recorded_at <= as_of (and it has happened: event_time <= as_of).
This looks at everything retrieved or cited, so leaking unknowable data fails here even when
the final answer happens to be right. Which records *should* be cited is evidence grounding;
whether the answer is right is answer correctness.
"""

from __future__ import annotations

from pulseeval.agent import AgentTrace
from pulseeval.evaluation.schemas import CheckSpec, EvaluationResult, FailureType, build_result
from pulseeval.scenarios import Case

TEMPORAL_EVALUATOR_VERSION = "0.3.0"


def unknowable_records(case: Case, trace: AgentTrace) -> list[str]:
    """Retrieved or cited record ids that were not knowable at case.as_of."""
    used = [case.timeline.get(rid)
            for rid in dict.fromkeys(trace.retrieved_context + trace.evidence_used)]
    return [r.record_id for r in used
            if r is not None and (r.recorded_at > case.as_of or r.event_time > case.as_of)]


def evaluate_temporal_consistency(case: Case, trace: AgentTrace) -> EvaluationResult:
    leaked = unknowable_records(case, trace)
    specs = [
        CheckSpec(
            name="no_unknowable_records", failure_type=FailureType.TEMPORAL_FAILURE,
            passed=not leaked, severity="high",
            expected_behavior=f"Only records knowable at {case.as_of:%Y-%m-%d} are retrieved or cited.",
            actual_behavior=(f"Retrieved/cited records not knowable at as_of: {leaked}." if leaked
                             else "All retrieved/cited records were knowable at as_of."),
            evidence=leaked,
        ),
    ]
    return build_result(case.case_id, "temporal_consistency", TEMPORAL_EVALUATOR_VERSION,
                        trace, specs)
