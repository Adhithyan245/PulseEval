"""PHIA-derived cases. Skipped unless PHIA data is present locally (it is not committed)."""

import csv
from pathlib import Path
from statistics import mean

import pytest

from pulseeval.agent import HealthAgent
from pulseeval.evaluation import run_suite
from pulseeval.phia import load_timeline, phia_cases

DATA = Path(__file__).resolve().parents[1] / "data" / "raw" / "phia"
pytestmark = pytest.mark.skipif(not (DATA / "summary_df_465.csv").exists(),
                                reason="PHIA data not present in data/raw/phia/")


def test_expected_values_match_independent_recomputation_from_csv():
    with open(DATA / "summary_df_465.csv", encoding="utf-8", newline="") as f:
        rhr = {row["datetime"][:10]: float(row["resting_heart_rate"])
               for row in csv.DictReader(f) if row["resting_heart_rate"]}
    for case in phia_cases(DATA):
        days = [rid.rsplit("_", 1)[1] for rid in case.expected_record_ids]
        assert mean(rhr[d] for d in days) == pytest.approx(case.expected_value, abs=1e-6)
        assert "Not a PHIA label" in case.provenance


def test_missing_source_day_is_not_imputed():
    timeline = load_timeline(DATA, "465")
    assert timeline.get("phia465_rhr_2023-10-21") is None
    assert len(phia_cases(DATA)[1].expected_record_ids) == 13  # 14-day window, 1 day missing


def test_reference_agent_passes_and_window_fault_is_detected():
    cases = phia_cases(DATA)
    assert all(r.passed for r in run_suite(HealthAgent(), cases))
    failed = {(r.case_id, r.evaluator) for r in run_suite(HealthAgent(respect_window=False), cases)
              if not r.passed}
    assert failed == {(c.case_id, e) for c in cases
                      for e in ("evidence_grounding", "answer_correctness")} | {
        ("phia465_rhr_mean_14d", "missing_data")}  # all-history agent claims "all 14 days"


def test_real_gap_regression_silent_agent_fails_only_missing_data():
    """PHIA 465, 14-day window, 2023-10-21 absent in the source: a correct, grounded,
    temporally valid answer that hides the gap fails missing-data handling only."""
    [_, case] = phia_cases(DATA)
    results = {r.evaluator: r for r in run_suite(HealthAgent(report_coverage=False), [case])}
    assert {e for e, r in results.items() if not r.passed} == {"missing_data"}
    failed = {c.name for c in results["missing_data"].checks if not c.passed}
    assert failed == {"gap_acknowledged"}
    assert "2023-10-21" in results["missing_data"].checks[0].explanation
