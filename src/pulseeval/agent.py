"""System under test: a deliberately small, deterministic personal-health agent.

The agent exists so PulseEval has something concrete to evaluate. Its config
knobs inject known faults so evaluators can be checked against known-good and
known-bad behaviour.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from pulseeval.timeline import MemberTimeline, Record

AGENT_VERSION = "0.1.0"

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


# --- agent -------------------------------------------------------------------

def _intent(question: str) -> str | None:
    return "training_goal" if "goal" in question.lower() else None


class HealthAgent:
    def __init__(self, ordering: Ordering = "chronological", respect_as_of: bool = True):
        self.ordering = ordering
        self.respect_as_of = respect_as_of

    def answer(self, timeline: MemberTimeline, question: str, as_of: datetime) -> AgentTrace:
        tools: list[ToolCall] = []

        context = retrieve_context(timeline, as_of, self.respect_as_of)
        tools.append(ToolCall(
            name="retrieve_context",
            inputs={"as_of": as_of.isoformat(), "respect_as_of": self.respect_as_of},
            outputs=[r.record_id for r in context],
        ))

        target = _intent(question)
        record = None
        if target is not None:
            record = latest_value(context, target, self.ordering)
            tools.append(ToolCall(
                name="latest_value",
                inputs={"name": target, "ordering": self.ordering},
                outputs=[record.record_id] if record else [],
            ))

        if record is None:
            final_answer = "I don't have data to answer that question."
        else:
            final_answer = (
                f"Your current training goal is {record.value} "
                f"(set {record.event_time:%Y-%m-%d})."
            )

        return AgentTrace(
            agent_version=AGENT_VERSION,
            agent_config={"ordering": self.ordering, "respect_as_of": self.respect_as_of},
            query=question,
            member_id=timeline.member_id,
            as_of=as_of,
            time_window=(None, as_of) if self.respect_as_of else (None, None),
            retrieved_context=[r.record_id for r in context],
            tools_called=tools,
            evidence_used=[record.record_id] if record else [],
            final_answer=final_answer,
            abstention=record is None,
        )
