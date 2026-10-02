"""PulseEval evaluation engine: every case is scored on three independent dimensions."""

from __future__ import annotations

from pulseeval.agent import HealthAgent
from pulseeval.evaluation.answer import evaluate_answer_correctness
from pulseeval.evaluation.grounding import evaluate_evidence_grounding
from pulseeval.evaluation.schemas import EvaluationResult
from pulseeval.evaluation.temporal import evaluate_temporal_consistency
from pulseeval.scenarios import Case

EVALUATORS = (evaluate_temporal_consistency, evaluate_evidence_grounding,
              evaluate_answer_correctness)


def run_suite(agent: HealthAgent, cases: list[Case]) -> list[EvaluationResult]:
    results = []
    for case in cases:
        trace = agent.answer(case.timeline, case.question, case.as_of)
        results.extend(evaluate(case, trace) for evaluate in EVALUATORS)
    return results
