"""End-to-end: each fault-injected agent fails exactly the dimensions it should."""

import pytest

from pulseeval.agent import HealthAgent
from pulseeval.evaluation import run_suite
from pulseeval.scenarios import CASES

T, G, A, M = "temporal_consistency", "evidence_grounding", "answer_correctness", "missing_data"


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
    }),
    (HealthAgent(respect_window=False), {
        "rhr_mean_7d": {G, A},  # complete window: coverage claim is true
        "rhr_mean_7d_late_sync": {G, A, M},
        "rhr_mean_7d_gap": {G, A, M},
    }),
    (HealthAgent(report_coverage=False), {
        # right number, right evidence, nothing unknowable -- only coverage misrepresented
        "rhr_mean_7d_late_sync": {M},
        "rhr_mean_7d_gap": {M},
    }),
    (HealthAgent(impute_missing=True), {
        "rhr_mean_7d_late_sync": {M},  # carried-forward 55 leaves the mean at 55.0 exactly
        "rhr_mean_7d_gap": {G, A, M},
    }),
], ids=["reference", "input_order", "no_as_of", "no_window", "silent_gaps", "impute"])
def test_fault_injected_agents_fail_expected_dimensions(agent, expected):
    assert _failures(agent) == expected


def test_missing_data_applies_only_to_windowed_numeric_cases():
    evaluated = {r.case_id for r in run_suite(HealthAgent(), CASES) if r.evaluator == M}
    assert evaluated == {c.case_id for c in CASES if c.kind == "numeric"}


def test_every_case_records_provenance():
    assert all(c.provenance for c in CASES)
