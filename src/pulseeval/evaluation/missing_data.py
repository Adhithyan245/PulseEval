"""Missing-data handling evaluator: does the answer represent window coverage accurately?

Missing data is not itself a failure. With N expected daily observations in the requested
window and A actually available (knowable at as_of), M = N - A days are missing:
  gap_acknowledged            - if M > 0, the answer says the window is incomplete (a gap
                                word, "A of N days" with A < N, "based on A days", "M missing");
                                not required if M == 0
  no_false_completeness_claim - if M > 0, no "all N days" / "no missing days" / A >= N claim
  no_false_imputation         - no claim of more observations than exist, no "imputed /
                                estimated / interpolated" wording, no value given for a missing day
  coverage_counts_accurate    - any stated counts match A, M, N; no gap claimed when complete

Applies only to NumericCase (ADR-009). Expected counts come from case labels
(`expected_observations`, `expected_record_ids`), never from agent code. Independent of
temporal consistency (what was knowable), grounding (what was cited) and answer correctness
(whether the number is right).
"""

from __future__ import annotations

from datetime import timedelta

from pulseeval.agent import AgentTrace
from pulseeval.evaluation.schemas import CheckSpec, EvaluationResult, FailureType, build_result
from pulseeval.evaluation.text import coverage_claims, dated_values
from pulseeval.scenarios import Case, NumericCase

MISSING_DATA_EVALUATOR_VERSION = "0.1.0"
_M = FailureType.MISSING_DATA_FAILURE


def evaluate_missing_data(case: Case, trace: AgentTrace) -> EvaluationResult | None:
    if not isinstance(case, NumericCase):
        return None  # not applicable (ADR-009)

    n = case.expected_observations
    available = len(case.expected_record_ids)
    m = n - available
    present = {case.timeline.get(rid).event_time.date() for rid in case.expected_record_ids}
    window_days = [case.window_start.date() + timedelta(days=i) for i in range(n)]
    missing_days = [d for d in window_days if d not in present]
    coverage = f"{available} of {n} expected daily observations available"
    if missing_days:
        coverage += f"; missing: {[d.isoformat() for d in missing_days]}"

    claims = coverage_claims(trace.final_answer)
    # Any statement that the window is incomplete counts as acknowledgement; whether the
    # stated numbers are right is coverage_counts_accurate.
    acknowledged = (claims.gap_acknowledged or any(a < n for a in claims.available)
                    or any(x > 0 for x in claims.missing))
    complete_claims = claims.completeness_claimed or any(a >= n for a in claims.available)
    over_claimed = [a for a in claims.available if a > available]
    filled_days = dated_values(trace.final_answer, case.unit, missing_days)
    wrong_counts = ([f"available {a} != {available}" for a in claims.available if a < available]
                    + [f"missing {x} != {m}" for x in claims.missing if x != m]
                    + [f"of {t} != {n}" for t in claims.total if t != n])
    spurious_gap = m == 0 and claims.gap_acknowledged and not claims.missing == [0]
    said = (f"Answer: {trace.final_answer!r}. Parsed coverage: "
            f"{claims.model_dump(exclude_defaults=True) or 'none'}.")

    specs = [
        CheckSpec(
            name="gap_acknowledged", failure_type=_M,
            passed=m == 0 or acknowledged, severity="medium",
            expected_behavior=("No disclaimer required (window complete)." if m == 0 else
                               f"Answer acknowledges that {m} of {n} days have no data."),
            actual_behavior=f"{coverage}. {said}",
        ),
        CheckSpec(
            name="no_false_completeness_claim", failure_type=_M,
            passed=m == 0 or not complete_claims, severity="high",
            expected_behavior=f"Result is not presented as covering all {n} days.",
            actual_behavior=(f"{coverage}, but the answer claims complete coverage. {said}"
                             if m and complete_claims else f"{coverage}. No false completeness claim."),
        ),
        CheckSpec(
            name="no_false_imputation", failure_type=_M,
            passed=not (over_claimed or claims.imputation_claimed or filled_days), severity="high",
            expected_behavior=(f"No claim of more than {available} observations, no imputation, "
                               "and no value attributed to a missing day."),
            actual_behavior=(
                "; ".join(filter(None, [
                    f"claims {over_claimed} observations" if over_claimed else "",
                    "claims imputed/estimated values" if claims.imputation_claimed else "",
                    f"gives values for missing days {[d.isoformat() for d in filled_days]}"
                    if filled_days else "",
                ])) or "No fabricated or imputed observations claimed.") + f" ({coverage}.)",
        ),
        CheckSpec(
            name="coverage_counts_accurate", failure_type=_M,
            passed=not (wrong_counts or spurious_gap), severity="medium",
            expected_behavior=f"Any stated counts match: {available} available, {m} missing, {n} total.",
            actual_behavior=("; ".join(wrong_counts + (["gap claimed but window complete"]
                                                       if spurious_gap else []))
                             or "Stated counts (if any) are accurate.") + f" ({coverage}.)",
        ),
    ]
    return build_result(case.case_id, "missing_data", MISSING_DATA_EVALUATOR_VERSION, trace, specs)
