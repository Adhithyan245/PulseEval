"""End-to-end: each fault-injected agent fails exactly the dimensions it should."""

import pytest

from pulseeval.agent import HealthAgent
from pulseeval.evaluation import run_suite
from pulseeval.scenarios import CASES

T, G, A = "temporal_consistency", "evidence_grounding", "answer_correctness"


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
        "rhr_mean_7d_late_sync": {T, A},  # leaked reading is relevant and in-window
    }),
    (HealthAgent(respect_window=False), {
        "rhr_mean_7d": {G, A},  # nothing unknowable, but evidence outside the window
        "rhr_mean_7d_late_sync": {G, A},
    }),
], ids=["reference", "input_order", "no_as_of", "no_window"])
def test_fault_injected_agents_fail_expected_dimensions(agent, expected):
    assert _failures(agent) == expected


def test_every_case_records_provenance():
    assert all(c.provenance for c in CASES)
