"""PulseEval evaluation engine: failure taxonomy, result schemas, and evaluators."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel

from pulseeval.agent import AgentTrace, HealthAgent
from pulseeval.scenarios import Case

TEMPORAL_EVALUATOR_VERSION = "0.1.0"


class FailureType(str, Enum):
    TEMPORAL_FAILURE = "TEMPORAL_FAILURE"
    MEMORY_FAILURE = "MEMORY_FAILURE"
    GROUNDING_FAILURE = "GROUNDING_FAILURE"
    CAUSALITY_FAILURE = "CAUSALITY_FAILURE"
    CONTRADICTION_FAILURE = "CONTRADICTION_FAILURE"
    MISSING_DATA_FAILURE = "MISSING_DATA_FAILURE"
    UNCERTAINTY_FAILURE = "UNCERTAINTY_FAILURE"
    ABSTENTION_FAILURE = "ABSTENTION_FAILURE"
    TOOL_FAILURE = "TOOL_FAILURE"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"
    PERSONALIZATION_FAILURE = "PERSONALIZATION_FAILURE"


Severity = Literal["low", "medium", "high"]


class Check(BaseModel):
    name: str
    passed: bool
    explanation: str


class Failure(BaseModel):
    failure_type: FailureType
    severity: Severity
    query: str
    expected_behavior: str
    actual_behavior: str
    evidence: list[str]
    trace: AgentTrace
    explanation: str


class EvaluationResult(BaseModel):
    case_id: str
    evaluator: str
    evaluator_version: str
    passed: bool
    checks: list[Check]
    failures: list[Failure]


def evaluate_temporal_consistency(case: Case, trace: AgentTrace) -> EvaluationResult:
    """Deterministic check that the agent respected as-of time and used the current state.

    Ground truth comes from the case labels and timeline timestamps, never from agent code.
    Evidence ids missing from the timeline are ignored here (owned by a grounding evaluator).
    """
    as_of = case.as_of
    cited = [case.timeline.get(rid) for rid in dict.fromkeys(trace.retrieved_context + trace.evidence_used)]
    future = [r.record_id for r in cited
              if r is not None and (r.recorded_at > as_of or r.event_time > as_of)]
    expected = case.timeline.get(case.expected_record_id)

    specs = [
        (
            "no_future_evidence",
            not future,
            f"Only records knowable at {as_of:%Y-%m-%d} are retrieved or cited.",
            f"Retrieved/cited records not knowable at as_of: {future}." if future
            else "All retrieved/cited records were knowable at as_of.",
            future,
            "high",
        ),
        (
            "uses_current_state",
            case.expected_record_id in trace.evidence_used,
            f"Evidence includes the current '{case.target_name}' record "
            f"{case.expected_record_id} ({expected.value!r}).",
            f"Evidence used: {trace.evidence_used}.",
            trace.evidence_used,
            "high",
        ),
        (
            "answer_states_current_value",
            case.expected_value.lower() in trace.final_answer.lower(),
            f"Answer states the current value {case.expected_value!r}.",
            f"Answer: {trace.final_answer!r}.",
            trace.evidence_used,
            "medium",
        ),
    ]

    checks: list[Check] = []
    failures: list[Failure] = []
    for name, passed, expected_behavior, actual_behavior, evidence, severity in specs:
        checks.append(Check(name=name, passed=passed, explanation=actual_behavior))
        if not passed:
            failures.append(Failure(
                failure_type=FailureType.TEMPORAL_FAILURE, severity=severity,
                query=trace.query, expected_behavior=expected_behavior,
                actual_behavior=actual_behavior, evidence=evidence, trace=trace,
                explanation=f"Temporal check '{name}' failed.",
            ))

    return EvaluationResult(
        case_id=case.case_id, evaluator="temporal_consistency",
        evaluator_version=TEMPORAL_EVALUATOR_VERSION,
        passed=not failures, checks=checks, failures=failures,
    )


def run_suite(agent: HealthAgent, cases: list[Case]) -> list[EvaluationResult]:
    return [
        evaluate_temporal_consistency(case, agent.answer(case.timeline, case.question, case.as_of))
        for case in cases
    ]
