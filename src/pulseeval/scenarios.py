"""Evaluation cases: a timeline, a question, an as-of time, and hand-labelled expectations.

Fixture data is synthetic and illustrative; values are not real measurements.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from pulseeval.timeline import MemberTimeline, Record

SCENARIOS_VERSION = "0.1.0"


class Case(BaseModel):
    case_id: str
    description: str
    timeline: MemberTimeline
    question: str
    as_of: datetime
    target_name: str  # record name the question is about
    expected_record_id: str  # hand-labelled current record at as_of
    expected_value: str


def _r(record_id, kind, name, value, event, recorded=None, unit=None) -> Record:
    event_time = datetime.fromisoformat(event)
    return Record(
        record_id=record_id, kind=kind, name=name, value=value, unit=unit,
        event_time=event_time,
        recorded_at=datetime.fromisoformat(recorded) if recorded else event_time,
        source="fixture",
    )


AS_OF = datetime(2026, 4, 1)
QUESTION = "What is my current training goal?"

_BASE = [
    _r("g1", "goal", "training_goal", "marathon training", "2026-01-05"),
    _r("o1", "physiological", "resting_hr", 52.0, "2026-02-01", unit="bpm"),
    _r("o2", "sleep", "sleep_duration", 7.4, "2026-02-01", unit="h"),
    _r("g2", "goal", "training_goal", "weight training", "2026-03-10"),
    _r("o3", "physiological", "resting_hr", 55.0, "2026-03-15", unit="bpm"),
]


def _case(case_id: str, description: str, records: list[Record]) -> Case:
    return Case(
        case_id=case_id, description=description,
        timeline=MemberTimeline(member_id="M001", records=records),
        question=QUESTION, as_of=AS_OF, target_name="training_goal",
        expected_record_id="g2", expected_value="weight training",
    )


CASES: list[Case] = [
    _case("goal_update_chronological",
          "Goal changes marathon -> weight training; records in chronological order.",
          list(_BASE)),
    _case("goal_update_reversed",
          "Same goal change, records delivered in reverse order (temporal reversal).",
          list(reversed(_BASE))),
    _case("goal_future_record",
          "A later goal (recorded after as_of) exists and must not be used.",
          _BASE + [_r("g3", "goal", "training_goal", "half marathon", "2026-05-01")]),
    _case("goal_late_arriving_record",
          "A goal change before as_of that was only recorded after as_of is not yet knowable.",
          _BASE + [_r("g4", "goal", "training_goal", "rest and recovery",
                      "2026-03-25", recorded="2026-04-10")]),
]
