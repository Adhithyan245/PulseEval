"""Provenance, reproducibility and the PHIA boundary (Phase 3)."""

import json
import pathlib
import re
from pathlib import Path

import pytest

from pulseeval.benchmark import AGENT_CONFIGS
from pulseeval.evaluation import run_suite
from pulseeval.phia import phia_cases
from pulseeval.scenarios import CASES

SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "pulseeval"
PHIA_DATA = Path(__file__).resolve().parents[1] / "data" / "raw" / "phia"
BY_ID = {c.case_id: c for c in CASES}


def test_case_ids_are_unique_and_every_case_has_provenance_and_semantics():
    assert len(BY_ID) == len(CASES)
    for case in CASES:
        assert case.provenance.strip() and case.description.strip(), case.case_id
        assert case.question and case.target_name, case.case_id


@pytest.mark.parametrize("agent_name", AGENT_CONFIGS)
def test_every_result_traces_back_to_case_agent_and_evidence(agent_name):
    for result in run_suite(AGENT_CONFIGS[agent_name], CASES):
        case = BY_ID[result.case_id]
        assert result.evaluator_version
        for failure in result.failures:
            trace = failure.trace
            assert trace.query == case.question and trace.member_id == case.timeline.member_id
            assert trace.agent_config and trace.agent_version
            known = {r.record_id for r in case.timeline.records}
            # every id the trace retrieved is a real record of this case's timeline
            assert set(trace.retrieved_context) <= known


def test_source_has_no_randomness_or_wall_clock_dependence():
    pattern = re.compile(r"\bimport random\b|\buuid\b|datetime\.now|date\.today|time\.time\(")
    offenders = [p.name for p in SRC.rglob("*.py") if pattern.search(p.read_text(encoding="utf-8"))]
    assert offenders == []


def test_phia_labels_are_never_read_as_expected_answers():
    source = (SRC / "phia.py").read_text(encoding="utf-8")
    for label_source in ("final_v2", "Objective Query", "objective_queries", ".xlsx",
                         '["label"]', '["Answer"]'):
        assert label_source not in source
    assert "summary_df_" in source  # only the raw daily summaries are read


@pytest.mark.skipif(not (PHIA_DATA / "summary_df_465.csv").exists(),
                    reason="PHIA data not present in data/raw/phia/")
def test_phia_enabled_and_disabled_runs_agree_on_synthetic_cases():
    def dump(results):
        return {r.case_id + "/" + r.evaluator: json.dumps(r.model_dump(mode="json"),
                                                         sort_keys=True) for r in results}

    phia = phia_cases(PHIA_DATA)
    for name, agent in AGENT_CONFIGS.items():
        synthetic = dump(run_suite(agent, CASES))
        with_phia = dump(run_suite(agent, CASES + phia))
        assert {k: v for k, v in with_phia.items() if k.split("/")[0] in BY_ID} == synthetic, name
    for case in phia:
        assert "Not a PHIA label" in case.provenance
