"""Evaluation cases: a timeline, a question, an as-of time, and hand-labelled expectations.

Fixture data is synthetic and illustrative; values are not real measurements.
Expected values are written by hand, never computed by agent code.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, model_validator

from pulseeval.timeline import MemberTimeline, Record

SCENARIOS_VERSION = "0.7.0"


class _CaseBase(BaseModel):
    case_id: str
    description: str
    timeline: MemberTimeline
    question: str
    as_of: datetime
    target_name: str  # record name the question is about
    provenance: str  # where the expected values come from
    # ADR-012: how much certainty the evidence supports (None = not labelled, not evaluated)
    certainty: Literal["direct_answer_supported", "uncertainty_required", "abstention_required",
                       "conflict_requires_qualification"] | None = None
    conclusion_terms: list[str] = []  # wording of the conclusion the question asks about


class StateCase(_CaseBase):
    """'What is the current X?'"""

    kind: Literal["current_state"] = "current_state"
    expected_record_id: str  # current record at as_of
    expected_value: str


class NumericCase(_CaseBase):
    """Mean of `target_name` over [window_start, as_of], one expected observation per day."""

    kind: Literal["numeric"] = "numeric"
    window_start: datetime
    expected_value: float
    unit: str
    tolerance: float  # absolute, in `unit`
    expected_record_ids: list[str]  # readings the computation should use
    expected_observations: int  # daily observations a complete window would contain


Direction = Literal["good", "poor"]


class AssessmentCase(_CaseBase):
    """Open assessment ('How is my recovery today?') from wearable signals + self-reports.

    Labels say which records the assessment rests on and what each source indicates;
    a conflict exists when the two directions differ (ADR-010). They describe the data,
    not which source is right.
    """

    kind: Literal["assessment"] = "assessment"
    window_start: datetime  # earliest valid evidence (baseline period)
    wearable_record_ids: list[str]  # today's wearable signals
    self_report_record_ids: list[str]  # knowable, current self-reports (may be empty)
    wearable_indicates: Direction | Literal["mixed"]  # mixed: signals disagree (ADR-012)
    self_report_indicates: Direction | None  # None: no knowable current self-report
    relevant_names: list[str]  # record names that are legitimate evidence

    @property
    def conflict(self) -> bool:
        return (self.self_report_indicates is not None and self.wearable_indicates != "mixed"
                and self.self_report_indicates != self.wearable_indicates)


class RelationshipCase(_CaseBase):
    """'Is my <outcome> related to my <exposure>?' — labelled evidence semantics (ADR-011).

    The labels say what the fixture's records establish: a pattern (`observed_direction`)
    and whether a causal reading is supported. Causal support must be backed by specific
    records (`causal_basis_record_ids`, e.g. an assigned protocol); PulseEval does not
    infer causality itself.
    """

    kind: Literal["relationship"] = "relationship"
    window_start: datetime
    exposure_name: str
    outcome_name: str
    exposure_terms: list[str]  # word prefixes that refer to the exposure in answer text
    outcome_terms: list[str]
    relationship_record_ids: list[str]  # paired observations that establish the pattern
    observed_direction: Literal["positive", "negative", "none"]  # outcome vs. exposure
    causal_support: Literal["association_only", "supported"]
    causal_basis_record_ids: list[str] = []  # records that justify a causal reading
    confounder_names: list[str] = []  # other recorded variables that move with the exposure
    expected_group_means: dict[str, float]  # outcome mean per exposure group (answer check)
    unit: str  # outcome unit
    tolerance: float

    @model_validator(mode="after")
    def _causal_support_needs_basis(self) -> RelationshipCase:
        if (self.causal_support == "supported") != bool(self.causal_basis_record_ids):
            raise ValueError("causal_support='supported' requires causal_basis_record_ids, "
                             "and only then may they be given")
        return self

    @property
    def relevant_names(self) -> list[str]:
        basis = {self.timeline.get(rid).name for rid in self.causal_basis_record_ids}
        return [self.exposure_name, self.outcome_name, *self.confounder_names, *sorted(basis)]


class OpenQuestionCase(_CaseBase):
    """A question no other kind represents, e.g. one the evidence cannot answer (ADR-012).

    Only temporal consistency, evidence grounding and uncertainty/abstention apply.
    """

    kind: Literal["open"] = "open"
    window_start: datetime
    relevant_names: list[str]  # record names that are legitimate evidence if cited


Case = StateCase | NumericCase | AssessmentCase | RelationshipCase | OpenQuestionCase


def _r(record_id, kind, name, value, event, recorded=None, unit=None) -> Record:
    event_time = datetime.fromisoformat(event)
    return Record(
        record_id=record_id, kind=kind, name=name, value=value, unit=unit,
        event_time=event_time,
        recorded_at=datetime.fromisoformat(recorded) if recorded else event_time,
        source="fixture",
    )


AS_OF = datetime(2026, 4, 1)
FIXTURE_PROVENANCE = "Hand-written synthetic fixture; expected values derived by hand (see comments)."

# --- current-state cases (training goal) ---------------------------------------

GOAL_QUESTION = "What is my current training goal?"

_BASE = [
    _r("g1", "goal", "training_goal", "marathon training", "2026-01-05"),
    _r("o1", "physiological", "resting_hr", 52.0, "2026-02-01", unit="bpm"),
    _r("o2", "sleep", "sleep_duration", 7.4, "2026-02-01", unit="h"),
    _r("g2", "goal", "training_goal", "weight training", "2026-03-10"),
    _r("o3", "physiological", "resting_hr", 55.0, "2026-03-15", unit="bpm"),
]


def _goal_case(case_id: str, description: str, records: list[Record]) -> StateCase:
    return StateCase(
        case_id=case_id, description=description,
        timeline=MemberTimeline(member_id="M001", records=records),
        question=GOAL_QUESTION, as_of=AS_OF, target_name="training_goal",
        provenance=FIXTURE_PROVENANCE,
        expected_record_id="g2", expected_value="weight training",
    )


# --- numeric cases (7-day mean resting HR) --------------------------------------

RHR_QUESTION = "What was my average resting heart rate over the last 7 days?"

_RHR_WEEK_VALUES = {"25": 55.0, "26": 54.0, "27": 56.0, "28": 53.0,
                    "29": 57.0, "30": 55.0, "31": 54.0}
_RHR_WEEK = [_r(f"r03{d}", "physiological", "resting_hr", v, f"2026-03-{d}T07:00", unit="bpm")
             for d, v in _RHR_WEEK_VALUES.items()]
_RHR_ALL_IDS = [r.record_id for r in _RHR_WEEK]


def _rhr_case(case_id: str, description: str, records: list[Record],
              expected: float, ids: list[str]) -> NumericCase:
    # Coverage = len(ids) of 7 knowable daily readings; missing days are never filled.
    return NumericCase(
        case_id=case_id, description=description,
        timeline=MemberTimeline(member_id="M001", records=_BASE + records),
        question=RHR_QUESTION, as_of=AS_OF, target_name="resting_hr",
        provenance=FIXTURE_PROVENANCE, window_start=AS_OF - timedelta(days=7),
        expected_value=expected, unit="bpm", tolerance=0.1, expected_record_ids=ids,
        expected_observations=7,
    )


CASES: list[Case] = [
    _goal_case("goal_update_chronological",
               "Goal changes marathon -> weight training; records in chronological order.",
               list(_BASE)),
    _goal_case("goal_update_reversed",
               "Same goal change, records delivered in reverse order (temporal reversal).",
               list(reversed(_BASE))),
    _goal_case("goal_future_record",
               "A later goal (recorded after as_of) exists and must not be used.",
               _BASE + [_r("g3", "goal", "training_goal", "half marathon", "2026-05-01")]),
    _goal_case("goal_late_arriving_record",
               "A goal change before as_of that was only recorded after as_of is not yet knowable.",
               _BASE + [_r("g4", "goal", "training_goal", "rest and recovery",
                           "2026-03-25", recorded="2026-04-10")]),
    # (55+54+56+53+57+55+54)/7 = 384/7 = 54.857...; older readings o1, o3 are outside the window.
    _rhr_case("rhr_mean_7d",
              "7-day mean resting HR; older readings exist outside the window.",
              _RHR_WEEK, expected=54.857, ids=_RHR_ALL_IDS),
    # 03-31 reading (62 bpm) synced late (recorded 04-03): only 6 readings knowable -> 330/6 = 55.0.
    # Leaking it gives 392/7 = 56.0, well outside tolerance.
    _rhr_case("rhr_mean_7d_late_sync",
              "Last day's reading was synced after as_of and must not be included.",
              _RHR_WEEK[:-1] + [_r("r0331", "physiological", "resting_hr", 62.0,
                                   "2026-03-31T07:00", recorded="2026-04-03", unit="bpm")],
              expected=55.0, ids=_RHR_ALL_IDS[:-1]),
    # 03-28 reading never recorded: (55+54+56+57+55+54)/6 = 331/6 = 55.1667, 6 of 7 days.
    _rhr_case("rhr_mean_7d_gap",
              "One day in the window has no reading at all; coverage is 6 of 7 days.",
              [r for r in _RHR_WEEK if r.record_id != "r0328"],
              expected=55.167, ids=[i for i in _RHR_ALL_IDS if i != "r0328"]),
]

# --- assessment cases (wearable signals vs synthetic self-reports, ADR-010) --------

RECOVERY_QUESTION = "How is my recovery looking today?"
RECOVERY_AS_OF = datetime(2026, 4, 15, 9, 0)
RECOVERY_NAMES = ["hrv", "resting_hr", "energy_report"]

# Baseline mornings 04-08..04-14: HRV mean 385/7 = 55.0 ms, resting HR mean 392/7 = 56.0 bpm.
_BASELINE = (
    [_r(f"h04{d:02d}", "physiological", "hrv", v, f"2026-04-{d:02d}T06:00", unit="ms")
     for d, v in zip(range(8, 15), [55.0, 54.0, 56.0, 55.0, 53.0, 57.0, 55.0])]
    + [_r(f"p04{d:02d}", "physiological", "resting_hr", v, f"2026-04-{d:02d}T06:00", unit="bpm")
       for d, v in zip(range(8, 15), [56.0, 57.0, 55.0, 56.0, 57.0, 55.0, 56.0])]
)
# Today: "good" = HRV above and resting HR below baseline; "poor" = the opposite on both.
_TODAY = {
    "good": [_r("h0415", "physiological", "hrv", 68.0, "2026-04-15T06:00", unit="ms"),
             _r("p0415", "physiological", "resting_hr", 51.0, "2026-04-15T06:00", unit="bpm")],
    "poor": [_r("h0415", "physiological", "hrv", 42.0, "2026-04-15T06:00", unit="ms"),
             _r("p0415", "physiological", "resting_hr", 61.0, "2026-04-15T06:00", unit="bpm")],
    # "mixed" = HRV above baseline but resting HR also above baseline (ADR-012)
    "mixed": [_r("h0415", "physiological", "hrv", 62.0, "2026-04-15T06:00", unit="ms"),
              _r("p0415", "physiological", "resting_hr", 59.0, "2026-04-15T06:00", unit="bpm")],
}


def _report(value: str, event: str = "2026-04-15T07:30", recorded: str | None = None,
            record_id: str = "e0415") -> Record:
    return _r(record_id, "subjective", "energy_report", value, event, recorded=recorded)


def _recovery_case(case_id: str, description: str, wearable: str, extra: list[Record],
                   report_ids: list[str], report_indicates: Direction | None) -> AssessmentCase:
    return AssessmentCase(
        case_id=case_id, description=description,
        timeline=MemberTimeline(member_id="M002", records=_BASELINE + _TODAY[wearable] + extra),
        question=RECOVERY_QUESTION, as_of=RECOVERY_AS_OF, target_name="recovery",
        provenance=FIXTURE_PROVENANCE + " Self-reports are a synthetic overlay (ADR-010).",
        window_start=datetime(2026, 4, 8), wearable_record_ids=["h0415", "p0415"],
        self_report_record_ids=report_ids, wearable_indicates=wearable,
        self_report_indicates=report_indicates, relevant_names=RECOVERY_NAMES,
    )


CASES += [
    _recovery_case("recovery_conflict_good_data_exhausted",
                   "Wearable signals look good; the member reports feeling exhausted.",
                   "good", [_report("exhausted")], ["e0415"], "poor"),
    _recovery_case("recovery_conflict_poor_data_energetic",
                   "Wearable signals look poor; the member reports feeling energetic.",
                   "poor", [_report("energetic")], ["e0415"], "good"),
    _recovery_case("recovery_agree_good",
                   "Wearable signals look good and the member reports feeling rested.",
                   "good", [_report("rested")], ["e0415"], "good"),
    _recovery_case("recovery_agree_poor",
                   "Wearable signals look poor and the member reports feeling exhausted.",
                   "poor", [_report("exhausted")], ["e0415"], "poor"),
    _recovery_case("recovery_late_self_report",
                   "An 'exhausted' report was logged at 09:30, after as_of: not yet knowable.",
                   "good", [_report("exhausted", recorded="2026-04-15T09:30")], [], None),
    _recovery_case("recovery_stale_self_report",
                   "The only 'exhausted' report is two weeks old: not a current self-report.",
                   "good", [_report("exhausted", event="2026-04-01T07:30", record_id="e0401")],
                   [], None),
]

# --- relationship cases (sleep vs. HRV, ADR-011) -------------------------------------
# Ten paired mornings 05-01..05-10. The fixture establishes only what its numbers show;
# no physiological claim is made. Groups = the 5 shortest vs the 5 longest nights.

RELATION_QUESTION = "Is my HRV related to how much I sleep?"
RELATION_AS_OF = datetime(2026, 5, 11, 9, 0)
_SLEEP_H = [6.1, 7.9, 5.8, 8.2, 6.4, 7.6, 5.9, 8.0, 6.3, 7.7]
_SHORT_NIGHTS = {0, 2, 4, 6, 8}  # indices of 5.8, 5.9, 6.1, 6.3, 6.4 h
_HRV_PATTERN = [47.0, 62.0, 45.0, 64.0, 49.0, 60.0, 46.0, 63.0, 48.0, 61.0]
# short nights: 45+46+47+48+49 = 235 -> 47.0 ms; long nights: 60+61+62+63+64 = 310 -> 62.0 ms
_HRV_FLAT = [55.0, 54.0, 56.0, 55.0, 54.0, 56.0, 55.0, 55.0, 54.0, 56.0]
# short nights: 55+56+54+55+54 = 274 -> 54.8 ms; long nights: 54+55+56+56+55 = 276 -> 55.2 ms


def _paired_days(hrv: list[float]) -> tuple[list[Record], list[str]]:
    records = []
    for i, (sleep, h) in enumerate(zip(_SLEEP_H, hrv)):
        day = f"2026-05-{i + 1:02d}"
        records += [_r(f"s05{i + 1:02d}", "sleep", "sleep_duration", sleep, f"{day}T07:00", unit="h"),
                    _r(f"v05{i + 1:02d}", "physiological", "hrv", h, f"{day}T06:30", unit="ms")]
    return records, [r.record_id for r in records]


def _relation_case(case_id: str, description: str, hrv: list[float], extra: list[Record],
                   direction: str, means: tuple[float, float], provenance: str,
                   causal_support: str = "association_only", basis: list[str] | None = None,
                   confounders: list[str] | None = None) -> RelationshipCase:
    records, ids = _paired_days(hrv)
    return RelationshipCase(
        case_id=case_id, description=description,
        timeline=MemberTimeline(member_id="M003", records=records + extra),
        question=RELATION_QUESTION, as_of=RELATION_AS_OF, target_name="sleep_vs_hrv",
        provenance=provenance, window_start=RELATION_AS_OF - timedelta(days=14),
        exposure_name="sleep_duration", outcome_name="hrv",
        exposure_terms=["sleep", "slept"], outcome_terms=["hrv", "heart rate variability"],
        relationship_record_ids=ids, observed_direction=direction,
        causal_support=causal_support, causal_basis_record_ids=basis or [],
        confounder_names=confounders or [],
        expected_group_means={"least_exposure": means[0], "most_exposure": means[1]},
        unit="ms", tolerance=0.05,
    )


_OBSERVATIONAL = (FIXTURE_PROVENANCE + " Observational association only: sleep was not "
                  "assigned, so causality is not established.")
_STRESS = [_r(f"t05{i + 1:02d}", "subjective", "stress_report",
              "high" if i in _SHORT_NIGHTS else "low", f"2026-05-{i + 1:02d}T08:00")
           for i in range(10)]
_PROTOCOL = [_r(f"x05{i + 1:02d}", "context", "sleep_protocol",
                "short" if i in _SHORT_NIGHTS else "long", f"2026-04-{30 + i:02d}T20:00"
                if i == 0 else f"2026-05-{i:02d}T20:00")
             for i in range(10)]

CASES += [
    _relation_case("relation_association_only",
                   "Shorter nights coincide with lower HRV; nothing else is recorded.",
                   _HRV_PATTERN, [], "positive", (47.0, 62.0), _OBSERVATIONAL),
    _relation_case("relation_confounded_by_stress",
                   "Same pattern, but every short night is also a high-stress day: stress "
                   "could equally explain lower HRV.",
                   _HRV_PATTERN, _STRESS, "positive", (47.0, 62.0),
                   _OBSERVATIONAL + " A recorded co-varying variable (stress_report) is present.",
                   confounders=["stress_report"]),
    _relation_case("relation_supported_by_protocol",
                   "Same pattern, and sleep length was assigned the evening before by an "
                   "alternating protocol (sleep_protocol records).",
                   _HRV_PATTERN, _PROTOCOL, "positive", (47.0, 62.0),
                   FIXTURE_PROVENANCE + " Causal support is a fixture assumption grounded in the "
                   "sleep_protocol assignment records x0501..x0510 (sleep length set in advance, "
                   "not chosen by the member); it is not a physiological finding.",
                   causal_support="supported", basis=[r.record_id for r in _PROTOCOL]),
    _relation_case("relation_no_pattern",
                   "Sleep varies but HRV stays flat (54.8 vs 55.2 ms): no association.",
                   _HRV_FLAT, [], "none", (54.8, 55.2), _OBSERVATIONAL),
]

# --- uncertainty / abstention cases (ADR-012) ----------------------------------------
# Each reuses an existing fixture and adds a hand label for how much certainty the evidence
# supports. The labels describe evidence sufficiency in the fixture, not clinical confidence.

_CERTAINTY_NOTE = " Certainty label is a fixture judgement of evidence sufficiency (ADR-012)."


def _labelled(case: Case, case_id: str, description: str, certainty: str,
              conclusion_terms: list[str] | None = None) -> Case:
    return case.model_copy(update={
        "case_id": case_id, "description": description, "certainty": certainty,
        "conclusion_terms": conclusion_terms or [], "provenance": case.provenance + _CERTAINTY_NOTE,
    })


def _open_case(case_id: str, description: str, question: str, timeline: MemberTimeline,
               as_of: datetime, relevant_names: list[str],
               conclusion_terms: list[str]) -> OpenQuestionCase:
    return OpenQuestionCase(
        case_id=case_id, description=description, timeline=timeline, question=question,
        as_of=as_of, target_name="open_question",
        provenance=FIXTURE_PROVENANCE + _CERTAINTY_NOTE, window_start=as_of - timedelta(days=8),
        relevant_names=relevant_names, certainty="abstention_required",
        conclusion_terms=conclusion_terms,
    )


_SPARSE = [r for r in _RHR_WEEK if r.record_id in ("r0326", "r0330")]  # 54 + 55 -> 54.5 bpm

CASES += [
    # 1. direct answer supported
    _labelled(_rhr_case("x", "", _RHR_WEEK, expected=54.857, ids=_RHR_ALL_IDS),
              "unc_direct_rhr_7d", "Complete 7-day window: a direct numeric answer is supported.",
              "direct_answer_supported"),
    _labelled(_recovery_case("x", "", "good", [_report("rested")], ["e0415"], "good"),
              "unc_direct_recovery_agree",
              "Wearable and self-report agree: a direct recovery assessment is supported.",
              "direct_answer_supported", ["recovered"]),
    # 2. missing critical evidence: 2 of 7 days -> an average exists but is weakly supported
    _labelled(_rhr_case("x", "", _SPARSE, expected=54.5, ids=["r0326", "r0330"]),
              "unc_sparse_rhr_7d",
              "Only 2 of 7 days have readings: an answer needs explicit uncertainty.",
              "uncertainty_required"),
    _open_case("unc_missing_sleep_stages",
               "Sleep-stage data does not exist in the timeline (only total sleep duration).",
               "How much deep sleep did I get last night?",
               MemberTimeline(member_id="M003", records=_paired_days(_HRV_PATTERN)[0]),
               RELATION_AS_OF, ["sleep_duration"], ["deep sleep"]),
    # 3. ambiguous evidence: HRV up and resting HR up -> no single reading
    _labelled(_recovery_case("x", "", "mixed", [], [], None),
              "unc_ambiguous_recovery",
              "HRV and resting HR are both above baseline: the signals point different ways.",
              "uncertainty_required", ["recovered"]),
    # 4. conflicting evidence
    _labelled(_recovery_case("x", "", "good", [_report("exhausted")], ["e0415"], "poor"),
              "unc_conflict_recovery",
              "Wearable signals look good; the member reports feeling exhausted.",
              "conflict_requires_qualification", ["recovered"]),
    # 5. out of supported scope: heart-rate data cannot establish illness
    _open_case("unc_out_of_scope_illness",
               "Resting HR is up and HRV down, but nothing in the timeline can establish illness.",
               "Am I getting sick?",
               MemberTimeline(member_id="M002", records=_BASELINE + _TODAY["poor"]),
               RECOVERY_AS_OF, ["hrv", "resting_hr"], ["sick", "ill", "illness"]),
]
