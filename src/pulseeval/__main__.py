"""CLI: run the evaluation suite against an agent config and print a report."""

from __future__ import annotations

import argparse
import json

from pulseeval.agent import AGENT_VERSION, HealthAgent
from pulseeval.evaluation import run_suite
from pulseeval.scenarios import CASES, SCENARIOS_VERSION

AGENTS = {
    "reference": HealthAgent(),
    "input_order": HealthAgent(ordering="input_order"),  # fault: assumes sorted input
    "no_as_of": HealthAgent(respect_as_of=False),  # fault: leaks future/late records
    "no_window": HealthAgent(respect_window=False),  # fault: aggregates all history
}


def main() -> None:
    parser = argparse.ArgumentParser(prog="pulseeval")
    parser.add_argument("--agent", choices=AGENTS, default="reference")
    parser.add_argument("--json", action="store_true", help="print full results as JSON")
    args = parser.parse_args()

    results = run_suite(AGENTS[args.agent], CASES)

    if args.json:
        print(json.dumps([r.model_dump(mode="json") for r in results], indent=2))
        return

    print("PulseEval - Longitudinal Health Agent Evaluation")
    print(f"Agent: {args.agent} (v{AGENT_VERSION}) | Scenarios: v{SCENARIOS_VERSION}")
    print(f"Cases evaluated: {len(results)}")
    for evaluator in dict.fromkeys(r.evaluator for r in results):
        group = [r for r in results if r.evaluator == evaluator]
        passed = sum(r.passed for r in group)
        print(f"{evaluator} (v{group[0].evaluator_version}): "
              f"{passed}/{len(group)} ({passed / len(group):.0%})")
    print()
    for r in results:
        print(f"[{'PASS' if r.passed else 'FAIL'}] {r.case_id}")
        for f in r.failures:
            print(f"    {f.failure_type.value} [{f.aspect}/{f.check}] ({f.severity}): "
                  f"{f.actual_behavior}")


if __name__ == "__main__":
    main()
