"""Scores the curator's filters against listings that a human reviewer labelled (evals/datasets/reviewed.jsonl).

    python -m evals.run_reviewed

Each case is one listing plus the shopper's request. The listing is placed among three ordinary current listings and run
through the curator's filter chain, so it is judged the way a real shortlist would judge it.
  should_exclude -> the filters must drop it           acceptable -> they must keep it
Cases flagged `"fixed": true` are regressions: once a failure is fixed it must stay fixed, and the gate enforces that.
Cases not yet fixed are the backlog: `open_gaps` lists what the filters still miss, which is where to work next.
Real feedback arrives through `python -m evals.review`; the `seed-*` rows are hand-written starters.
"""
import json
from datetime import date
from pathlib import Path

import tests.conftest  # noqa: F401
from evals.run_filters import _stage

DATASET = Path(__file__).parent / "datasets" / "reviewed.jsonl"
NOW, OLD = date.today().year, date.today().year - 4


def _fill(text: str) -> str:
    return text.replace("{NOW}", str(NOW)).replace("{OLD}", str(OLD))


def _listing(id: str, title: str) -> dict:
    return {"id": id, "title": title, "price_inr": 1600, "price_display": "₹1,600", "rating": 4.2, "rating_count": 500,
            "seller": "Amazon.in", "api": "google_shopping", "rank": 0}


def load(path: Path = DATASET) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def survives(case: dict) -> bool:
    product = case.get("product") or "item"
    fillers = [_listing(f"f{i}", f"Standard {product.title()} Model {chr(65 + i)} ({NOW})") for i in range(3)]
    scenario = {"id": product, "message": _fill(case.get("request") or product)}
    kept = {o["id"] for o in _stage([_listing("target", _fill(case["title"])), *fillers], scenario)}
    return "target" in kept


def reviewed_eval(path: Path = DATASET) -> dict:
    cases = load(path)
    bad = [c for c in cases if c["label"] == "should_exclude"]
    fine = [c for c in cases if c["label"] == "acceptable"]
    caught = {c["id"] for c in bad if not survives(c)}
    kept = {c["id"] for c in fine if survives(c)}
    fixed = [c for c in cases if c.get("fixed")]
    ok = lambda c: (c["id"] in caught) if c["label"] == "should_exclude" else (c["id"] in kept)
    return {
        "cases": len(cases), "from_real_feedback": sum(c.get("source") == "feedback" for c in cases),
        "should_exclude": len(bad), "caught": len(caught), "catch_rate": round(len(caught) / len(bad), 3) if bad else None,
        "acceptable": len(fine), "acceptable_kept_rate": round(len(kept) / len(fine), 3) if fine else None,
        "regression_cases": len(fixed), "regression_pass_rate": round(sum(map(ok, fixed)) / len(fixed), 3) if fixed else None,
        "regressions": [c["id"] for c in fixed if not ok(c)],
        "open_gaps": [{"id": c["id"], "title": _fill(c["title"]), "note": c.get("note", "")} for c in bad if c["id"] not in caught],
    }


if __name__ == "__main__":
    print(json.dumps(reviewed_eval(), indent=2, ensure_ascii=False))
