"""Evidence-grounding evaluator: is the cited evidence the right evidence for the claim?

Checks the agent's `evidence_used` against the case and the timeline:
  cited_records_exist          - no fabricated record ids
  cites_required_records       - nothing required is missing
  cited_records_relevant       - cited records are the asked-about field(s) (and unit)
  cited_records_within_window  - cited events fall in the question's valid window
  evidence_supports_claim      - (state, numeric) the asserted value follows from the records
  no_contradicting_evidence    - (state) no cited record silently contradicts the claim
For assessments (ADR-010) the required records are the labelled wearable + self-report ids
and relevance uses the case's `relevant_names`; how a wearable/self-report conflict is
represented is contradiction handling, not grounding.

Knowability at as_of (late-synced / future data) is temporal consistency, and whether the
claim is *right* is answer correctness; this evaluator only asks whether the claim is
grounded in appropriate cited records. A faithful answer over the wrong window passes
answer-faithfulness here but fails `cited_records_within_window`.
"""

from __future__ import annotations

from datetime import datetime

from pulseeval.agent import AgentTrace
from pulseeval.evaluation.schemas import CheckSpec, EvaluationResult, FailureType, build_result
from pulseeval.evaluation.text import affirmed_number, asserts, value_mentions
from pulseeval.scenarios import AssessmentCase, Case, NumericCase, StateCase
from pulseeval.timeline import Record

GROUNDING_EVALUATOR_VERSION = "0.2.0"
_EPS = 1e-9
_G = FailureType.GROUNDING_FAILURE


def _window(case: Case) -> tuple[datetime | None, datetime]:
    start = case.window_start if isinstance(case, NumericCase | AssessmentCase) else None
    return start, case.as_of


def _required(case: Case) -> list[str]:
    if isinstance(case, NumericCase):
        return case.expected_record_ids
    if isinstance(case, AssessmentCase):
        return case.wearable_record_ids + case.self_report_record_ids
    return [case.expected_record_id]


def _relevant_names(case: Case) -> list[str]:
    return case.relevant_names if isinstance(case, AssessmentCase) else [case.target_name]


def _support_spec(case: Case, trace: AgentTrace, relevant: list[Record]) -> CheckSpec:
    if isinstance(case, NumericCase):
        claim, _ = affirmed_number(trace.final_answer, case.unit)
        if claim is None:
            ok, actual = True, "No single numeric claim to ground (see answer_correctness)."
        elif not relevant:
            ok, actual = False, f"Claim {claim:g} {case.unit} cites no relevant readings."
        else:
            mean = sum(float(r.value) for r in relevant) / len(relevant)
            ok = abs(claim - mean) <= case.tolerance + _EPS
            actual = (f"Claim {claim:g} {case.unit}; mean of {len(relevant)} cited readings "
                      f"= {mean:.3f} {case.unit}.")
        expected = f"Claimed value equals the mean of the cited readings (±{case.tolerance:g})."
    else:
        field_values = {str(r.value) for r in case.timeline.records if r.name == case.target_name}
        claimed = sorted(v for v in field_values if asserts(trace.final_answer, v))
        cited_values = {str(r.value) for r in relevant}
        unsupported = [v for v in claimed if v not in cited_values]
        ok = not unsupported
        actual = (f"Claimed {claimed or 'nothing'}; cited values {sorted(cited_values)}"
                  + (f"; unsupported: {unsupported}." if unsupported else "."))
        expected = "Every value asserted as current appears in a cited record."
    return CheckSpec(name="evidence_supports_claim", failure_type=_G, passed=ok, severity="high",
                     expected_behavior=expected, actual_behavior=actual,
                     evidence=[r.record_id for r in relevant])


def _contradiction_spec(trace: AgentTrace, relevant: list[Record]) -> CheckSpec:
    # A cited value is fine if it is the claim, or the answer explicitly frames it
    # (past/negated). Otherwise the record is presented as support for a claim it contradicts.
    contradicting = [r.record_id for r in relevant
                     if not value_mentions(trace.final_answer, str(r.value))]
    claimed_any = any(asserts(trace.final_answer, str(r.value)) for r in relevant)
    ok = not (contradicting and claimed_any)
    return CheckSpec(
        name="no_contradicting_evidence", failure_type=_G, passed=ok, severity="medium",
        expected_behavior="Cited records either support the claim or are explicitly framed "
                          "in the answer (e.g. as past or no longer current).",
        actual_behavior=(f"Cited but unacknowledged conflicting records: {contradicting}."
                         if not ok else "No cited record silently contradicts the claim."),
        evidence=contradicting,
    )


def evaluate_evidence_grounding(case: Case, trace: AgentTrace) -> EvaluationResult:
    cited_ids = list(dict.fromkeys(trace.evidence_used))
    cited = [case.timeline.get(rid) for rid in cited_ids]
    missing_ids = [rid for rid, r in zip(cited_ids, cited) if r is None]
    existing = [r for r in cited if r is not None]

    required = _required(case)
    not_cited = [rid for rid in required if rid not in cited_ids]

    unit = case.unit if isinstance(case, NumericCase) else None
    names = _relevant_names(case)
    irrelevant = [r.record_id for r in existing
                  if r.name not in names or (unit is not None and r.unit != unit)]
    relevant = [r for r in existing if r.record_id not in irrelevant]

    start, end = _window(case)
    outside = [r.record_id for r in existing
               if r.event_time > end or (start is not None and r.event_time < start)]
    window_text = f"[{start:%Y-%m-%d %H:%M}, {end:%Y-%m-%d %H:%M}]" if start else f"<= {end:%Y-%m-%d}"

    specs = [
        CheckSpec(name="cited_records_exist", failure_type=_G, passed=not missing_ids,
                  severity="high", expected_behavior="Every cited id exists in the timeline.",
                  actual_behavior=(f"Fabricated/unknown ids: {missing_ids}." if missing_ids
                                   else "All cited ids exist."), evidence=missing_ids),
        CheckSpec(name="cites_required_records", failure_type=_G, passed=not not_cited,
                  severity="high", expected_behavior=f"Evidence includes {required}.",
                  actual_behavior=(f"Missing evidence: {not_cited}." if not_cited
                                   else "All required records cited."), evidence=not_cited),
        CheckSpec(name="cited_records_relevant", failure_type=_G, passed=not irrelevant,
                  severity="medium",
                  expected_behavior=(f"Cited records are {names}"
                                     + (f" in {unit}." if unit else ".")),
                  actual_behavior=(f"Irrelevant records cited: {irrelevant}." if irrelevant
                                   else "All cited records are relevant."), evidence=irrelevant),
        CheckSpec(name="cited_records_within_window", failure_type=_G, passed=not outside,
                  severity="high", expected_behavior=f"Cited events fall within {window_text}.",
                  actual_behavior=(f"Cited outside the window: {outside}." if outside
                                   else "All cited events are within the window."),
                  evidence=outside),
    ]
    if not isinstance(case, AssessmentCase):  # an assessment has no single value to support
        specs.append(_support_spec(case, trace, relevant))
    if isinstance(case, StateCase):
        specs.append(_contradiction_spec(trace, relevant))
    return build_result(case.case_id, "evidence_grounding", GROUNDING_EVALUATOR_VERSION,
                        trace, specs)
