"""Evaluation cases: a timeline, a question, an as-of time, and hand-labelled expectations.

Fixture data is synthetic and illustrative; values are not real measurements.
Expected values are written by hand, never computed by agent code.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel

from pulseeval.timeline import MemberTimeline, Record

SCENARIOS_VERSION = "0.5.0"


class _CaseBase(BaseModel):
    case_id: str
    description: str
    timeline: MemberTimeline
    question: str
    as_of: datetime
    target_name: str  # record name the question is about
    provenance: str  # where the expected values come from


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
    wearable_indicates: Direction
    self_report_indicates: Direction | None  # None: no knowable current self-report
    relevant_names: list[str]  # record names that are legitimate evidence

    @property
    def conflict(self) -> bool:
        return (self.self_report_indicates is not None
                and self.self_report_indicates != self.wearable_indicates)


Case = StateCase | NumericCase | AssessmentCase


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
}


def _report(value: str, event: str = "2026-04-15T07:30", recorded: str | None = None,
            record_id: str = "e0415") -> Record:
    return _r(record_id, "subjective", "energy_report", value, event, recorded=recorded)


def _recovery_case(case_id: str, description: str, wearable: Direction, extra: list[Record],
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
