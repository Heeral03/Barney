"""The "Barney noticed" feed: things worth the shopper's attention that they did not have to ask for.

Barney only suggests; the shopper buys on the store's own site. So what he notices is about suggestions:
  - a wishlisted product's price fell;
  - a product the shopper opened with "Buy this" / "Check this out" is now cheaper than when they looked.

A background worker (`python -m app.worker`) builds these. Each item has a dedupe key, so the same drop is announced once.
"""
import logging

from app import alerts
from app.db import pool
from app.pricehistory import observe
from app.sources.verify import page_price
from app.tools.products import inr

log = logging.getLogger(__name__)

DROP_AT_LEAST = 0.05  # a fall smaller than 5% is noise
CLICK_WINDOW_DAYS = 14
MAX_FEED = 30

with pool.connection() as conn:
    conn.execute("""
        create table if not exists feed_items (
            id bigserial primary key,
            user_id text not null,
            kind text not null,
            title text not null,
            body text not null,
            link text,
            dedupe text not null,
            seen boolean not null default false,
            created_at timestamptz not null default now(),
            unique (user_id, dedupe)
        )""")


def _add(user_id: str, kind: str, title: str, body: str, link: str | None, dedupe: str) -> bool:
    with pool.connection() as conn:
        row = conn.execute(
            "insert into feed_items (user_id, kind, title, body, link, dedupe) values (%s, %s, %s, %s, %s, %s) "
            "on conflict (user_id, dedupe) do nothing returning id", (user_id, kind, title[:200], body[:400], link, dedupe)).fetchone()
    return bool(row)


def wishlist_drops() -> int:
    """Wishlisted products whose latest checked price is clearly below the one before it."""
    made = 0
    with pool.connection() as conn:
        rows = conn.execute("""
            select w.user_id, w.id, w.title, w.offer->>'link' as link,
                   (select price_inr from price_checks where wishlist_id = w.id order by checked_at desc limit 1) as now_price,
                   (select price_inr from price_checks where wishlist_id = w.id order by checked_at desc offset 1 limit 1) as before_price
            from wishlist w""").fetchall()
    for r in rows:
        if r["now_price"] is None or r["before_price"] is None:
            continue
        now, before = float(r["now_price"]), float(r["before_price"])
        if now <= before * (1 - DROP_AT_LEAST):
            made += _add(r["user_id"], "drop", f"Price dropped: {r['title'][:70]}",
                         f"Now {inr(now)}, was {inr(before)}. It's on your wishlist.", r["link"], f"drop:{r['id']}:{int(now)}")
    return made


def clicked_drops() -> int:
    """Products the shopper opened (Buy this / Check this out) that are now cheaper than when they looked."""
    made = 0
    with pool.connection() as conn:
        rows = conn.execute("""
            select distinct on (user_id, title) user_id, title, link, price
            from events
            where kind in ('buy', 'check') and link is not null and price is not null
              and at > now() - make_interval(days => %s)
            order by user_id, title, at desc""", (CLICK_WINDOW_DAYS,)).fetchall()
    for r in rows:
        now = page_price(r["link"], alerts.PAGE_TIMEOUT)
        if now is None:
            continue
        observe(r["title"], now, "")  # the history learns from this check too
        was = float(r["price"])
        if now <= was * (1 - DROP_AT_LEAST):
            made += _add(r["user_id"], "drop", f"Cheaper now: {r['title'][:70]}",
                         f"You looked at it for {inr(was)}. It's {inr(now)} now.", r["link"], f"click:{r['title'][:60]}:{int(now)}")
    return made


def build_all() -> dict:
    """The scheduled job: refresh prices, then turn what changed into feed items."""
    checked = alerts.check_all()
    return {**checked, "wishlist_drops": wishlist_drops(), "clicked_drops": clicked_drops()}


def unseen(user_id: str, limit: int = MAX_FEED) -> list[dict]:
    with pool.connection() as conn:
        rows = conn.execute("select id, kind, title, body, link, extract(epoch from created_at) as at from feed_items "
                            "where user_id = %s and not seen order by id desc limit %s", (user_id, limit)).fetchall()
    return [{**r, "at": float(r["at"])} for r in rows]


def mark_seen(user_id: str) -> None:
    with pool.connection() as conn:
        conn.execute("update feed_items set seen = true where user_id = %s and not seen", (user_id,))
