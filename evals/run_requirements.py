"""Evals for the requirements agent, the one LLM call that decides each turn.

    python -m evals.run_requirements              # budget parser (offline) + agent cases (calls Groq, ~1 call per case)
    python -m evals.run_requirements --offline    # budget parser only
    python -m evals.run_requirements --repeat 3   # run each case 3 times to expose flaky behaviour

Everything is scored against hand labels with code, no judge model:
  decision accuracy, product extraction, budget extraction, restart on product switch, skip detection, question-plan
  shape (4-6 attributes, 2+ options, no "other"), required facts, and search-query hygiene (no prices, years, hype words).
"""
import os

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

import argparse
import re
import time
from collections import defaultdict

from app.tools.products import parse_budget
from evals.requirements_cases import BUDGETS, CASES

HYGIENE = re.compile(r"(?i)(₹|\brs\b|\binr\b|\bunder\b|\bbelow\b|\blatest\b|\bnew model\b|\bgenuine\b|\boriginal\b|\bbest\b|\bcheap\b|\b20[1-3]\d\b)")


def budget_eval() -> dict:
    wrong = [{"text": t, "expected": list(w), "got": list(parse_budget(t))} for t, w in BUDGETS if parse_budget(t) != w]
    return {"cases": len(BUDGETS), "accuracy": round(1 - len(wrong) / len(BUDGETS), 3), "wrong": wrong}


def _run(case: dict) -> dict:
    import tests.conftest  # noqa: F401  (offline embedding model, as in the unit tests)
    from groq import RateLimitError
    from langchain_core.messages import HumanMessage

    from app.agents.requirements import requirements_node

    state = {"messages": [HumanMessage(content=case["message"])], **(case.get("state") or {})}
    for attempt in range(6):
        try:
            return requirements_node(state)
        except RateLimitError:
            time.sleep(20 + 15 * attempt)
    raise RuntimeError("Groq stayed rate limited")


def grade(case: dict, out: dict) -> dict[str, bool]:
    """One boolean per check that this case defines."""
    plan, profile = out.get("plan") or {}, out.get("profile") or {}
    checks: dict[str, bool] = {"decision": plan.get("decision") in case["decision"]}
    product = (profile.get("product") or plan.get("product") or "").lower()
    if "product" in case:
        checks["product"] = any(w in product for w in case["product"])
    if "keep_product" in case:
        checks["product_kept"] = any(w in product for w in case["keep_product"])
    for key in ("budget_max", "budget_min"):
        if key in case:
            checks[key] = (profile.get(key) if profile.get(key) is not None else plan.get(key)) == case[key]
    if "restart" in case:
        checks["restart"] = ("budget_max" not in profile and "gender" not in (profile.get("facts") or {})) == case["restart"]
    if "skip" in case:
        checks["skip"] = bool(profile.get("skip") or plan.get("skip")) == case["skip"]
    if "mode" in case:
        checks["mode"] = plan.get("mode") == case["mode"]
    if case.get("attrs"):
        attrs = profile.get("attrs") or []
        checks["plan_shape"] = 4 <= len(attrs) <= 6 and all(len(a["options"]) >= 2 and a["question"] for a in attrs)
        checks["plan_has_budget"] = any(a["topic"].lower().startswith("budget") for a in attrs)
    for topic, needle in (case.get("fact") or {}).items():
        facts = {**(profile.get("facts") or {}), **{f["topic"]: f["value"] for f in plan.get("facts") or []}}
        checks[f"fact:{topic}"] = any(topic in k.lower() and needle in str(v).lower() for k, v in facts.items())
    if "remember" in case:
        checks["remember"] = any(case["remember"] in m["text"].lower() for m in plan.get("remember") or [])
    queries = plan.get("queries") or []
    if plan.get("decision") == "search":
        checks["queries_clean"] = 1 <= len(queries) <= 3 and not any(HYGIENE.search(q) for q in queries)
        if "queries_contain" in case:
            checks["queries_contain"] = all(case["queries_contain"] in q.lower() for q in queries)
    return checks


def agent_eval(repeat: int = 1) -> dict:
    by_check: dict[str, list[bool]] = defaultdict(list)
    rows, failures = [], []
    for case in CASES:
        for run in range(repeat):
            try:
                out = _run(case)
                checks = grade(case, out)
                got = (out.get("plan") or {}).get("decision")
            except Exception as e:  # a crash is a failure of every check, not a skipped case
                checks, got = {"decision": False}, f"crash: {e!r}"[:120]
            for name, ok in checks.items():
                by_check[name.split(":")[0]].append(ok)
            rows.append({"case": case["id"], "run": run, "decision": got, "passed": all(checks.values()), "checks": checks})
            failures += [f"{case['id']}: {n} (decision={got})" for n, ok in checks.items() if not ok]
    n = len(rows)
    return {
        "cases": len(CASES), "runs": n,
        "case_pass_rate": round(sum(r["passed"] for r in rows) / n, 3),
        "by_check": {k: round(sum(v) / len(v), 3) for k, v in sorted(by_check.items())},
        "failures": failures, "rows": rows,
    }


def main(offline: bool = False, repeat: int = 1) -> dict:
    result = {"budget_parser": budget_eval()}
    if not offline:
        result["requirements_agent"] = agent_eval(repeat)
    return result


if __name__ == "__main__":
    import json
    from pathlib import Path

    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--repeat", type=int, default=1)
    a = ap.parse_args()
    res = main(a.offline, a.repeat)
    out = Path(__file__).parent / "results" / "requirements.json"
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    summary = {"budget_parser": {k: v for k, v in res["budget_parser"].items()}}
    if "requirements_agent" in res:
        summary["requirements_agent"] = {k: v for k, v in res["requirements_agent"].items() if k != "rows"}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
