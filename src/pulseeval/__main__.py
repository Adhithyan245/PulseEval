"""CLI: run the evaluation suite against an agent config and print a report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pulseeval.agent import AGENT_VERSION
from pulseeval.benchmark import AGENT_CONFIGS, render
from pulseeval.evaluation import run_suite
from pulseeval.external import answers_from_agent, evaluate_traces, export_cases
from pulseeval.phia import phia_cases
from pulseeval.scenarios import CASES, SCENARIOS_VERSION

AGENTS = AGENT_CONFIGS


def _print_report(agent_label: str, cases, results) -> None:
    print("PulseEval - Longitudinal Health Agent Evaluation")
    print(f"Agent: {agent_label} | Scenarios: v{SCENARIOS_VERSION}")
    print(f"Cases evaluated: {len(cases)}")
    for evaluator in dict.fromkeys(r.evaluator for r in results):
        group = [r for r in results if r.evaluator == evaluator]
        passed = sum(r.passed for r in group)
        print(f"{evaluator} (v{group[0].evaluator_version}): "
              f"{passed}/{len(group)} ({passed / len(group):.0%})")
    print()
    for case in cases:
        case_results = [r for r in results if r.case_id == case.case_id]
        verdicts = " ".join(f"{r.evaluator.split('_')[0]}={'PASS' if r.passed else 'FAIL'}"
                            for r in case_results)
        print(f"[{'PASS' if all(r.passed for r in case_results) else 'FAIL'}] "
              f"{case.case_id}  ({verdicts})")
        for r in case_results:
            for f in r.failures:
                print(f"    {f.failure_type.value} [{r.evaluator}/{f.check}] ({f.severity}): "
                      f"{f.actual_behavior}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="pulseeval")
    parser.add_argument("--agent", choices=AGENTS, default="reference")
    parser.add_argument("--json", action="store_true", help="print full results as JSON")
    parser.add_argument("--benchmark", action="store_true",
                        help="print the consolidated benchmark report (Markdown) and exit")
    parser.add_argument("--phia", metavar="DIR",
                        help="also run PHIA-derived cases from a local PHIA data directory")
    parser.add_argument("--export-cases", metavar="FILE",
                        help="write the blind case export (questions + timelines) and exit")
    parser.add_argument("--write-answers", metavar="FILE",
                        help="write --agent's answers in the external answers format and exit")
    parser.add_argument("--evaluate", metavar="FILE",
                        help="evaluate an external agent's answers file instead of --agent")
    args = parser.parse_args()

    if args.benchmark:
        print(render(), end="")
        return

    cases = CASES + (phia_cases(args.phia) if args.phia else [])

    if args.export_cases:
        Path(args.export_cases).write_text(json.dumps(export_cases(cases), indent=2),
                                           encoding="utf-8")
        print(f"Wrote {len(cases)} cases to {args.export_cases}")
        return
    if args.write_answers:
        payload = answers_from_agent(AGENTS[args.agent], args.agent, cases)
        Path(args.write_answers).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {len(cases)} answers from '{args.agent}' to {args.write_answers}")
        return

    if args.evaluate:
        payload = json.loads(Path(args.evaluate).read_text(encoding="utf-8"))
        name, results, unanswered = evaluate_traces(payload, cases)
        label = f"{name} (external)"
        answered = [c for c in cases if c.case_id not in unanswered]
    else:
        results = run_suite(AGENTS[args.agent], cases)
        label, answered, unanswered = f"{args.agent} (v{AGENT_VERSION})", cases, []

    if args.json:
        print(json.dumps([r.model_dump(mode="json") for r in results], indent=2))
        return
    _print_report(label, answered, results)
    if unanswered:
        print(f"\nUnanswered ({len(unanswered)}): {', '.join(unanswered)}")


if __name__ == "__main__":
    main()
