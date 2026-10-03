"""Phase 3 benchmark (ADR-013): every agent configuration over the synthetic cases.

`render()` returns a deterministic Markdown report: applicability and pass/fail per dimension,
fault intent vs. observed failures, independence and co-failure matrices, intentional overlaps,
failure analysis built from live evaluator output, and the per-case failure grid. The committed
BENCHMARK.md must equal `render()` (tests/test_benchmark.py). PHIA cases are excluded so the
report reproduces without the locally stored, non-redistributable PHIA data.
"""

from __future__ import annotations

from collections import Counter

from pulseeval.agent import AGENT_VERSION, HealthAgent
from pulseeval.evaluation import EVALUATORS
from pulseeval.evaluation.schemas import EvaluationResult
from pulseeval.scenarios import CASES, SCENARIOS_VERSION, Case

AGENT_CONFIGS: dict[str, HealthAgent] = {
    "reference": HealthAgent(),
    "input_order": HealthAgent(ordering="input_order"),  # fault: assumes sorted input
    "no_as_of": HealthAgent(respect_as_of=False),  # fault: leaks future/late records
    "no_window": HealthAgent(respect_window=False),  # fault: aggregates all history
    "silent_gaps": HealthAgent(report_coverage=False),  # fault: never mentions missing days
    "impute": HealthAgent(impute_missing=True),  # fault: carries values into missing days
    "ignore_self_report": HealthAgent(ignore_self_report=True),  # fault: wearable data only
    "dismiss_self_report": HealthAgent(dismiss_self_report=True),  # fault: data overrides report
    "causal_overclaim": HealthAgent(causal_overclaim=True),  # fault: association stated as cause
    "overconfident": HealthAgent(overconfident=True),  # fault: definitive despite thin evidence
    "false_abstention": HealthAgent(false_abstention=True),  # fault: refuses supported answers
}

DIMENSIONS = [  # (evaluator name, abbreviation)
    ("temporal_consistency", "T"), ("evidence_grounding", "G"), ("answer_correctness", "A"),
    ("missing_data", "M"), ("contradiction_handling", "C"), ("causal_restraint", "K"),
    ("uncertainty_abstention", "U"),
]
ABBR = dict(DIMENSIONS)
T, G, A, M, C, K, U = (name for name, _ in DIMENSIONS)

# Fault model: the dimensions a fault is designed to trigger, and the knock-on dimensions it is
# allowed to trigger, each with the reason. Anything else observed is a fault-model violation.
FAULT_INTENT: dict[str, tuple[set[str], dict[str, str]]] = {
    "input_order": ({G, A}, {}),
    "no_as_of": ({T}, {G: "the leaked record replaces the current one",
                       A: "the leaked record changes the value",
                       M: "the leaked reading is counted toward coverage",
                       C: "the unknowable self-report creates an invented conflict"}),
    "no_window": ({G}, {A: "out-of-window readings change the mean",
                        M: "all-history coverage is reported as a complete window",
                        C: "a stale self-report creates an invented conflict",
                        U: "all-history data hides thin coverage, so the caveat is dropped"}),
    "silent_gaps": ({M}, {}),
    "impute": ({M}, {G: "carried values no longer match the cited readings",
                     A: "carried values move the mean outside tolerance",
                     U: "an imputed 'full' window drops the uncertainty caveat"}),
    "ignore_self_report": ({G, C}, {}),
    "dismiss_self_report": ({C}, {U: "intentional overlap: definitive resolution of a real "
                                     "conflict is also unjustified certainty"}),
    "causal_overclaim": ({K}, {}),
    "overconfident": ({U}, {C: "intentional overlap: definitive resolution of a real conflict "
                               "is also a contradiction-handling failure"}),
    "false_abstention": ({U}, {A: "a refusal reports no value",
                               M: "a refusal omits the coverage statement",
                               C: "a refusal omits the conflict statement"}),
}

# Every co-failing pair must be explained (tests/test_benchmark.py). "intentional overlap": two
# dimensions judge the same act; "shared root cause": one fault breaks two distinct properties.
OVERLAPS: dict[frozenset, tuple[str, str]] = {
    frozenset({C, U}): ("intentional overlap",
                        "Resolving a genuine wearable/self-report conflict definitively "
                        "misrepresents the conflict and claims unjustified certainty."),
    frozenset({G, A}): ("shared root cause",
                        "A wrong (stale, unknowable, out-of-window) record is cited and its "
                        "value reported: grounding judges the evidence, answer the text."),
    frozenset({A, M}): ("shared root cause",
                        "A refusal or an imputed window leaves both the value and the coverage "
                        "statement wrong."),
    frozenset({G, M}): ("shared root cause",
                        "Out-of-window or carried-forward readings break the citations and the "
                        "coverage statement together."),
    frozenset({A, U}): ("shared root cause",
                        "Refusing a supported numeric question reports no value and is an "
                        "unnecessary abstention."),
    frozenset({G, C}): ("shared root cause",
                        "The self-report is neither cited nor represented in the answer."),
    frozenset({M, U}): ("shared root cause",
                        "A thin or imputed window treated as complete drops both the coverage "
                        "statement and the uncertainty caveat."),
    frozenset({T, A}): ("shared root cause", "An unknowable record changes the value."),
    frozenset({G, U}): ("shared root cause",
                        "All-history readings fall outside the window and hide thin coverage."),
    frozenset({T, G}): ("shared root cause",
                        "A cited future record is unknowable and replaces the current record."),
    frozenset({T, C}): ("shared root cause",
                        "An unknowable self-report creates an invented conflict."),
    frozenset({T, M}): ("shared root cause",
                        "An unknowable reading is counted toward coverage."),
}


def _evaluate(case: Case, trace) -> dict[str, EvaluationResult]:
    results = (evaluate(case, trace) for evaluate in EVALUATORS)
    return {r.evaluator: r for r in results if r is not None}


def run_all(cases: list[Case] = CASES) -> dict[str, dict[str, dict[str, EvaluationResult]]]:
    """agent -> case_id -> evaluator -> result."""
    return {name: {c.case_id: _evaluate(c, agent.answer(c.timeline, c.question, c.as_of))
                   for c in cases}
            for name, agent in AGENT_CONFIGS.items()}


def failing(results: dict[str, EvaluationResult]) -> set[str]:
    return {name for name, r in results.items() if not r.passed}


def curated_witnesses() -> list[tuple[str, str, dict[str, EvaluationResult]]]:
    """Trace-level witnesses for independence that no agent fault produces on its own."""
    case = next(c for c in CASES if c.case_id == "goal_future_record")
    trace = HealthAgent().answer(case.timeline, case.question, case.as_of)
    leaked = trace.model_copy(update={"retrieved_context": trace.retrieved_context + ["g3"]})
    return [(T, "goal_future_record: reference trace that also retrieves (but does not cite) "
                "the future record g3", _evaluate(case, leaked))]


def fault_matrix(runs) -> dict[str, dict[str, str]]:
    """agent -> dimension -> 'intended' | 'secondary' | 'MISSING' | 'UNEXPECTED'."""
    out = {}
    for agent, (intended, secondary) in FAULT_INTENT.items():
        observed = set().union(*(failing(r) for r in runs[agent].values()))
        row = {}
        for dim, _ in DIMENSIONS:
            if dim in intended:
                row[dim] = "intended" if dim in observed else "MISSING"
            elif dim in observed:
                row[dim] = "secondary" if dim in secondary else "UNEXPECTED"
        out[agent] = row
    return out


def independence(runs) -> dict[str, dict]:
    """Per dimension: sole-failure witnesses and pass-while-another-fails witnesses."""
    rows = [(agent, case_id, res) for agent, by_case in runs.items()
            for case_id, res in by_case.items()]
    out = {}
    for dim, _ in DIMENSIONS:
        sole = [(a, c) for a, c, r in rows if failing(r) == {dim}]
        curated = [label for d, label, r in curated_witnesses() if d == dim and failing(r) == {dim}]
        passes = [(a, c) for a, c, r in rows if dim in r and r[dim].passed and failing(r)]
        out[dim] = {"sole": sole, "curated": curated, "passes_while_other_fails": passes}
    return out


def co_failures(runs) -> Counter:
    pairs: Counter = Counter()
    for by_case in runs.values():
        for res in by_case.values():
            dims = sorted(failing(res), key=list(ABBR).index)
            pairs.update((x, y) for i, x in enumerate(dims) for y in dims[i + 1:])
    return pairs


# Representative failures, including overlaps and a limitation; text comes from live results.
ANALYSIS = [
    ("causal_overclaim", "relation_association_only", K,
     "The agent cites the right paired records and reports the right group means, then states "
     "the association as causation. Only causal restraint can see this: the labels say "
     "association only, and nothing else about the answer is wrong."),
    ("overconfident", "unc_sparse_rhr_7d", U,
     "Two of seven days are available. The answer is correctly computed, grounded and states "
     "'2 of 7 days had data', but then calls the result 'definitely your true average'. Every "
     "other dimension passes; the certainty level is the only defect."),
    ("impute", "rhr_gap_first_day", M,
     "The agent fills the missing first day with an older reading and claims full coverage. "
     "The mean stays within tolerance and the cited readings still support it, so only "
     "missing-data handling fails."),
    ("no_as_of", "rhr_mean_7d_late_sync", T,
     "A reading recorded after the question time is used. Temporal consistency catches the "
     "leak; answer correctness (wrong mean) and missing-data (claims 7 of 7 knowable days) fail "
     "as consequences. Grounding passes: the reading is relevant and inside the window."),
    ("dismiss_self_report", "recovery_conflict_good_data_exhausted", C,
     "Both sources are cited (grounding passes), but the self-report is waved away "
     "('actually well recovered'). Contradiction handling is the only dimension that judges "
     "how a source conflict is represented."),
    ("overconfident", "unc_conflict_recovery", C,
     "Intentional overlap: the conflict is flagged but then resolved definitively. This fails "
     "contradiction handling (unsupported resolution) and uncertainty (unjustified certainty)."),
    ("input_order", "goal_three_updates_shuffled", G,
     "Records arrive out of order and the agent takes the last one listed. The stale goal is "
     "cited and asserted, so grounding and answer correctness fail. Temporal consistency passes: "
     "it checks knowability at the question time, not ordering - a deliberate scope boundary."),
    ("false_abstention", "unc_direct_recovery_agree", U,
     "The reverse direction: the evidence supports a direct answer, the agent gathers it and "
     "then refuses. Only uncertainty/abstention fails (answer correctness does not apply)."),
]


def _md_table(header: list[str], rows: list[list[str]]) -> list[str]:
    return (["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
            + ["| " + " | ".join(row) + " |" for row in rows])


def render(cases: list[Case] = CASES) -> str:
    runs = run_all(cases)
    reference = runs["reference"]
    lines = ["# PulseEval Benchmark Report", "",
             "Generated by `python -m pulseeval --benchmark` (do not edit by hand). "
             "Synthetic cases only; PHIA-derived cases are excluded so the report reproduces "
             "without the PHIA data. PulseEval evaluates agent behaviour: it does not establish "
             "clinical truth, estimate clinical risk, perform causal inference, or give medical "
             "advice.", "",
             f"- Cases: {len(cases)} ({', '.join(f'{k} {v}' for k, v in sorted(Counter(c.kind for c in cases).items()))})",
             f"- Agent configurations: {len(AGENT_CONFIGS)} (reference + {len(AGENT_CONFIGS) - 1} faults)",
             f"- Agent v{AGENT_VERSION}, scenarios v{SCENARIOS_VERSION}", ""]

    lines += ["## Dimensions", "",
              "Applicability is per case (ADR-009): a dimension that does not apply returns no "
              "result and is not counted. Pass/fail is for the reference agent; the fault "
              "columns count failing (agent, case) pairs across the 10 faults.", ""]
    rows = []
    for dim, abbr in DIMENSIONS:
        applicable = [c for c in reference.values() if dim in c]
        version = applicable[0][dim].evaluator_version if applicable else "-"
        fails = sum(1 for agent, by_case in runs.items() if agent != "reference"
                    for res in by_case.values() if dim in res and not res[dim].passed)
        rows.append([f"{dim} ({abbr})", version, str(len(applicable)),
                     str(len(cases) - len(applicable)),
                     str(sum(r[dim].passed for r in applicable)),
                     str(sum(not r[dim].passed for r in applicable)), str(fails)])
    lines += _md_table(["dimension", "version", "applicable", "N/A", "reference pass",
                        "reference fail", "fault failures"], rows) + [""]

    lines += ["## Fault model: intended vs. observed", "",
              "**intended** = designed to fail and does; **secondary** = an explained knock-on "
              "failure; **MISSING** / **UNEXPECTED** would be fault-model violations.", ""]
    matrix = fault_matrix(runs)
    lines += _md_table(["fault"] + [abbr for _, abbr in DIMENSIONS],
                       [[agent] + [matrix[agent].get(dim, "") for dim, _ in DIMENSIONS]
                        for agent in FAULT_INTENT]) + [""]
    for agent, (_, secondary) in FAULT_INTENT.items():
        for dim, why in secondary.items():
            if matrix[agent].get(dim) == "secondary":
                lines.append(f"- `{agent}` -> {ABBR[dim]}: {why}")
    lines.append("")

    lines += ["## Independence", "",
              "For each dimension: (agent, case) pairs where it is the *only* failing dimension, "
              "and pairs where it passes while another applicable dimension fails.", ""]
    ind = independence(runs)
    rows = []
    for dim, abbr in DIMENSIONS:
        sole, curated, passes = ind[dim]["sole"], ind[dim]["curated"], ind[dim]["passes_while_other_fails"]
        example = (f"`{sole[0][0]}` / `{sole[0][1]}`" if sole
                   else f"curated: {curated[0]}" if curated else "none")
        rows.append([abbr, str(len(sole)), example, str(len(passes)),
                     f"`{passes[0][0]}` / `{passes[0][1]}`" if passes else "none"])
    lines += _md_table(["dim", "sole failures", "example", "passes while another fails",
                        "example"], rows) + [""]

    lines += ["## Co-failures and intentional overlaps", "",
              "Every pair of dimensions that fails together on some (agent, case) is listed "
              "with its explanation.", ""]
    pairs = co_failures(runs)
    lines += _md_table(["pair", "co-failing (agent, case) pairs", "type", "explanation"],
                       [[f"{ABBR[x]}+{ABBR[y]}", str(n),
                         *OVERLAPS.get(frozenset({x, y}), ("UNEXPLAINED", ""))]
                        for (x, y), n in sorted(pairs.items(),
                                                key=lambda kv: (-kv[1], kv[0]))]) + [""]

    lines += ["## Failure analysis", ""]
    for agent, case_id, dim, why in ANALYSIS:
        res = runs[agent][case_id]
        verdicts = ", ".join(f"{ABBR[d]}={'PASS' if r.passed else 'FAIL'}" for d, r in res.items())
        lines += [f"### `{agent}` on `{case_id}`", "", f"Results: {verdicts}", "", why, ""]
        for d, r in res.items():
            for f in r.failures:
                lines.append(f"- {f.failure_type.value} `{d}/{f.check}`: {f.actual_behavior[:220]}")
        lines.append("")

    lines += ["## Per-case failing dimensions", "",
              "Letters are failing dimensions; `.` = all applicable dimensions pass.", ""]
    lines += _md_table(["case"] + list(AGENT_CONFIGS),
                       [[f"`{c.case_id}`"] + ["".join(ABBR[d] for d, _ in DIMENSIONS
                                                      if d in failing(runs[a][c.case_id])) or "."
                                              for a in AGENT_CONFIGS] for c in cases])
    return "\n".join(lines) + "\n"
