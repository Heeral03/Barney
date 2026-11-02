"""Human review of shopper feedback, turned into eval cases.

A thumbs-down or "wrong" on a card says something went wrong, not what. A reviewer opens the queue, sees the shopper's
request next to the listing they disliked, and labels it:

  should_exclude  Barney should never have recommended this listing (wrong audience, outdated, wrong connector...)
  acceptable      the listing is fine; the thumbs-down was taste or a misclick

Labelled items are exported to `evals/datasets/reviewed.jsonl`, where `python -m evals.run_reviewed` scores whether the
curator's filters catch them. Every real failure a reviewer confirms becomes a regression test; once a fix lands the
case is marked `"fixed": true` and the eval gate keeps it fixed.
"""
import json
from pathlib import Path

from app.commands import is_command
from app.db import pool

LABELS = ("should_exclude", "acceptable")
DATASET = Path(__file__).resolve().parents[1] / "evals" / "datasets" / "reviewed.jsonl"

with pool.connection() as conn:
    for column, kind in (("review_label", "text"), ("review_note", "text"), ("reviewed_by", "text"), ("reviewed_at", "timestamptz")):
        conn.execute(f"alter table feedback add column if not exists {column} {kind}")


def request_for(thread_id: str, before) -> str:
    """What the shopper asked for in this conversation up to the feedback: their last few messages, buttons left out."""
    if not thread_id:
        return ""
    with pool.connection() as conn:
        rows = conn.execute("select content from chat_log where thread_id = %s and role = 'user' and created_at <= %s order by id desc limit 6",
                            (thread_id, before)).fetchall()
    said = [r["content"] for r in rows if not is_command(r["content"])][:3]
    return " | ".join(reversed(said))


def queue(limit: int = 50) -> list[dict]:
    """Negative feedback nobody has reviewed yet, oldest first, each with the shopper's request."""
    with pool.connection() as conn:
        rows = conn.execute(
            "select id, thread_id, product, title, verdict, at from feedback "
            "where verdict in ('down', 'wrong') and review_label is null order by id limit %s", (limit,)).fetchall()
    return [{"id": r["id"], "product": r["product"], "title": r["title"], "verdict": r["verdict"],
             "request": request_for(r["thread_id"], r["at"]), "at": r["at"].isoformat()} for r in rows]


def label(feedback_id: int, verdict: str, note: str = "", reviewer: str = "") -> bool:
    """Record a reviewer's decision. False if the label is unknown or the item was already reviewed."""
    if verdict not in LABELS:
        raise ValueError(f"label must be one of {LABELS}")
    with pool.connection() as conn:
        row = conn.execute(
            "update feedback set review_label = %s, review_note = %s, reviewed_by = %s, reviewed_at = now() "
            "where id = %s and verdict in ('down', 'wrong') and review_label is null returning id",
            (verdict, note[:300], reviewer[:80], feedback_id)).fetchone()
    return row is not None


def export(path: Path = DATASET) -> int:
    """Append reviewed items that are not in the dataset yet. Returns how many were added."""
    path.parent.mkdir(parents=True, exist_ok=True)
    have = {json.loads(line)["id"] for line in path.read_text().splitlines() if line.strip()} if path.exists() else set()
    with pool.connection() as conn:
        rows = conn.execute("select id, thread_id, product, title, review_label, review_note, at from feedback "
                            "where review_label is not null order by id").fetchall()
    added = 0
    with path.open("a") as f:
        for r in rows:
            case_id = f"fb-{r['id']}"
            if case_id in have:
                continue
            f.write(json.dumps({"id": case_id, "source": "feedback", "request": request_for(r["thread_id"], r["at"]), "product": r["product"],
                                "title": r["title"], "label": r["review_label"], "note": r["review_note"], "fixed": False},
                               ensure_ascii=False) + "\n")
            added += 1
    return added
