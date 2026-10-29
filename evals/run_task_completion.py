"""Does Barney finish the shopper's job? DeepEval's TaskCompletionMetric over the real LangGraph agent.

Run:  .venv/bin/python -m evals.run_task_completion            (needs Postgres and GROQ_API_KEY; no search credits)

The graph runs for real (requirements agent, supervisor, parallel workers, curator, presenter, all on Groq). Only the
search API is replaced by the fixed catalogs in scenarios.py. Each conversation is one traced agent run
(@observe, see the DeepEval "LLM tracing" docs); the search is a `tool` span, so the judge sees every listing Barney
could have chosen, not only the one it did. TaskCompletionMetric infers the task from the shopper's message and scores
how well the outcome fulfils it. On top of the judge, three checks that need no judge (pick correctness, trap
avoidance, and finishing in <= MAX_TURNS) are computed against the hand labels.
"""
import os

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")  # no usage data leaves the machine

import json
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import tests.conftest  # noqa: F401  (swaps the embedding model for a fast offline one, like the unit tests)
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.evaluate.configs import AsyncConfig, DisplayConfig
from deepeval.metrics import TaskCompletionMetric
from deepeval.test_run.test_run import global_test_run_manager
from deepeval.tracing import observe, update_current_trace
from groq import RateLimitError
from langchain_core.messages import HumanMessage

import app.agents.presenter as presenter
import app.agents.researcher as researcher
import app.sources.serpapi as serpapi
from app.commands import SKIP
from app.graph import chatbot, checkpointer
from app.memory import store as ltm_store
from evals.judge import JUDGE_MODEL, GroqJudge
from evals.scenarios import SCENARIOS

MAX_TURNS = 3
PAUSE = 12  # seconds between scenarios, to stay inside Groq's per-minute token limit
THRESHOLD = 0.7
RESULTS = Path(__file__).parent / "results"
BY_MESSAGE = {s["message"]: s for s in SCENARIOS}
RUNS: dict[str, dict] = {}  # message -> what the deterministic checks saw


PAID_CALLS: list[str] = []


def _block_paid_apis():
    """No SerpAPI credit is ever spent here: the fixed catalog is the only search. Any attempt is counted and refused."""
    def refuse(*a, **k):
        PAID_CALLS.append(repr(a)[:80])
        raise RuntimeError("paid search blocked in evals")

    serpapi.available = lambda: False
    serpapi.searches_left = lambda: None
    serpapi.search_shopping = refuse


def _install_catalog(scenario: dict):
    """Search returns this scenario's listings for any query, as a traced tool call."""
    @observe(type="tool", name="search_listings")
    def shopping(query: str) -> list[dict]:
        return [{**{k: v for k, v in o.items() if k != "id"}, "price_display": f"₹{o['price_inr']:,}", "api": "google_shopping", "rank": i}
                for i, o in enumerate(scenario["catalog"])]

    researcher.shopping_offers = shopping
    researcher.web_offers = lambda q: []
    researcher.tavily_search = lambda q: []
    presenter.find_media_many = lambda items: [{"link": f"https://shop.example/{i}", "image_url": ""} for i, _ in enumerate(items)]


def _invoke(state: dict, cfg: dict) -> dict:
    """One graph turn. Groq's free tier limits tokens per minute; wait it out rather than count it against Barney."""
    for attempt in range(6):
        try:
            return chatbot.invoke(state, config=cfg)
        except RateLimitError:
            time.sleep(20 + 15 * attempt)
    raise RuntimeError("Groq stayed rate limited")


def _answers(form: dict, persona: list[str]) -> dict[str, list[str]]:
    """Fill the questionnaire like the persona would: tap options that mention what they care about, else the first."""
    out = {}
    for q in form["questions"]:
        hits = [o for o in q["options"] if any(k in o.lower() for k in persona)]
        pick = hits[:2] or q["options"][:1]
        if pick:
            out[q["topic"]] = pick
    return out


@observe(name="barney_agent")
def barney(message: str) -> str:
    scenario = BY_MESSAGE[message]
    _install_catalog(scenario)
    thread, user = f"eval-{uuid.uuid4().hex[:8]}", f"eval-{uuid.uuid4().hex[:8]}"
    cfg = {"configurable": {"thread_id": thread, "user_id": user}, "recursion_limit": 40}
    started, turns, said, answers = time.monotonic(), 0, message, {}
    pick, reply, out = None, "", {}
    try:
        while turns < MAX_TURNS:
            turns += 1
            out = _invoke({"messages": [HumanMessage(content=said)], "answers": answers, "form": None}, cfg)
            reply = str(out["messages"][-1].content)
            best = next((c for c in out.get("cards") or [] if c.get("best")), None)
            if best:
                pick = next((o["id"] for o in scenario["catalog"] if o["title"] == best["title"]), None)
                break
            if out.get("form"):
                answers = _answers(out["form"], scenario["persona"])
                said = "; ".join(f"{t}: {', '.join(v)}" for t, v in answers.items()) or SKIP
            else:
                said, answers = (out.get("options") or [SKIP])[0], {}
    finally:
        checkpointer.delete_thread(thread)
        for m in ltm_store.all_memories(ltm_store.ltm, user):
            ltm_store.forget(ltm_store.ltm, user, m["key"])
    RUNS[message] = {"id": scenario["id"], "turns": turns, "pick": pick, "finished": pick is not None or bool(best),
                     "seconds": round(time.monotonic() - started, 1)}
    chosen = next((o for o in scenario["catalog"] if o["id"] == pick), None)
    outcome = f"Barney recommended: {chosen['title']} at ₹{chosen['price_inr']:,}" if chosen else "Barney did not recommend a product."
    final = f"{outcome}\n\nBarney's message to the shopper:\n{reply}"
    update_current_trace(input=message, output=final)
    return final


def main():
    _block_paid_apis()
    judge = GroqJudge()
    metric = TaskCompletionMetric(threshold=THRESHOLD, model=judge, include_reason=True)
    dataset = EvaluationDataset(goldens=[Golden(input=s["message"]) for s in SCENARIOS])
    for golden in dataset.evals_iterator(
        metrics=[metric], async_config=AsyncConfig(run_async=False), display_config=DisplayConfig(print_results=False, show_indicator=False)
    ):
        try:
            barney(golden.input)
        except Exception as e:  # a crashed run is a failure, not a silent skip
            RUNS.setdefault(golden.input, {"id": BY_MESSAGE[golden.input]["id"], "error": repr(e)[:300], "finished": False})
            update_current_trace(input=golden.input, output=f"Barney crashed: {e!r}"[:300])
        time.sleep(PAUSE)

    scored = {}
    for tc in global_test_run_manager.get_test_run().test_cases:
        for md in tc.metrics_data or []:
            scored[tc.input] = {"score": md.score, "success": md.success, "reason": md.reason}

    rows = []
    for s in SCENARIOS:
        run, sc = RUNS.get(s["message"], {}), scored.get(s["message"], {})
        rows.append({
            "scenario": s["id"], **run, "pick_correct": run.get("pick") in s["ok"], "picked_trap": run.get("pick") in s["trap"],
            "task_completion": sc.get("score"), "judge_pass": sc.get("success"), "judge_reason": sc.get("reason"),
        })

    n = len(rows)
    scores = [r["task_completion"] for r in rows if r["task_completion"] is not None]
    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scenarios": n, "paid_search_calls": len(PAID_CALLS), "judge_model": JUDGE_MODEL, "threshold": THRESHOLD, "deepeval": __import__("deepeval").__version__,
        "task_completion_mean": round(statistics.mean(scores), 3) if scores else None,
        "task_completion_pass_rate": round(sum(1 for r in rows if r["judge_pass"]) / n, 3),
        "correct_pick_rate": round(sum(r["pick_correct"] for r in rows) / n, 3),
        "trap_pick_rate": round(sum(r["picked_trap"] for r in rows) / n, 3),
        "finished_within_turns_rate": round(sum(bool(r.get("finished")) for r in rows) / n, 3),
        "median_seconds_to_pick": statistics.median([r["seconds"] for r in rows if "seconds" in r] or [0]),
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "task_completion.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2))
    for r in rows:
        print(f"{r['scenario']:<24} pick={r.get('pick')!s:<5} ok={r['pick_correct']!s:<5} trap={r['picked_trap']!s:<5} "
              f"tc={r['task_completion']} turns={r.get('turns')} {r.get('error', '')}")


if __name__ == "__main__":
    main()
