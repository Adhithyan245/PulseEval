"""Answer-correctness evaluator: does the final text assert the right thing?

State questions: the current value is affirmed and no other value of that field is affirmed.
Numeric questions: exactly one affirmed number with the unit, within an absolute tolerance.
Relationship questions: every labelled group mean is affirmed in the unit, within tolerance
(how the relationship is framed causally is causal restraint, not answer correctness).
Judged against hand-labelled / independently recomputed expectations, never agent code.
"""

from __future__ import annotations

from pulseeval.agent import AgentTrace
from pulseeval.evaluation.schemas import CheckSpec, EvaluationResult, FailureType, build_result
from pulseeval.evaluation.text import affirmed_number, asserts, numbers_with_unit, value_mentions
from pulseeval.scenarios import (AssessmentCase, Case, NumericCase, OpenQuestionCase,
                                 RelationshipCase, StateCase)

ANSWER_EVALUATOR_VERSION = "0.3.1"
_EPS = 1e-9  # absorbs float noise at the tolerance boundary


def _state_specs(case: StateCase, trace: AgentTrace) -> list[CheckSpec]:
    other_values = sorted({str(r.value) for r in case.timeline.records
                           if r.name == case.target_name and str(r.value) != case.expected_value})
    stale_asserted = [v for v in other_values if asserts(trace.final_answer, v)]
    mentions = value_mentions(trace.final_answer, case.expected_value)
    return [
        CheckSpec(
            name="answer_asserts_current_value", failure_type=FailureType.TEMPORAL_FAILURE,
            passed="affirmed" in mentions, severity="medium",
            expected_behavior=f"Answer affirms the current value {case.expected_value!r}.",
            actual_behavior=(f"Mentions of {case.expected_value!r}: {mentions or 'none'}. "
                             f"Answer: {trace.final_answer!r}."),
        ),
        CheckSpec(
            name="answer_does_not_assert_other_value", failure_type=FailureType.TEMPORAL_FAILURE,
            passed=not stale_asserted, severity="high",
            expected_behavior=f"Answer does not present any of {other_values} as current.",
            actual_behavior=(f"Asserted as current: {stale_asserted}." if stale_asserted
                             else "No other value asserted as current."),
        ),
    ]


def _numeric_specs(case: NumericCase, trace: AgentTrace) -> list[CheckSpec]:
    actual, affirmed = affirmed_number(trace.final_answer, case.unit)
    error = None if actual is None else abs(actual - case.expected_value)
    if actual is not None:
        extracted = f"Extracted {actual} {case.unit}."
    elif affirmed:
        extracted = f"Ambiguous: several affirmed values {affirmed} {case.unit}."
    else:
        extracted = f"No affirmed value in {case.unit!r} found."
    return [
        CheckSpec(
            name="value_extracted", failure_type=FailureType.NUMERICAL_FAILURE,
            passed=actual is not None, severity="medium",
            expected_behavior=f"Answer affirms exactly one value in {case.unit!r}.",
            actual_behavior=f"{extracted} Answer: {trace.final_answer!r}.",
        ),
        CheckSpec(
            name="value_within_tolerance", failure_type=FailureType.NUMERICAL_FAILURE,
            passed=error is not None and error <= case.tolerance + _EPS, severity="high",
            expected_behavior=(f"|actual - {case.expected_value:g}| <= {case.tolerance:g} "
                               f"{case.unit}."),
            actual_behavior=(f"No value to compare. {extracted}" if error is None else
                             f"actual={actual:g}, expected={case.expected_value:g}, "
                             f"error={error:.3g} {case.unit}."),
        ),
    ]


def _relationship_specs(case: RelationshipCase, trace: AgentTrace) -> list[CheckSpec]:
    reported = [v for v, polarity in numbers_with_unit(trace.final_answer, case.unit)
                if polarity == "affirmed"]
    missing = {group: mean for group, mean in case.expected_group_means.items()
               if not any(abs(v - mean) <= case.tolerance + _EPS for v in reported)}
    return [
        CheckSpec(
            name="group_means_reported", failure_type=FailureType.NUMERICAL_FAILURE,
            passed=not missing, severity="high",
            expected_behavior=(f"Answer reports each group mean {case.expected_group_means} "
                               f"{case.unit} (±{case.tolerance:g})."),
            actual_behavior=(f"Affirmed values: {reported} {case.unit}"
                             + (f"; not found: {missing}." if missing else ".")),
        ),
    ]


def evaluate_answer_correctness(case: Case, trace: AgentTrace) -> EvaluationResult | None:
    if isinstance(case, AssessmentCase | OpenQuestionCase):
        return None  # no single correct value (ADR-009, ADR-010, ADR-012)
    if isinstance(case, RelationshipCase):
        specs = _relationship_specs(case, trace)
    elif isinstance(case, NumericCase):
        specs = _numeric_specs(case, trace)
    else:
        specs = _state_specs(case, trace)
    return build_result(case.case_id, "answer_correctness", ANSWER_EVALUATOR_VERSION, trace, specs)
