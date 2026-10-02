"""PulseEval evaluation engine. `run_suite` routes each case to its evaluator by kind."""

from __future__ import annotations

from pulseeval.agent import HealthAgent
from pulseeval.evaluation.numerical import evaluate_numerical_correctness
from pulseeval.evaluation.schemas import EvaluationResult
from pulseeval.evaluation.temporal import evaluate_temporal_consistency
from pulseeval.scenarios import Case, NumericCase


def run_suite(agent: HealthAgent, cases: list[Case]) -> list[EvaluationResult]:
    results = []
    for case in cases:
        trace = agent.answer(case.timeline, case.question, case.as_of)
        if isinstance(case, NumericCase):
            results.append(evaluate_numerical_correctness(case, trace))
        else:
            results.append(evaluate_temporal_consistency(case, trace))
    return results
