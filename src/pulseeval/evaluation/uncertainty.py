"""Uncertainty / abstention evaluator: does expressed certainty match the evidence's support?

PulseEval does not estimate statistical confidence, clinical risk or medical probability.
Each labelled case states how much certainty its evidence supports (`certainty`, ADR-012);
the evaluator checks whether the agent's expressed certainty and willingness to answer are
consistent with that label. Answer text is parsed clause by clause (`text.certainty_claims`):
refusals, limitations, hedges, certainty markers and definitive conclusions, with negated,
hypothetical and quoted framing excluded from "certainty".

  no_unnecessary_abstention  - direct_answer_supported: the agent answers (no abstention or
                               refusal). Hedging and cautious wording are fine.
  uncertainty_expressed      - uncertainty_required / conflict_requires_qualification: a
                               limitation ("unclear", "so few days", "conflict") or a hedge
  abstained_or_qualified     - abstention_required: the agent abstains or states that the
                               evidence cannot establish the conclusion (a hedge is not enough)
  no_unjustified_certainty   - every level except direct_answer_supported: no certainty markers
                               ("definitely", "clearly", "no doubt") and no definitive conclusion
                               using the case's `conclusion_terms`

Applies only to cases with `certainty` set (ADR-009). Whether the cited records, window,
numbers, coverage, conflict representation or causal language are right belongs to the
other six dimensions.
"""

from __future__ import annotations

from pulseeval.agent import AgentTrace
from pulseeval.evaluation.schemas import CheckSpec, EvaluationResult, FailureType, build_result
from pulseeval.evaluation.text import certainty_claims
from pulseeval.scenarios import Case

UNCERTAINTY_EVALUATOR_VERSION = "0.1.0"
_U, _A = FailureType.UNCERTAINTY_FAILURE, FailureType.ABSTENTION_FAILURE


def evaluate_uncertainty_abstention(case: Case, trace: AgentTrace) -> EvaluationResult | None:
    level = case.certainty
    if level is None:
        return None  # not labelled -> not applicable (ADR-009)

    claims = certainty_claims(trace.final_answer, case.conclusion_terms)
    refused = trace.abstention or bool(claims.refusals)
    qualified = bool(claims.limitations) or claims.hedged
    overconfident = claims.certainty_markers or claims.definitive_conclusions
    parsed = (f"Label: {level}. Answer: {trace.final_answer!r}. Parsed: abstention="
              f"{trace.abstention}, refusals={len(claims.refusals)}, limitations="
              f"{len(claims.limitations)}, hedged={claims.hedged}, certainty="
              f"{claims.certainty_markers or 'none'}, definitive conclusions="
              f"{claims.definitive_conclusions or 'none'}.")

    def na(levels: str) -> str:
        return f"Not applicable: label is {level} (check applies to {levels})."

    direct = level == "direct_answer_supported"
    needs_qualification = level in ("uncertainty_required", "conflict_requires_qualification")
    specs = [
        CheckSpec(
            name="no_unnecessary_abstention", failure_type=_A, severity="high",
            passed=not direct or not refused,
            expected_behavior="The evidence supports a direct answer; the agent provides it.",
            actual_behavior=parsed if direct else na("direct_answer_supported"),
        ),
        CheckSpec(
            name="uncertainty_expressed", failure_type=_U, severity="medium",
            passed=not needs_qualification or qualified,
            expected_behavior="The answer expresses the uncertainty or conflict in the evidence.",
            actual_behavior=(parsed if needs_qualification else
                             na("uncertainty_required, conflict_requires_qualification")),
        ),
        CheckSpec(
            name="abstained_or_qualified", failure_type=_A, severity="high",
            passed=level != "abstention_required" or refused or bool(claims.limitations),
            expected_behavior=("The agent abstains or states that the evidence cannot establish "
                               "the requested conclusion."),
            actual_behavior=(parsed if level == "abstention_required"
                             else na("abstention_required")),
        ),
        CheckSpec(
            name="no_unjustified_certainty", failure_type=_U, severity="high",
            passed=direct or not overconfident,
            expected_behavior=("No definitive framing or conclusion beyond what the evidence "
                               "supports."),
            actual_behavior=(na("every level except direct_answer_supported") if direct
                             else parsed),
        ),
    ]
    return build_result(case.case_id, "uncertainty_abstention", UNCERTAINTY_EVALUATOR_VERSION,
                        trace, specs)
