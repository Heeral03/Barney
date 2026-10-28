"""What the dashboard shows: the shopper's name, their budget, their wishlist and their recent comparisons.

Everything here is real data: the name comes from memory, comparisons are the side-by-side tables from past chats, and the
budget is a number the shopper sets. The dashboard's "remaining" is the budget minus what their wishlist would cost.
"""
import re

from app import wishlist
from app.db import pool
from app.memory import store as ltm_store

with pool.connection() as conn:
    conn.execute("create table if not exists budget (user_id text primary key, amount_inr numeric not null)")


def get_budget(user_id: str) -> float | None:
    with pool.connection() as conn:
        row = conn.execute("select amount_inr from budget where user_id = %s", (user_id,)).fetchone()
    return float(row["amount_inr"]) if row else None


def set_budget(user_id: str, amount_inr: float | None) -> None:
    with pool.connection() as conn:
        if amount_inr is None:
            conn.execute("delete from budget where user_id = %s", (user_id,))
        else:
            conn.execute("insert into budget (user_id, amount_inr) values (%s, %s) "
                         "on conflict (user_id) do update set amount_inr = excluded.amount_inr", (user_id, amount_inr))


def name_of(user_id: str) -> str | None:
    """The shopper's name, if they ever told Barney ("Name is Heeral")."""
    try:
        for m in ltm_store.about_the_person(ltm_store.ltm, user_id):
            found = re.match(r"(?i)^(?:their |the shopper's )?name is (.+)$", str(m.get("text", "")).strip())
            if found:
                return found.group(1).strip(" .")
    except Exception:
        pass
    return None


def _price(row: dict) -> float | None:
    if row.get("price_inr"):
        return float(row["price_inr"])
    digits = re.sub(r"[^\d.]", "", str(row.get("price_display") or "").replace(",", ""))
    return float(digits) if digits else None


def comparison_card(table: dict, thread_id: str = "") -> dict | None:
    """A summary of one side-by-side table for the dashboard: the pick, the price range, the rating, the stores."""
    rows = table.get("rows") or []
    if not rows:
        return None
    best = next((r for r in rows if r.get("best")), rows[0])
    prices = [p for p in map(_price, rows) if p]
    rated = [r for r in rows if r.get("rating")]
    if prices and _price(best) == min(prices) and len(prices) > 1:
        tag = "Lowest price"
    elif rated and best.get("rating") == max(r["rating"] for r in rated) and len(rated) > 1:
        tag = "Best overall"
    else:
        tag = "Barney's pick"
    return {"thread_id": thread_id, "title": best["title"], "image_url": best.get("image_url"), "options": len(rows),
            "price_low": min(prices) if prices else None, "price_high": max(prices) if prices else None,
            "rating": best.get("rating"), "rating_count": best.get("rating_count"),
            "stores": max(len(best.get("stores") or []), 1), "tag": tag, "specs": table.get("specs") or []}


def comparisons(user_id: str, limit: int = 6) -> list[dict]:
    """The shopper's most recent side-by-side comparisons, newest first."""
    with pool.connection() as conn:
        rows = conn.execute(
            "select thread_id, payload->'table' as t from chat_log where user_id = %s and role = 'assistant' "
            "and jsonb_typeof(payload->'table') = 'object' order by id desc limit %s", (user_id, limit)).fetchall()
    return [c for c in (comparison_card(r["t"], r["thread_id"]) for r in rows) if c]


def overview(user_id: str) -> dict:
    items = wishlist.items(user_id)
    amount = get_budget(user_id)
    total = sum(w["price_inr"] for w in items if w.get("price_inr"))
    cards = comparisons(user_id, 6)
    with pool.connection() as conn:
        n_comparisons = conn.execute(
            "select count(*) as n from chat_log where user_id = %s and jsonb_typeof(payload->'table') = 'object'", (user_id,)).fetchone()["n"]
    try:
        n_prefs = len(ltm_store.all_memories(ltm_store.ltm, user_id))
    except Exception:
        n_prefs = 0
    return {
        "name": name_of(user_id),
        "stats": {"wishlist": len(items), "comparisons": n_comparisons, "preferences": n_prefs},
        "budget": {"amount": amount, "wishlist_total": total, "remaining": (amount - total) if amount is not None else None},
        "wishlist": items[:3], "comparisons": cards[:3],
    }
