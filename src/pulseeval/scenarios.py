"""Evaluation cases: a timeline, a question, an as-of time, and hand-labelled expectations.

Fixture data is synthetic and illustrative; values are not real measurements.
Expected values are written by hand, never computed by agent code.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from pulseeval.timeline import MemberTimeline, Record

SCENARIOS_VERSION = "0.2.0"


class _CaseBase(BaseModel):
    case_id: str
    description: str
    timeline: MemberTimeline
    question: str
    as_of: datetime


class StateCase(_CaseBase):
    """'What is the current X?' — evaluated for temporal consistency."""

    kind: Literal["current_state"] = "current_state"
    target_name: str  # record name the question is about
    expected_record_id: str  # current record at as_of
    expected_value: str


class NumericCase(_CaseBase):
    """Aggregate over a window — evaluated for numerical correctness."""

    kind: Literal["numeric"] = "numeric"
    expected_value: float
    unit: str
    tolerance: float  # absolute, in `unit`
    expected_record_ids: list[str]  # readings the computation should use


Case = StateCase | NumericCase


def _r(record_id, kind, name, value, event, recorded=None, unit=None) -> Record:
    event_time = datetime.fromisoformat(event)
    return Record(
        record_id=record_id, kind=kind, name=name, value=value, unit=unit,
        event_time=event_time,
        recorded_at=datetime.fromisoformat(recorded) if recorded else event_time,
        source="fixture",
    )


AS_OF = datetime(2026, 4, 1)

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
    return NumericCase(
        case_id=case_id, description=description,
        timeline=MemberTimeline(member_id="M001", records=_BASE + records),
        question=RHR_QUESTION, as_of=AS_OF,
        expected_value=expected, unit="bpm", tolerance=0.1, expected_record_ids=ids,
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
]
