"""PulseEval evaluation engine: each case is scored on independent dimensions.

An evaluator returns None when its dimension does not apply to the case (ADR-009).
"""

from __future__ import annotations

from pulseeval.agent import HealthAgent
from pulseeval.evaluation.answer import evaluate_answer_correctness
from pulseeval.evaluation.grounding import evaluate_evidence_grounding
from pulseeval.evaluation.missing_data import evaluate_missing_data
from pulseeval.evaluation.schemas import EvaluationResult
from pulseeval.evaluation.temporal import evaluate_temporal_consistency
from pulseeval.scenarios import Case

EVALUATORS = (evaluate_temporal_consistency, evaluate_evidence_grounding,
              evaluate_answer_correctness, evaluate_missing_data)


def run_suite(agent: HealthAgent, cases: list[Case]) -> list[EvaluationResult]:
    results = []
    for case in cases:
        trace = agent.answer(case.timeline, case.question, case.as_of)
        results.extend(r for r in (evaluate(case, trace) for evaluate in EVALUATORS)
                       if r is not None)
    return results
