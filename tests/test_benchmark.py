"""Benchmark report (ADR-013): fault model, independence, overlaps, and report freshness."""

import pathlib

import pytest

from pulseeval.benchmark import (AGENT_CONFIGS, DIMENSIONS, FAULT_INTENT, OVERLAPS,
                                 co_failures, curated_witnesses, failing, fault_matrix,
                                 independence, render, run_all)

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def runs():
    return run_all()


def test_reference_agent_passes_every_applicable_dimension(runs):
    assert {cid for cid, res in runs["reference"].items() if failing(res)} == set()


def test_every_fault_triggers_exactly_its_intended_or_explained_dimensions(runs):
    for agent, row in fault_matrix(runs).items():
        assert "MISSING" not in row.values(), (agent, row)
        assert "UNEXPECTED" not in row.values(), (agent, row)


def test_every_fault_has_an_intent():
    faults = set(AGENT_CONFIGS) - {"reference"}
    assert faults and set(FAULT_INTENT) == faults


def test_every_dimension_fails_alone_somewhere_and_passes_while_another_fails(runs):
    ind = independence(runs)
    for dim, _ in DIMENSIONS:
        assert ind[dim]["sole"] or ind[dim]["curated"], dim
        assert ind[dim]["passes_while_other_fails"], dim


def test_curated_witnesses_fail_only_their_dimension():
    for dim, label, results in curated_witnesses():
        assert failing(results) == {dim}, label


def test_every_co_failing_pair_is_explained(runs):
    unexplained = [pair for pair in co_failures(runs) if frozenset(pair) not in OVERLAPS]
    assert unexplained == []


def test_report_is_deterministic_and_ascii():
    report = render()
    assert report == render()
    assert report.isascii()


def test_committed_benchmark_report_is_up_to_date():
    committed = (ROOT / "BENCHMARK.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert committed == render(), "regenerate: python -m pulseeval --benchmark > BENCHMARK.md"
