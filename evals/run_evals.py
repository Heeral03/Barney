"""Single entry point for the eval suite. Exits non-zero if any metric falls below its threshold.

    python -m evals.run_evals            # offline suite: no LLM, no network, deterministic
    python -m evals.run_evals --agent    # also score the requirements agent (calls Groq)
    python -m evals.run_evals --e2e      # also run the end-to-end task-completion eval (needs Postgres + GROQ_API_KEY)

Thresholds are regression gates set at the current baseline; raise them as the system improves.
Each entry is (metric path, comparison, bound).
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from evals import run_filters, run_requirements, run_reviewed

RESULTS = Path(__file__).parent / "results"

OFFLINE_GATES = [
    ("model_year_extraction.year_recall", ">=", 0.95),
    ("model_year_extraction.false_positive_rate", "<=", 0.0),
    ("curator_filters.recall", ">=", 0.95),
    ("curator_filters.good_kept_rate", ">=", 1.0),
    ("budget_parser.accuracy", ">=", 1.0),
    ("reviewed_feedback.regression_pass_rate", ">=", 1.0),
    ("reviewed_feedback.acceptable_kept_rate", ">=", 1.0),
]
AGENT_GATES = [
    ("requirements_agent.case_pass_rate", ">=", 0.75),
    ("requirements_agent.by_check.skip", ">=", 0.9),
    ("requirements_agent.by_check.plan_shape", ">=", 0.9),
    ("requirements_agent.by_check.budget_max", ">=", 0.9),
]
E2E_GATES = [
    ("task_completion_mean", ">=", 0.70),
    ("correct_pick_rate", ">=", 0.75),
    ("trap_pick_rate", "<=", 0.125),
    ("finished_within_turns_rate", ">=", 0.90),
]


def _get(data: dict, path: str):
    for key in path.split("."):
        data = data[key]
    return data


def check(data: dict, gates: list) -> list[dict]:
    rows = []
    for path, op, bound in gates:
        value = _get(data, path)
        ok = value is not None and (value >= bound if op == ">=" else value <= bound)
        rows.append({"metric": path, "value": value, "gate": f"{op} {bound}", "pass": ok})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", action="store_true", help="also score the requirements agent (LLM)")
    parser.add_argument("--e2e", action="store_true", help="also run the LLM-backed end-to-end eval")
    args = parser.parse_args()

    report = {"date": date.today().isoformat(), "suites": {}}
    offline = {"model_year_extraction": run_filters.year_eval(), "curator_filters": run_filters.filter_eval(),
               "budget_parser": run_requirements.budget_eval(), "reviewed_feedback": run_reviewed.reviewed_eval()}
    report["suites"]["offline"] = {"gates": check(offline, OFFLINE_GATES), "detail": offline}

    if args.agent:
        agent = run_requirements.main(repeat=1)
        report["suites"]["agent"] = {"gates": check(agent, AGENT_GATES), "detail": agent}

    if args.e2e:
        from evals import run_task_completion

        run_task_completion.main()
        e2e = json.loads((RESULTS / "task_completion.json").read_text())["summary"]
        report["suites"]["e2e"] = {"gates": check(e2e, E2E_GATES), "detail": e2e}

    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))

    failed = 0
    for name, suite in report["suites"].items():
        print(f"\n[{name}]")
        for g in suite["gates"]:
            failed += not g["pass"]
            print(f"  {'PASS' if g['pass'] else 'FAIL'}  {g['metric']:<46} {g['value']}  (gate {g['gate']})")
    print(f"\n{'FAILED' if failed else 'OK'}: {failed} gate(s) failed. Report: {RESULTS / 'report.json'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
