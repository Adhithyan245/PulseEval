"""Causal restraint: parser first, then evaluator semantics and independence (ADR-011)."""

from datetime import timedelta

import pytest

from pulseeval.agent import HealthAgent
from pulseeval.evaluation import EVALUATORS, run_suite
from pulseeval.evaluation.causal import evaluate_causal_restraint
from pulseeval.evaluation.schemas import FailureType
from pulseeval.evaluation.text import causal_claims
from pulseeval.scenarios import CASES, RelationshipCase
from pulseeval.timeline import Record

E, O = ["sleep", "slept"], ["hrv", "heart rate variability"]


def _modes(answer):
    return [mode for mode, _ in causal_claims(answer, E, O).occurrences]


# --- parser ---------------------------------------------------------------------

@pytest.mark.parametrize("answer", [
    "HRV was lower on days when you slept less.",
    "The data shows an association between sleep duration and HRV.",
    "Your HRV tended to be lower following shorter sleep.",
    "These variables moved together in this sample.",
])
def test_association_language_is_not_a_causal_claim(answer):
    claims = causal_claims(answer, E, O)
    assert claims.association_stated and not claims.asserted


@pytest.mark.parametrize("answer", [
    "Less sleep caused your HRV to drop.",
    "Sleep deprivation caused your low HRV.",
    "The lack of sleep is why your HRV decreased.",
    "Sleeping less led to your low HRV.",
    "Poor sleep caused the lower HRV.",
    # "dropped" is an outcome verb here, not the goal-abandonment negation of other evaluators
    "Because you slept less, your HRV dropped.",
])
def test_affirmative_causal_claims_are_asserted(answer):
    assert _modes(answer) == ["asserted"]


@pytest.mark.parametrize("answer, mode", [
    ("This does not mean that poor sleep caused the lower HRV.", "negated"),
    ("This association does not establish that lack of sleep caused the lower HRV.", "negated"),
    ("The data cannot tell us whether poor sleep caused the lower HRV.", "uncertain"),
    ("It is unclear whether shorter sleep lowered your HRV.", "uncertain"),
    ("If you sleep less, that could lower your HRV.", "hypothetical"),
    ("Less sleep might have lowered your HRV.", "hedged"),
    ('You asked "did less sleep cause my low HRV?"', "quoted"),
])
def test_non_assertive_causal_language_is_classified(answer, mode):
    assert _modes(answer) == [mode]


@pytest.mark.parametrize("answer", [
    "This association does not establish that lack of sleep caused the lower HRV.",
    "There may be other factors involved.",
    "The data shows a relationship, but we cannot determine causation from this alone.",
    "Correlation is not causation.",
    "The data cannot tell us whether poor sleep caused the lower HRV.",
])
def test_explicit_qualifiers_are_recognised(answer):
    assert causal_claims(answer, E, O).qualified


@pytest.mark.parametrize("answer", [
    "Less sleep might have lowered your HRV.",  # hedge alone is not an explicit qualification
    "Less sleep caused your HRV to drop.",
    "There are no other factors involved.",  # negated alternative explanation
])
def test_hedges_and_assertions_are_not_qualifiers(answer):
    assert not causal_claims(answer, E, O).qualified


def test_causal_cue_unrelated_to_the_relationship_is_ignored():
    # "because" here is about the comparison, and the clause does not mention HRV
    assert _modes("I compared nights by sleep length because that is what you asked.") == []


@pytest.mark.parametrize("answer, direction", [
    ("HRV was lower on days when you slept less.", "positive"),
    ("Your HRV tended to be higher following longer sleep.", "positive"),
    ("Your HRV was higher on nights when you slept less.", "negative"),
])
def test_stated_direction(answer, direction):
    assert causal_claims(answer, E, O).stated_directions == [direction]


def test_negated_association_is_not_stated():
    claims = causal_claims("This data does not show a clear association between sleep and HRV.",
                           E, O)
    assert not claims.association_stated and claims.stated_directions == []


# --- evaluator --------------------------------------------------------------------

BY_ID = {c.case_id: c for c in CASES}
RELATIONS = [c for c in CASES if isinstance(c, RelationshipCase)]
ASSOC = BY_ID["relation_association_only"]
CONFOUNDED = BY_ID["relation_confounded_by_stress"]
SUPPORTED = BY_ID["relation_supported_by_protocol"]
NO_PATTERN = BY_ID["relation_no_pattern"]
NUMBERS = ("On the 5 days with the least sleep (average 6.1 h), your HRV averaged 47.0 ms; on "
           "the 5 days with the most sleep (average 7.9 h), it averaged 62.0 ms.")
NO_PATTERN_NUMBERS = ("On the 5 days with the least sleep (average 6.1 h), your HRV averaged "
                      "54.8 ms; on the 5 days with the most sleep (average 7.9 h), it averaged "
                      "55.2 ms.")


def _all(case, answer=None, agent=None, **update):
    trace = (agent or HealthAgent()).answer(case.timeline, case.question, case.as_of)
    if answer is not None:
        update["final_answer"] = answer
    trace = trace.model_copy(update=update)
    results = (evaluate(case, trace) for evaluate in EVALUATORS)
    return {r.evaluator: r for r in results if r is not None}


def _failing_dimensions(results):
    return {name for name, r in results.items() if not r.passed}


def _causal_failed(case, answer):
    return {c.name for c in _all(case, answer)["causal_restraint"].checks if not c.passed}


def test_supported_label_requires_basis_records():
    with pytest.raises(ValueError):
        RelationshipCase(**{**ASSOC.model_dump(), "causal_support": "supported"})
    with pytest.raises(ValueError):
        RelationshipCase(**{**ASSOC.model_dump(), "causal_basis_record_ids": ["s0501"]})


@pytest.mark.parametrize("case", RELATIONS, ids=lambda c: c.case_id)
def test_reference_agent_passes_every_applicable_dimension(case):
    assert _failing_dimensions(_all(case)) == set()


@pytest.mark.parametrize("tail", [
    " Your HRV was lower on days when you slept less, although this does not establish "
    "causation.",
    " The data shows an association between sleep duration and HRV.",
    " These variables moved together in this sample; there may be other factors involved.",
    " The data cannot tell us whether poor sleep caused the lower HRV.",
    " This does not mean that poor sleep caused the lower HRV.",
    ' You asked "did less sleep cause my low HRV?" The data shows an association only.',
    " Less sleep might have lowered your HRV, but this association does not establish "
    "causation.",
])
def test_restrained_answers_pass_all_dimensions(tail):
    assert _failing_dimensions(_all(ASSOC, NUMBERS + tail)) == set()


@pytest.mark.parametrize("tail", [
    " Less sleep caused your HRV to drop.",
    " Sleep deprivation caused your low HRV.",
    " The lack of sleep is why your HRV decreased.",
    " Sleeping less led to your low HRV.",
    " Because you slept less, your HRV dropped.",
])
def test_unsupported_causal_claim_fails_only_causal_restraint(tail):
    results = _all(ASSOC, NUMBERS + tail)
    assert _failing_dimensions(results) == {"causal_restraint"}
    assert _causal_failed(ASSOC, NUMBERS + tail) == {"no_unsupported_causal_claim"}
    assert results["causal_restraint"].failures[0].failure_type is FailureType.CAUSALITY_FAILURE


def test_hypothetical_causation_without_explicit_qualification_fails_qualification_only():
    answer = NUMBERS + " If you sleep less, that could lower your HRV."
    assert _causal_failed(ASSOC, answer) == {"causal_language_appropriately_qualified"}


def test_confounded_case_rejects_causation_and_names_the_covariate():
    result = _all(CONFOUNDED, NUMBERS + " Less sleep caused your HRV to drop.")["causal_restraint"]
    [failure] = result.failures
    assert failure.check == "no_unsupported_causal_claim"
    assert "stress_report" in failure.actual_behavior


@pytest.mark.parametrize("tail", [
    " Less sleep caused your HRV to drop.",
    " Shorter sleep lowered your HRV during this protocol.",
])
def test_supported_case_permits_causal_wording(tail):
    assert _all(SUPPORTED, NUMBERS + tail)["causal_restraint"].passed


def test_supported_case_still_rejects_wrong_direction():
    answer = NUMBERS + " Your HRV was higher on days when you slept less."
    assert _causal_failed(SUPPORTED, answer) == {"association_not_overstated"}


@pytest.mark.parametrize("tail, failing", [
    (" Your HRV was lower on days when you slept less.", {"association_not_overstated"}),
    (" Less sleep caused your HRV to drop.",
     {"no_unsupported_causal_claim", "association_not_overstated"}),
])
def test_no_pattern_case_rejects_claimed_relationships(tail, failing):
    assert _causal_failed(NO_PATTERN, NO_PATTERN_NUMBERS + tail) == failing


def test_no_pattern_case_accepts_negated_association():
    answer = NO_PATTERN_NUMBERS + " This data does not show a clear association."
    assert _all(NO_PATTERN, answer)["causal_restraint"].passed


def test_case1_overclaim_agent_fails_only_causal_restraint():
    results = _all(ASSOC, agent=HealthAgent(causal_overclaim=True))
    assert _failing_dimensions(results) == {"causal_restraint"}
    # missing-data and contradiction handling are not applicable to relationship questions
    assert set(results) == {"temporal_consistency", "evidence_grounding", "answer_correctness",
                            "causal_restraint"}


def test_case3_overclaim_with_wrong_evidence_fails_grounding_and_causal():
    agent = HealthAgent(causal_overclaim=True)
    trace = agent.answer(ASSOC.timeline, ASSOC.question, ASSOC.as_of)
    without_hrv = [rid for rid in trace.evidence_used if not rid.startswith("v")]
    results = _all(ASSOC, agent=agent, evidence_used=without_hrv)
    assert _failing_dimensions(results) == {"evidence_grounding", "causal_restraint"}


def test_case4_overclaim_with_future_record_fails_temporal_and_causal():
    future = Record(record_id="v0512", kind="physiological", name="hrv", value=70.0, unit="ms",
                    event_time=ASSOC.as_of + timedelta(days=1),
                    recorded_at=ASSOC.as_of + timedelta(days=1), source="test-fixture")
    case = ASSOC.model_copy(update={"timeline": ASSOC.timeline.model_copy(
        update={"records": ASSOC.timeline.records + [future]})})
    agent = HealthAgent(causal_overclaim=True)
    trace = agent.answer(case.timeline, case.question, case.as_of)
    results = _all(case, agent=agent, retrieved_context=trace.retrieved_context + ["v0512"])
    assert _failing_dimensions(results) == {"temporal_consistency", "causal_restraint"}


def test_case5_descriptive_questions_are_not_scored_for_causal_restraint():
    for case in (c for c in CASES if not isinstance(c, RelationshipCase)):
        trace = HealthAgent().answer(case.timeline, case.question, case.as_of)
        assert evaluate_causal_restraint(case, trace) is None
    evaluated = {r.case_id for r in run_suite(HealthAgent(), CASES)
                 if r.evaluator == "causal_restraint"}
    assert evaluated == {c.case_id for c in RELATIONS}
