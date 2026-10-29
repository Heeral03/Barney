"""Wishlist: listings the shopper hearted. They show what the shopper likes the look of (cut, colour, pattern,
brand), so each one is also turned into a few taste memories, and the requirements agent sees the recent ones."""
import logging

from langchain_core.messages import HumanMessage
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, field_validator

from app import alerts, settings
from app.db import pool
from app.llm import Structured, load_prompt
from app.memory import writer

log = logging.getLogger(__name__)

PROMPT = load_prompt("barney_taste.txt")

with pool.connection() as conn:
    conn.execute("""
        create table if not exists wishlist (
            id bigserial primary key,
            user_id text not null,
            key text not null,
            product text not null default '',
            title text not null,
            offer jsonb not null,
            created_at timestamptz not null default now(),
            unique (user_id, key)
        )""")


with pool.connection() as conn:
    conn.execute("alter table wishlist add column if not exists target_inr numeric")


class Taste(BaseModel):
    traits: list[str] = Field(default_factory=list)

    @field_validator("traits", mode="before")
    @classmethod
    def _none(cls, v):
        return v or []


extractor = Structured(Taste, '{"traits":[""]}')


def _key(offer: dict) -> str:
    return (offer.get("link") or offer.get("title") or "").strip().lower()


def add(user_id: str, offer: dict, product: str = "") -> int | None:
    """Save a listing. Returns its id, or None if it was already on the wishlist."""
    slim = {k: offer.get(k) for k in ("title", "price_display", "price_inr", "seller", "rating", "rating_count",
                                       "link", "link_domain", "image_url")}
    with pool.connection() as conn:
        row = conn.execute(
            "insert into wishlist (user_id, key, product, title, offer) values (%s, %s, %s, %s, %s) "
            "on conflict (user_id, key) do nothing returning id",
            (user_id, _key(offer), product, offer.get("title", ""), Jsonb(slim)),
        ).fetchone()
    return row["id"] if row else None


def remove(user_id: str, item_id: int) -> None:
    with pool.connection() as conn:
        conn.execute("delete from wishlist where user_id = %s and id = %s", (user_id, item_id))


def items(user_id: str, limit: int = 100) -> list[dict]:
    with pool.connection() as conn:
        rows = conn.execute(
            "select id, product, title, offer, target_inr from wishlist where user_id = %s order by id desc limit %s", (user_id, limit)
        ).fetchall()
    seen = alerts.stats([r["id"] for r in rows])
    return [{"id": r["id"], "product": r["product"], **r["offer"], "target_inr": float(r["target_inr"]) if r["target_inr"] is not None else None,
             **seen.get(r["id"], {})} for r in rows]


def set_target(user_id: str, item_id: int, target_inr: float | None) -> None:
    """The price the shopper is waiting for (None clears it)."""
    with pool.connection() as conn:
        conn.execute("update wishlist set target_inr = %s where user_id = %s and id = %s", (target_inr, user_id, item_id))


def recent(user_id: str, n: int = 8) -> list[dict]:
    """Just what the agents need: title and product of the latest saves."""
    return [{"title": w["title"], "product": w["product"]} for w in items(user_id, n)]


def learn_taste(store, user_id: str, offer: dict, product: str, memory_id: str | None = None) -> list[str]:
    """Turn one hearted listing into taste memories ("Likes high-rise straight-fit jeans"). Never raises.
    Skipped when the shopper has paused learning. `memory_id` is whose tastes they go to (a profile), the account by default."""
    try:
        if not settings.learning_on(user_id):
            return []
        traits = extractor.invoke(
            [PROMPT, HumanMessage(content=f"Product type: {product or 'unknown'}\nListing title: {offer.get('title', '')[:160]}")]
        ).traits
        category = (product or "general").replace("_", " ").split()[-1].lower()
        return writer.save(store, memory_id or user_id, [{"text": t, "category": category, "kind": "preference"} for t in traits], source="inferred")
    except Exception as e:
        log.warning("could not learn taste from the wishlist: %s", e)
        return []
