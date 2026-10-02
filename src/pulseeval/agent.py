"""System under test: a deliberately small, deterministic personal-health agent.

The agent exists so PulseEval has something concrete to evaluate. Its config
knobs inject known faults so evaluators can be checked against known-good and
known-bad behaviour.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel

from pulseeval.timeline import MemberTimeline, Record

AGENT_VERSION = "0.2.0"

Ordering = Literal["chronological", "input_order"]


class ToolCall(BaseModel):
    name: str
    inputs: dict
    outputs: list[str]  # record ids returned by the tool


class AgentTrace(BaseModel):
    agent_version: str
    agent_config: dict
    query: str
    member_id: str
    as_of: datetime
    time_window: tuple[datetime | None, datetime | None]
    retrieved_context: list[str]
    tools_called: list[ToolCall]
    memories_used: list[str] = []
    evidence_used: list[str]
    final_answer: str
    uncertainty: str | None = None
    abstention: bool


# --- tools -------------------------------------------------------------------

def retrieve_context(timeline: MemberTimeline, as_of: datetime, respect_as_of: bool) -> list[Record]:
    if respect_as_of:
        return timeline.known_as_of(as_of)
    return list(timeline.records)


def latest_value(records: list[Record], name: str, ordering: Ordering) -> Record | None:
    matches = [r for r in records if r.name == name]
    if not matches:
        return None
    if ordering == "chronological":
        return max(matches, key=lambda r: (r.event_time, r.recorded_at, r.record_id))
    return matches[-1]  # fault: trusts that input arrives sorted


def mean_value(records: list[Record], name: str, start: datetime | None,
               end: datetime) -> tuple[float | None, list[Record]]:
    used = [r for r in records if r.name == name and r.event_time <= end
            and (start is None or r.event_time >= start)]
    if not used:
        return None, []
    return sum(float(r.value) for r in used) / len(used), used


# --- agent -------------------------------------------------------------------

_METRICS = {"resting heart rate": "resting_hr"}


def _intent(question: str) -> tuple[str, str, int | None] | None:
    """(operation, record name, window days) for the few supported question shapes."""
    q = question.lower()
    if "goal" in q:
        return "current", "training_goal", None
    days = re.search(r"last (\d+) days", q)
    for phrase, name in _METRICS.items():
        if "average" in q and phrase in q and days:
            return "mean", name, int(days.group(1))
    return None


class HealthAgent:
    def __init__(self, ordering: Ordering = "chronological", respect_as_of: bool = True,
                 respect_window: bool = True):
        self.ordering = ordering
        self.respect_as_of = respect_as_of
        self.respect_window = respect_window  # fault when False: aggregates all history

    def answer(self, timeline: MemberTimeline, question: str, as_of: datetime) -> AgentTrace:
        tools: list[ToolCall] = []

        context = retrieve_context(timeline, as_of, self.respect_as_of)
        tools.append(ToolCall(
            name="retrieve_context",
            inputs={"as_of": as_of.isoformat(), "respect_as_of": self.respect_as_of},
            outputs=[r.record_id for r in context],
        ))

        intent = _intent(question)
        evidence: list[Record] = []
        final_answer = "I don't have data to answer that question."
        window: tuple[datetime | None, datetime | None] = (
            (None, as_of) if self.respect_as_of else (None, None))

        if intent and intent[0] == "current":
            record = latest_value(context, intent[1], self.ordering)
            tools.append(ToolCall(
                name="latest_value",
                inputs={"name": intent[1], "ordering": self.ordering},
                outputs=[record.record_id] if record else [],
            ))
            if record is not None:
                evidence = [record]
                final_answer = (f"Your current training goal is {record.value} "
                                f"(set {record.event_time:%Y-%m-%d}).")

        elif intent and intent[0] == "mean":
            _, name, days = intent
            start = as_of - timedelta(days=days) if self.respect_window else None
            window = (start, as_of)
            mean, used = mean_value(context, name, start, as_of)
            tools.append(ToolCall(
                name="mean_value",
                inputs={"name": name, "start": start.isoformat() if start else None,
                        "end": as_of.isoformat()},
                outputs=[r.record_id for r in used],
            ))
            if mean is not None:
                evidence = used
                final_answer = (f"Your average resting heart rate over the last {days} days "
                                f"was {mean:.1f} {used[0].unit} ({len(used)} readings).")

        return AgentTrace(
            agent_version=AGENT_VERSION,
            agent_config={"ordering": self.ordering, "respect_as_of": self.respect_as_of,
                          "respect_window": self.respect_window},
            query=question,
            member_id=timeline.member_id,
            as_of=as_of,
            time_window=window,
            retrieved_context=[r.record_id for r in context],
            tools_called=tools,
            evidence_used=[r.record_id for r in evidence],
            final_answer=final_answer,
            abstention=not evidence,
        )
