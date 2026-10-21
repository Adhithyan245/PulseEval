"""External-agent interface (ADR-014): blind export, answer evaluation, round-trip equivalence."""

import json

import pytest

from pulseeval.benchmark import AGENT_CONFIGS
from pulseeval.evaluation import run_suite
from pulseeval.external import (ANSWERS_FORMAT, CASES_FORMAT, answers_from_agent,
                                evaluate_traces, export_cases)
from pulseeval.scenarios import CASES

BY_ID = {c.case_id: c for c in CASES}
GRADING_FIELDS = ("expected_value", "expected_record", "provenance", "description", "certainty",
                  "conclusion_terms", "causal_support", "causal_basis", "wearable_indicates",
                  "self_report_indicates", "observed_direction", "tolerance", "confounder")


def _outcomes(results):
    return {(r.case_id, r.evaluator): (r.passed, [(c.name, c.passed, c.explanation)
                                                  for c in r.checks]) for r in results}


def test_export_is_blind_and_complete():
    exported = export_cases()
    assert exported["format"] == CASES_FORMAT
    text = json.dumps(exported)
    assert not [f for f in GRADING_FIELDS if f in text]
    assert [c["case_id"] for c in exported["cases"]] == [c.case_id for c in CASES]
    for item in exported["cases"]:
        case = BY_ID[item["case_id"]]
        assert item["question"] == case.question
        # timeline order is preserved: ordering robustness is part of what is tested
        assert [r["record_id"] for r in item["records"]] == [r.record_id
                                                            for r in case.timeline.records]


@pytest.mark.parametrize("agent_name", AGENT_CONFIGS)
def test_external_evaluation_reproduces_built_in_results(agent_name):
    agent = AGENT_CONFIGS[agent_name]
    payload = json.loads(json.dumps(answers_from_agent(agent, agent_name)))  # via real JSON
    name, results, unanswered = evaluate_traces(payload)
    assert name == agent_name and unanswered == []
    assert _outcomes(results) == _outcomes(run_suite(agent, CASES))


def test_unanswered_cases_are_reported_not_skipped_silently():
    payload = answers_from_agent(AGENT_CONFIGS["reference"], "partial")
    payload["answers"] = payload["answers"][:3]
    _, results, unanswered = evaluate_traces(payload)
    assert {r.case_id for r in results} == {c.case_id for c in CASES[:3]}
    assert unanswered == [c.case_id for c in CASES[3:]]


@pytest.mark.parametrize("mutate, message", [
    (lambda p: p["answers"].append({"case_id": "no_such_case", "final_answer": "x"}),
     "unknown case_id"),
    (lambda p: p["answers"].append(dict(p["answers"][0])), "duplicate answer"),
    (lambda p: p.update(format="something-else/9"), "unsupported answers format"),
])
def test_malformed_submissions_are_rejected(mutate, message):
    payload = answers_from_agent(AGENT_CONFIGS["reference"], "ref")
    mutate(payload)
    with pytest.raises(ValueError, match=message):
        evaluate_traces(payload)


def test_free_text_external_answers_are_scored_by_the_same_evaluators():
    payload = {"format": ANSWERS_FORMAT, "agent": "hand-written", "answers": [
        # appropriate abstention on an out-of-scope question
        {"case_id": "unc_out_of_scope_illness", "abstention": True,
         "final_answer": "Heart-rate data alone can't tell me whether you are getting sick."},
        # correct value and evidence, but presented as causation
        {"case_id": "relation_association_only",
         "evidence_used": BY_ID["relation_association_only"].relationship_record_ids,
         "final_answer": "Your HRV averaged 47.0 ms after your 5 shortest nights and 62.0 ms "
                         "after your 5 longest. Short sleep caused your HRV to drop."},
    ]}
    _, results, _ = evaluate_traces(payload)
    failing = {(r.case_id, r.evaluator) for r in results if not r.passed}
    assert failing == {("relation_association_only", "causal_restraint")}


def test_citing_an_unknowable_record_is_a_temporal_failure_by_default():
    # retrieved_context defaults to evidence_used, so a cited future record is caught
    case = BY_ID["goal_future_record"]
    payload = {"format": ANSWERS_FORMAT, "agent": "leaky", "answers": [
        {"case_id": case.case_id, "evidence_used": ["g3"],
         "final_answer": "Your current training goal is half marathon."}]}
    _, results, _ = evaluate_traces(payload)
    temporal = next(r for r in results if r.evaluator == "temporal_consistency")
    assert not temporal.passed and temporal.failures[0].evidence == ["g3"]
