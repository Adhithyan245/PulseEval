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

AGENT_VERSION = "0.4.0"

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


def carry_forward(records: list[Record], name: str, start: datetime,
                  days: int) -> list[tuple[datetime, Record]]:
    """Fault tool: for each day in the window without a reading, reuse the latest earlier one."""
    readings = sorted((r for r in records if r.name == name), key=lambda r: r.event_time)
    filled = []
    for i in range(days):
        day = (start + timedelta(days=i)).date()
        if any(r.event_time.date() == day for r in readings):
            continue
        earlier = [r for r in readings if r.event_time.date() < day]
        if earlier:
            filled.append((datetime.combine(day, datetime.min.time()), earlier[-1]))
    return filled


# --- agent -------------------------------------------------------------------

_METRICS = {"resting heart rate": "resting_hr"}


# Synthetic self-report vocabulary (ADR-010) -> what it indicates about recovery.
_REPORT_DIRECTION = {"exhausted": "poor", "tired": "poor", "drained": "poor",
                     "rested": "good", "energetic": "good", "refreshed": "good"}


def _intent(question: str) -> tuple[str, str, int | None] | None:
    """(operation, record name, window days) for the few supported question shapes."""
    q = question.lower()
    if "goal" in q:
        return "current", "training_goal", None
    if "recover" in q:
        return "assess", "recovery", None
    days = re.search(r"last (\d+) days", q)
    for phrase, name in _METRICS.items():
        if "average" in q and phrase in q and days:
            return "mean", name, int(days.group(1))
    return None


class HealthAgent:
    def __init__(self, ordering: Ordering = "chronological", respect_as_of: bool = True,
                 respect_window: bool = True, report_coverage: bool = True,
                 impute_missing: bool = False, ignore_self_report: bool = False,
                 dismiss_self_report: bool = False):
        self.ordering = ordering
        self.respect_as_of = respect_as_of
        self.respect_window = respect_window  # fault when False: aggregates all history
        self.report_coverage = report_coverage  # fault when False: silent about gaps
        self.impute_missing = impute_missing  # fault when True: carries values into gaps
        self.ignore_self_report = ignore_self_report  # fault: wearable data only
        self.dismiss_self_report = dismiss_self_report  # fault: resolves conflicts for the data

    def _assess_recovery(self, context: list[Record], as_of: datetime,
                         tools: list[ToolCall]) -> tuple[list[Record], str]:
        """Today's HRV / resting HR vs the prior 7 days, plus the latest self-report."""
        day_start, base_start = as_of - timedelta(days=1), as_of - timedelta(days=8)
        today, baseline = {}, {}
        for name in ("hrv", "resting_hr"):
            readings = [r for r in context if r.name == name and r.event_time <= as_of]
            current = [r for r in readings if r.event_time >= day_start]
            today[name] = max(current, key=lambda r: r.event_time) if current else None
            baseline[name] = [r for r in readings if base_start <= r.event_time < day_start]
        tools.append(ToolCall(
            name="compare_to_baseline",
            inputs={"today_from": day_start.isoformat(), "baseline_from": base_start.isoformat()},
            outputs=[r.record_id for r in today.values() if r]
            + [r.record_id for rs in baseline.values() for r in rs],
        ))
        if not (today["hrv"] and today["resting_hr"] and all(baseline.values())):
            return [], "I don't have enough recent wearable data to assess your recovery."
        h, p = float(today["hrv"].value), float(today["resting_hr"].value)
        bh = sum(float(r.value) for r in baseline["hrv"]) / len(baseline["hrv"])
        bp = sum(float(r.value) for r in baseline["resting_hr"]) / len(baseline["resting_hr"])
        wearable = "good" if h > bh and p < bp else "poor" if h < bh and p > bp else "mixed"
        evidence = [today["hrv"], today["resting_hr"], *baseline["hrv"], *baseline["resting_hr"]]
        answer = (f"Your wearable data suggests "
                  f"{ {'good': 'good', 'poor': 'reduced', 'mixed': 'mixed'}[wearable]} recovery "
                  f"today (HRV {h:.0f} ms vs a 7-day average of {bh:.0f} ms; resting heart rate "
                  f"{p:.0f} bpm vs {bp:.0f} bpm).")

        report = None
        if not self.ignore_self_report:
            since = day_start if self.respect_window else None  # fault: any past report
            reports = [r for r in context if r.name == "energy_report" and r.event_time <= as_of
                       and (since is None or r.event_time >= since)]
            report = max(reports, key=lambda r: r.event_time) if reports else None
            tools.append(ToolCall(name="latest_self_report",
                                  inputs={"since": since.isoformat() if since else None},
                                  outputs=[report.record_id] if report else []))
        if report is None:
            return evidence, answer

        evidence.append(report)
        felt = _REPORT_DIRECTION.get(str(report.value))
        conflict = felt is not None and wearable != "mixed" and felt != wearable
        if conflict and self.dismiss_self_report:
            verdict = "well recovered" if wearable == "good" else "not well recovered"
            return evidence, (answer + f" You reported feeling {report.value}, but your data "
                              f"shows you are actually {verdict}.")
        answer += f" You reported feeling {report.value} this morning."
        if conflict:
            answer += (" These two signals conflict. Neither source alone gives a complete "
                       "picture, so it is worth weighing how you feel alongside the data.")
        elif felt == wearable:
            answer += " Your own report is consistent with the data."
        return evidence, answer

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

        elif intent and intent[0] == "assess":
            window = (as_of - timedelta(days=8), as_of)
            evidence, final_answer = self._assess_recovery(context, as_of, tools)

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
            covered = len({r.event_time.date() for r in used})
            if mean is not None and self.impute_missing and start is not None:
                filled = carry_forward(context, name, start, days)
                tools.append(ToolCall(
                    name="carry_forward",
                    inputs={"name": name, "dates": [d.date().isoformat() for d, _ in filled]},
                    outputs=[r.record_id for _, r in filled],
                ))
                values = [float(r.value) for r in used] + [float(r.value) for _, r in filled]
                mean, covered = sum(values) / len(values), covered + len(filled)
            if mean is not None:
                evidence = used
                coverage = ""
                if self.report_coverage:
                    coverage = (f" (all {days} days had data)" if covered >= days
                                else f" ({covered} of {days} days had data)")
                final_answer = (f"Your average resting heart rate over the last {days} days "
                                f"was {mean:.1f} {used[0].unit}{coverage}.")

        return AgentTrace(
            agent_version=AGENT_VERSION,
            agent_config={"ordering": self.ordering, "respect_as_of": self.respect_as_of,
                          "respect_window": self.respect_window,
                          "report_coverage": self.report_coverage,
                          "impute_missing": self.impute_missing,
                          "ignore_self_report": self.ignore_self_report,
                          "dismiss_self_report": self.dismiss_self_report},
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
