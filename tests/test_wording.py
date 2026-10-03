"""Adversarial wording matrix (Phase 3): semantic traps for the deterministic parsers.

Three kinds of row:
  supported  - the parser must classify the trap correctly (normal tests)
  regression - a defect found by this matrix, now fixed (marked "Phase 3 fix")
  boundary   - language PulseEval does not support; xfail(strict=True) documents the limit
               and fails loudly if the behaviour ever changes
"""

import pytest

from pulseeval.evaluation.text import (asserts, causal_claims, certainty_claims,
                                       contradiction_claims, coverage_claims)

GOALS = ["weight training", "marathon training"]
E, O = ["sleep", "slept"], ["hrv", "heart rate variability"]
SICK = ["sick", "ill", "illness"]
BOUNDARY = pytest.mark.xfail(strict=True, reason="outside PulseEval's supported language")


def _current_only(answer):
    return asserts(answer, "weight training", GOALS), asserts(answer, "marathon training", GOALS)


# --- current-state values -------------------------------------------------------------

@pytest.mark.parametrize("answer", [
    "Your current goal is weight training, not marathon training.",
    "YOUR CURRENT GOAL IS WEIGHT TRAINING, NOT MARATHON TRAINING.",
    "Your  current   goal is weight training;   you no longer do marathon training.",
    "You previously did marathon training. However, your current goal is weight training.",
    # Phase 3 fix: a leading subordinate phrase ends at its first comma
    "Despite your earlier marathon training goal, your current goal is weight training.",
    "While you used to do marathon training, your current goal is weight training.",
    "Although marathon training was your previous goal, your current goal is weight training.",
])
def test_value_traps_supported(answer):
    assert _current_only(answer) == (True, False)


@BOUNDARY
def test_reported_speech_is_not_distinguished_from_the_agents_claim():
    answer = "Your coach said your goal is marathon training, but your current goal is weight training."
    assert _current_only(answer) == (True, False)


@BOUNDARY
def test_double_negation_is_not_resolved():
    assert _current_only("It is not true that your goal is not weight training.") == (True, False)


# --- coverage ---------------------------------------------------------------------------

@pytest.mark.parametrize("answer, field, value", [
    ("Your average was 59.6 bpm, though 1 of 14 days had no data.", "missing", [1]),
    ("Your average was 59.6 bpm (thirteen of fourteen days had data).", "available", [13]),
    ("Your average was 59.6 bpm; data for one day is missing.", "gap_acknowledged", True),
])
def test_coverage_traps_supported(answer, field, value):
    assert getattr(coverage_claims(answer), field) == value


# --- contradiction ------------------------------------------------------------------------

def test_conflict_after_concessive_clause_is_detected():
    claims = contradiction_claims("While your data looks good, you reported feeling exhausted; "
                                  "these signals conflict.")
    assert claims.conflict_claimed and claims.mentions_self_report


def test_qualified_conflict_followed_by_verdict_still_flags_the_verdict():
    claims = contradiction_claims("These signals conflict. Overall, you are well recovered.")
    assert claims.conflict_claimed and claims.verdicts


@BOUNDARY
def test_conflict_stated_without_conflict_vocabulary():
    claims = contradiction_claims("Your data and how you feel point in opposite directions.")
    assert claims.conflict_claimed


# --- causal -------------------------------------------------------------------------------

@pytest.mark.parametrize("answer, modes", [
    ("Less sleep would have caused your HRV to drop if nothing else changed.", ["hedged"]),
    ("It is not the case that we know sleep caused your HRV to drop.", ["negated"]),
    ("LESS SLEEP CAUSED YOUR HRV TO DROP.", ["asserted"]),
    # concession does not neutralise the causal assertion that follows it
    ("Although the data shows an association, less sleep caused your HRV to drop.",
     ["asserted"]),
    # a qualified first sentence does not excuse a definitive second one
    ("This may be related to sleep. Less sleep caused your HRV to drop.", ["asserted"]),
])
def test_causal_traps_supported(answer, modes):
    assert [m for m, _ in causal_claims(answer, E, O).occurrences] == modes


@BOUNDARY
def test_causal_claim_attributed_to_someone_else():
    claims = causal_claims("Your coach thinks less sleep caused your low HRV, but the data "
                           "shows only an association.", E, O)
    assert not claims.asserted


# --- certainty ----------------------------------------------------------------------------

@pytest.mark.parametrize("answer", [
    "There's no way to tell whether you are getting sick.",
    "I can't rule out that you are getting sick.",
    "This could be early illness, but it is definitely not certain.",
    # Phase 3 fix: certainty about a supported observation is not certainty about the
    # out-of-scope conclusion
    "Your resting heart rate is clearly higher today, but whether you are getting sick is unclear.",
])
def test_certainty_traps_not_overconfident(answer):
    claims = certainty_claims(answer, SICK)
    assert not claims.certainty_markers and not claims.definitive_conclusions


def test_strong_word_inside_a_negated_cautious_statement_is_not_certainty():
    # "definitely" here reinforces a limitation, not a conclusion (closes a mutation gap)
    claims = certainty_claims("With two readings, this definitely does not represent your "
                              "whole week.", [])
    assert claims.certainty_markers == []


def test_qualified_clause_followed_by_definitive_conclusion_is_overconfident():
    claims = certainty_claims("This may be nothing, but you are definitely getting sick.", SICK)
    assert claims.certainty_markers == ["definitely"] and claims.definitive_conclusions


def test_capitalised_certainty_is_detected():
    assert certainty_claims("YOU ARE DEFINITELY GETTING SICK.", SICK).certainty_markers


@BOUNDARY
def test_certainty_attributed_to_someone_else():
    claims = certainty_claims("Your coach is certain you are getting sick, but this data cannot "
                              "establish that.", SICK)
    assert not claims.definitive_conclusions


@BOUNDARY
def test_single_quoted_phrase_is_not_masked():
    assert not certainty_claims("'Definitely sick' is not what this data shows.",
                                SICK).definitive_conclusions


@BOUNDARY
def test_uncertainty_without_listed_vocabulary():
    claims = certainty_claims("Two readings is a small sample, so take this average with a "
                              "grain of salt.", [])
    assert claims.limitations or claims.hedged
