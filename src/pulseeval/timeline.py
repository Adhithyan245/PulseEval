"""Canonical member timeline: typed, timestamped records with as-of semantics."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

RecordKind = Literal[
    "physiological", "activity", "sleep", "subjective", "context", "goal", "memory"
]


class Record(BaseModel):
    record_id: str
    kind: RecordKind
    name: str  # e.g. "resting_hr", "training_goal"
    value: float | str
    unit: str | None = None
    event_time: datetime  # when the fact happened / became true
    recorded_at: datetime  # when it entered the system (knowable from then on)
    source: str  # e.g. "wearable", "self_report", "fixture"
    confidence: float | None = None


class MemberTimeline(BaseModel):
    member_id: str
    records: list[Record]  # input order is not assumed to be meaningful

    def chronological(self) -> list[Record]:
        return sorted(self.records, key=lambda r: (r.event_time, r.recorded_at, r.record_id))

    def known_as_of(self, as_of: datetime) -> list[Record]:
        """Records the system could have known at `as_of`, in input order.

        Deliberately does not sort: ordering is the consumer's responsibility,
        and is part of what temporal evaluation tests.
        """
        return [r for r in self.records if r.recorded_at <= as_of]

    def get(self, record_id: str) -> Record | None:
        return next((r for r in self.records if r.record_id == record_id), None)
