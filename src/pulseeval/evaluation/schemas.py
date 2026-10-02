"""Failure taxonomy and evaluation result schemas shared by all evaluators."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel

from pulseeval.agent import AgentTrace


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
Aspect = Literal["temporal", "evidence", "answer"]


class Check(BaseModel):
    name: str
    aspect: Aspect
    passed: bool
    explanation: str


class Failure(BaseModel):
    failure_type: FailureType
    check: str
    aspect: Aspect
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


class CheckSpec(BaseModel):
    """One deterministic check outcome, before it is turned into Check/Failure."""

    name: str
    aspect: Aspect
    failure_type: FailureType
    passed: bool
    severity: Severity
    expected_behavior: str
    actual_behavior: str
    evidence: list[str] = []


def build_result(case_id: str, evaluator: str, version: str,
                 trace: AgentTrace, specs: list[CheckSpec]) -> EvaluationResult:
    checks = [Check(name=s.name, aspect=s.aspect, passed=s.passed, explanation=s.actual_behavior)
              for s in specs]
    failures = [
        Failure(
            failure_type=s.failure_type, check=s.name, aspect=s.aspect, severity=s.severity,
            query=trace.query, expected_behavior=s.expected_behavior,
            actual_behavior=s.actual_behavior, evidence=s.evidence, trace=trace,
            explanation=f"{evaluator} check '{s.name}' ({s.aspect}) failed.",
        )
        for s in specs if not s.passed
    ]
    return EvaluationResult(case_id=case_id, evaluator=evaluator, evaluator_version=version,
                            passed=not failures, checks=checks, failures=failures)
