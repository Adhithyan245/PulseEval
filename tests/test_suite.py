"""End-to-end: each fault-injected agent fails exactly the dimensions it should."""

import pytest

from pulseeval.agent import HealthAgent
from pulseeval.evaluation import run_suite
from pulseeval.scenarios import CASES

T, G, A, M = "temporal_consistency", "evidence_grounding", "answer_correctness", "missing_data"
C = "contradiction_handling"
K = "causal_restraint"
U = "uncertainty_abstention"


def _failures(agent):
    out = {}
    for r in run_suite(agent, CASES):
        if not r.passed:
            out.setdefault(r.case_id, set()).add(r.evaluator)
    return out


@pytest.mark.parametrize("agent, expected", [
    (HealthAgent(), {}),
    (HealthAgent(ordering="input_order"), {"goal_update_reversed": {G, A}}),
    (HealthAgent(respect_as_of=False), {
        "goal_future_record": {T, G, A},
        "goal_late_arriving_record": {T, G, A},
        # leaked reading is relevant and in-window (grounding passes) but was not knowable,
        # so claiming "all 7 days had data" misstates coverage at as_of
        "rhr_mean_7d_late_sync": {T, A, M},
        "recovery_late_self_report": {T, C},  # unknowable report -> invented conflict
    }),
    (HealthAgent(respect_window=False), {
        "rhr_mean_7d": {G, A},  # complete window: coverage claim is true
        "rhr_mean_7d_late_sync": {G, A, M},
        "rhr_mean_7d_gap": {G, A, M},
        "recovery_stale_self_report": {G, C},  # stale report -> out of window, invented conflict
        "unc_direct_rhr_7d": {G, A},
        # all-history mean sees 4 readings, so it no longer flags the thin coverage
        "unc_sparse_rhr_7d": {G, A, M, U},
    }),
    (HealthAgent(report_coverage=False), {
        # right number, right evidence, nothing unknowable -- only coverage misrepresented
        "rhr_mean_7d_late_sync": {M},
        "rhr_mean_7d_gap": {M},
        "unc_sparse_rhr_7d": {M},  # the uncertainty caveat is still given
    }),
    (HealthAgent(impute_missing=True), {
        "rhr_mean_7d_late_sync": {M},  # carried-forward 55 leaves the mean at 55.0 exactly
        "rhr_mean_7d_gap": {G, A, M},
        "unc_sparse_rhr_7d": {M, U},  # imputed "full" week -> caveat dropped
    }),
    (HealthAgent(ignore_self_report=True), {
        "recovery_conflict_good_data_exhausted": {G, C},
        "recovery_conflict_poor_data_energetic": {G, C},
        "recovery_agree_good": {G},  # report uncited, but no conflict to mishandle
        "recovery_agree_poor": {G},
        "unc_direct_recovery_agree": {G},
        # hedged single-source answer: confidence is fine, conflict representation is not
        "unc_conflict_recovery": {G, C},
    }),
    (HealthAgent(dismiss_self_report=True), {
        # cites both sources correctly; only the representation of the conflict is wrong
        "recovery_conflict_good_data_exhausted": {C},
        "recovery_conflict_poor_data_energetic": {C},
        "unc_conflict_recovery": {C, U},  # "you are actually well recovered" is definitive
    }),
    (HealthAgent(causal_overclaim=True), {
        # right records, window and numbers; only the causal framing is unjustified.
        # The protocol case supports causation; the no-pattern case states no relationship.
        "relation_association_only": {K},
        "relation_confounded_by_stress": {K},
    }),
    (HealthAgent(overconfident=True), {
        # definitive resolution of a real wearable/self-report conflict fails both
        # contradiction handling and (where labelled) uncertainty -- overlap by design
        "recovery_conflict_good_data_exhausted": {C},
        "recovery_conflict_poor_data_energetic": {C},
        "unc_conflict_recovery": {C, U},
        # everything else about these answers is right; only the certainty level is not
        "unc_sparse_rhr_7d": {U},
        "unc_ambiguous_recovery": {U},
        "unc_missing_sleep_stages": {U},
        "unc_out_of_scope_illness": {U},
    }),
    (HealthAgent(false_abstention=True), {
        # refusing where an answer is supported: answer correctness fails wherever a value is
        # expected, and uncertainty/abstention fails only on direct-answer cases
        **{c.case_id: {A} for c in CASES if c.kind in ("current_state", "numeric", "relationship")
           and c.case_id not in ("rhr_mean_7d_late_sync", "rhr_mean_7d_gap",
                                 "unc_sparse_rhr_7d", "unc_direct_rhr_7d")},
        "rhr_mean_7d_late_sync": {A, M},  # refusal also omits the coverage gap
        "rhr_mean_7d_gap": {A, M},
        "unc_sparse_rhr_7d": {A, M},  # abstaining under uncertainty is not overconfident
        "unc_direct_rhr_7d": {A, U},
        "unc_direct_recovery_agree": {U},  # only uncertainty fails: the reverse direction
        "recovery_conflict_good_data_exhausted": {C},
        "recovery_conflict_poor_data_energetic": {C},
        "unc_conflict_recovery": {C},
    }),
], ids=["reference", "input_order", "no_as_of", "no_window", "silent_gaps", "impute",
        "ignore_self_report", "dismiss_self_report", "causal_overclaim", "overconfident",
        "false_abstention"])
def test_fault_injected_agents_fail_expected_dimensions(agent, expected):
    assert _failures(agent) == expected


def test_missing_data_applies_only_to_windowed_numeric_cases():
    evaluated = {r.case_id for r in run_suite(HealthAgent(), CASES) if r.evaluator == M}
    assert evaluated == {c.case_id for c in CASES if c.kind == "numeric"}


def test_uncertainty_applies_only_to_labelled_cases():
    evaluated = {r.case_id for r in run_suite(HealthAgent(), CASES) if r.evaluator == U}
    assert evaluated == {c.case_id for c in CASES if c.certainty is not None}


def test_every_case_records_provenance():
    assert all(c.provenance for c in CASES)
