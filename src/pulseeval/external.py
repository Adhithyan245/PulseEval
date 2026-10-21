"""External-agent interface (ADR-014): blind case export and evaluation of external answers.

Any agent (rule-based, LLM-based, human) can be benchmarked without touching the evaluators:

1. `export_cases()` -> JSON with each case's question, as-of time and full timeline, in the
   timeline's original order. Expected values, labels, descriptions and provenance are
   withheld, so the export is blind. As for the built-in agent, the timeline includes records
   that were not yet knowable at as-of (recorded later): using them is a temporal failure.
2. The agent answers each case, citing the `record_id`s it used.
3. `evaluate_traces(payload)` scores the answers with the same seven evaluators.
"""

from __future__ import annotations

from pydantic import BaseModel

from pulseeval.agent import AgentTrace, HealthAgent
from pulseeval.evaluation import EVALUATORS
from pulseeval.evaluation.schemas import EvaluationResult
from pulseeval.scenarios import CASES, Case

CASES_FORMAT = "pulseeval-cases/1"
ANSWERS_FORMAT = "pulseeval-answers/1"
INSTRUCTIONS = (
    "Answer each case's question as of its `as_of` time, using its records. Return a JSON "
    f"object {{\"format\": \"{ANSWERS_FORMAT}\", \"agent\": <name>, \"answers\": [...]}} with "
    "one entry per case: case_id, final_answer (text), evidence_used (record_ids you relied "
    "on), and optionally retrieved_context (record_ids you looked at; defaults to "
    "evidence_used) and abstention (true if you declined to answer)."
)


class ExternalAnswer(BaseModel):
    case_id: str
    final_answer: str
    evidence_used: list[str] = []
    retrieved_context: list[str] | None = None
    abstention: bool = False


class ExternalAnswers(BaseModel):
    format: str = ANSWERS_FORMAT
    agent: str
    answers: list[ExternalAnswer]


def export_cases(cases: list[Case] = CASES) -> dict:
    """Blind export: what an agent needs to answer, and nothing it could be graded against."""
    return {
        "format": CASES_FORMAT,
        "instructions": INSTRUCTIONS,
        "cases": [{
            "case_id": case.case_id,
            "question": case.question,
            "as_of": case.as_of.isoformat(),
            "member_id": case.timeline.member_id,
            "records": [r.model_dump(mode="json", include={
                "record_id", "kind", "name", "value", "unit", "event_time", "recorded_at"})
                for r in case.timeline.records],
        } for case in cases],
    }


def answers_from_agent(agent: HealthAgent, name: str, cases: list[Case] = CASES) -> dict:
    """The built-in agent's answers in the external format (a template and a round-trip check)."""
    answers = []
    for case in cases:
        trace = agent.answer(case.timeline, case.question, case.as_of)
        answers.append(ExternalAnswer(
            case_id=case.case_id, final_answer=trace.final_answer,
            evidence_used=trace.evidence_used, retrieved_context=trace.retrieved_context,
            abstention=trace.abstention))
    return ExternalAnswers(agent=name, answers=answers).model_dump(mode="json")


def evaluate_traces(payload: dict, cases: list[Case] = CASES
                    ) -> tuple[str, list[EvaluationResult], list[str]]:
    """Score external answers. Returns (agent name, results, ids of unanswered cases)."""
    submission = ExternalAnswers.model_validate(payload)
    if submission.format != ANSWERS_FORMAT:
        raise ValueError(f"unsupported answers format {submission.format!r}")
    by_id = {c.case_id: c for c in cases}
    seen: set[str] = set()
    results: list[EvaluationResult] = []
    for answer in submission.answers:
        if answer.case_id not in by_id:
            raise ValueError(f"unknown case_id {answer.case_id!r}")
        if answer.case_id in seen:
            raise ValueError(f"duplicate answer for case_id {answer.case_id!r}")
        seen.add(answer.case_id)
        case = by_id[answer.case_id]
        trace = AgentTrace(
            agent_version="external", agent_config={"agent": submission.agent,
                                                    "source": "external"},
            query=case.question, member_id=case.timeline.member_id, as_of=case.as_of,
            time_window=(None, None),
            retrieved_context=(answer.retrieved_context if answer.retrieved_context is not None
                               else answer.evidence_used),
            tools_called=[], evidence_used=answer.evidence_used,
            final_answer=answer.final_answer, abstention=answer.abstention)
        results += [r for r in (evaluate(case, trace) for evaluate in EVALUATORS)
                    if r is not None]
    unanswered = [c.case_id for c in cases if c.case_id not in seen]
    return submission.agent, results, unanswered
