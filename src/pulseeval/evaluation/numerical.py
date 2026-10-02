"""Numerical-correctness evaluator: deterministic, tolerance-based.

Aspects:
  temporal - nothing retrieved/cited was unknowable at as_of
  evidence - cited readings are exactly the hand-labelled readings for the window
  answer   - exactly one affirmed number with the expected unit, within tolerance
"""

from __future__ import annotations

from pulseeval.agent import AgentTrace
from pulseeval.evaluation.schemas import CheckSpec, EvaluationResult, FailureType, build_result
from pulseeval.evaluation.temporal import unknowable_records
from pulseeval.evaluation.text import numbers_with_unit
from pulseeval.scenarios import NumericCase

NUMERICAL_EVALUATOR_VERSION = "0.1.0"
_EPS = 1e-9  # absorbs float noise at the tolerance boundary


def evaluate_numerical_correctness(case: NumericCase, trace: AgentTrace) -> EvaluationResult:
    future = unknowable_records(case, trace)
    expected_ids, cited_ids = set(case.expected_record_ids), set(trace.evidence_used)
    affirmed = sorted({v for v, polarity in numbers_with_unit(trace.final_answer, case.unit)
                       if polarity == "affirmed"})
    actual = affirmed[0] if len(affirmed) == 1 else None
    error = None if actual is None else abs(actual - case.expected_value)

    if actual is None:
        extracted = (f"No affirmed value in {case.unit!r} found." if not affirmed
                     else f"Ambiguous: several affirmed values {affirmed} {case.unit}.")
    else:
        extracted = f"Extracted {actual} {case.unit}."

    specs = [
        CheckSpec(
            name="no_future_evidence", aspect="temporal",
            failure_type=FailureType.TEMPORAL_FAILURE, passed=not future, severity="high",
            expected_behavior=f"Only readings knowable at {case.as_of:%Y-%m-%d} are used.",
            actual_behavior=(f"Retrieved/cited records not knowable at as_of: {future}." if future
                             else "All retrieved/cited records were knowable at as_of."),
            evidence=future,
        ),
        CheckSpec(
            name="evidence_matches_expected_readings", aspect="evidence",
            failure_type=FailureType.NUMERICAL_FAILURE,
            passed=cited_ids == expected_ids, severity="high",
            expected_behavior=f"Computation uses exactly readings {sorted(expected_ids)}.",
            actual_behavior=(f"Missing: {sorted(expected_ids - cited_ids)}; "
                             f"extra: {sorted(cited_ids - expected_ids)}."
                             if cited_ids != expected_ids else "Cited readings match."),
            evidence=trace.evidence_used,
        ),
        CheckSpec(
            name="value_extracted", aspect="answer",
            failure_type=FailureType.NUMERICAL_FAILURE,
            passed=actual is not None, severity="medium",
            expected_behavior=f"Answer affirms exactly one value in {case.unit!r}.",
            actual_behavior=f"{extracted} Answer: {trace.final_answer!r}.",
            evidence=trace.evidence_used,
        ),
        CheckSpec(
            name="value_within_tolerance", aspect="answer",
            failure_type=FailureType.NUMERICAL_FAILURE,
            passed=error is not None and error <= case.tolerance + _EPS, severity="high",
            expected_behavior=(f"|actual - {case.expected_value:g}| <= {case.tolerance:g} "
                               f"{case.unit}."),
            actual_behavior=(f"No value to compare. {extracted}" if error is None else
                             f"actual={actual:g}, expected={case.expected_value:g}, "
                             f"error={error:.3g} {case.unit}."),
            evidence=trace.evidence_used,
        ),
    ]
    return build_result(case.case_id, "numerical_correctness", NUMERICAL_EVALUATOR_VERSION,
                        trace, specs)
