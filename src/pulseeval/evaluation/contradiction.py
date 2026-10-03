"""Contradiction-handling evaluator: wearable signals vs. the member's self-report.

The evaluator never decides which source is right. It checks how the answer *represents*
the relationship between them, against hand labels on the case (ADR-010):

When the sources conflict (labelled directions differ):
  both_sources_acknowledged  - the answer refers to the wearable data and to the self-report
  conflict_flagged           - the answer explicitly says they conflict / don't match
  no_unsupported_resolution  - no unattributed, unhedged verdict ("you are well recovered")
When they do not conflict (agree, or no knowable current self-report):
  no_invented_conflict       - the answer does not claim a conflict
Always:
  no_source_dismissed        - neither source is waved away ("actually", "despite how you
                               feel", "the data is wrong")

Applies only to AssessmentCase (ADR-009). Which records the agent used is evidence
grounding; whether they were knowable is temporal consistency.
"""

from __future__ import annotations

from pulseeval.agent import AgentTrace
from pulseeval.evaluation.schemas import CheckSpec, EvaluationResult, FailureType, build_result
from pulseeval.evaluation.text import contradiction_claims
from pulseeval.scenarios import AssessmentCase, Case

CONTRADICTION_EVALUATOR_VERSION = "0.1.2"
_C = FailureType.CONTRADICTION_FAILURE


def evaluate_contradiction_handling(case: Case, trace: AgentTrace) -> EvaluationResult | None:
    if not isinstance(case, AssessmentCase):
        return None  # not applicable (ADR-009)

    claims = contradiction_claims(trace.final_answer)
    report = case.self_report_indicates
    situation = (f"Wearable indicates {case.wearable_indicates}; self-report indicates "
                 f"{report or 'nothing (no knowable current report)'}"
                 f" -> {'conflict' if case.conflict else 'no conflict'}.")
    said = (f"Answer: {trace.final_answer!r}. Parsed: "
            f"{claims.model_dump(exclude_defaults=True) or 'nothing'}.")
    na = "Not applicable: sources do not conflict."

    specs = [
        CheckSpec(
            name="both_sources_acknowledged", failure_type=_C, severity="high",
            passed=not case.conflict or (claims.mentions_wearable and claims.mentions_self_report),
            expected_behavior="Answer refers to both the wearable data and the self-report.",
            actual_behavior=(na if not case.conflict else
                             f"{situation} Mentions wearable: {claims.mentions_wearable}; "
                             f"mentions self-report: {claims.mentions_self_report}. {said}"),
        ),
        CheckSpec(
            name="conflict_flagged", failure_type=_C, severity="high",
            passed=not case.conflict or claims.conflict_claimed,
            expected_behavior="Answer explicitly states that the sources conflict.",
            actual_behavior=na if not case.conflict else f"{situation} {said}",
        ),
        CheckSpec(
            name="no_unsupported_resolution", failure_type=_C, severity="medium",
            passed=not case.conflict or not claims.verdicts,
            expected_behavior="With conflicting sources, no unattributed definitive verdict.",
            actual_behavior=(na if not case.conflict else
                             f"{situation} Verdicts: {claims.verdicts or 'none'}."),
        ),
        CheckSpec(
            name="no_invented_conflict", failure_type=_C, severity="medium",
            passed=case.conflict or not claims.conflict_claimed,
            expected_behavior="Answer does not claim a conflict that the data does not contain.",
            actual_behavior=("Not applicable: sources conflict." if case.conflict
                             else f"{situation} {said}"),
        ),
        CheckSpec(
            name="no_source_dismissed", failure_type=_C, severity="high",
            passed=not claims.dismissals,
            expected_behavior="Neither the wearable data nor the self-report is dismissed.",
            actual_behavior=(f"Dismissive wording: {claims.dismissals}. {said}"
                             if claims.dismissals else "No dismissive wording."),
        ),
    ]
    return build_result(case.case_id, "contradiction_handling", CONTRADICTION_EVALUATOR_VERSION,
                        trace, specs)
