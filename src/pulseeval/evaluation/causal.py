"""Causal-restraint evaluator: is the answer's causal language justified by the case's labels?

PulseEval does not perform causal inference. Each RelationshipCase is hand-labelled with
what its records establish (ADR-011): an observed pattern (`observed_direction`) and whether
a causal reading is supported (`causal_support`, backed by `causal_basis_record_ids`).
The answer is parsed clause by clause (`text.causal_claims`): causal cues are asserted,
negated, uncertain, hypothetical, hedged, or quoted; only *asserted* ones are claims.

  no_unsupported_causal_claim             - association_only: no asserted causal claim about
                                            the exposure -> outcome relationship
  causal_language_appropriately_qualified - association_only: if causation is floated
                                            (hedged / hypothetical), the answer also says
                                            explicitly that it is not established or that
                                            other factors may be involved
  association_not_overstated              - no association or causal claim when the records
                                            show no pattern; no stated direction opposite to
                                            the observed one

With `causal_support="supported"`, causal wording is permitted. Applies only to
RelationshipCase (ADR-009). Which records were cited is grounding; the reported group
means are answer correctness.
"""

from __future__ import annotations

from pulseeval.agent import AgentTrace
from pulseeval.evaluation.schemas import CheckSpec, EvaluationResult, FailureType, build_result
from pulseeval.evaluation.text import causal_claims
from pulseeval.scenarios import Case, RelationshipCase

CAUSAL_EVALUATOR_VERSION = "0.1.1"
_F = FailureType.CAUSALITY_FAILURE


def evaluate_causal_restraint(case: Case, trace: AgentTrace) -> EvaluationResult | None:
    if not isinstance(case, RelationshipCase):
        return None  # not applicable (ADR-009)

    claims = causal_claims(trace.final_answer, case.exposure_terms, case.outcome_terms)
    supported = case.causal_support == "supported"
    labels = (f"Labels: {case.exposure_name} -> {case.outcome_name}, observed direction "
              f"{case.observed_direction}, causal support {case.causal_support}"
              + (f" (basis records {case.causal_basis_record_ids})" if supported else "")
              + (f"; recorded co-varying variables {case.confounder_names}"
                 if case.confounder_names else "") + ".")
    parsed = (f"Parsed: {[m for m, _ in claims.occurrences] or 'no causal language'}, "
              f"qualified={claims.qualified}, association_stated={claims.association_stated}, "
              f"directions={claims.stated_directions or 'none'}.")
    na = "Not applicable: causal interpretation is supported by the case's basis records."

    overstated = []
    if case.observed_direction == "none":
        if claims.association_stated:
            overstated.append("association stated but the records show no pattern")
        if claims.asserted:
            overstated.append("causal effect asserted but the records show no pattern")
    else:
        overstated += [f"stated direction {d} contradicts observed {case.observed_direction}"
                       for d in claims.stated_directions if d != case.observed_direction]

    specs = [
        CheckSpec(
            name="no_unsupported_causal_claim", failure_type=_F, severity="high",
            passed=supported or not claims.asserted,
            expected_behavior="No asserted causal claim: the records establish association only.",
            actual_behavior=(na if supported else
                             (f"Asserted causal claims: {claims.asserted}. " if claims.asserted
                              else "No asserted causal claim. ") + f"{labels} {parsed}"),
        ),
        CheckSpec(
            name="causal_language_appropriately_qualified", failure_type=_F, severity="medium",
            passed=supported or not claims.speculative or claims.qualified,
            expected_behavior=("If causation is floated, the answer states explicitly that it is "
                               "not established (or that other factors may be involved)."),
            actual_behavior=(na if supported else
                             (f"Causation floated without explicit qualification: "
                              f"{claims.speculative}. " if claims.speculative
                              and not claims.qualified else "Qualification adequate. ")
                             + parsed),
        ),
        CheckSpec(
            name="association_not_overstated", failure_type=_F, severity="high",
            passed=not overstated,
            expected_behavior="The answer claims no relationship beyond what the records show.",
            actual_behavior=("; ".join(overstated) + f". {labels} {parsed}" if overstated
                             else "No relationship overstated."),
        ),
    ]
    return build_result(case.case_id, "causal_restraint", CAUSAL_EVALUATOR_VERSION, trace, specs)
