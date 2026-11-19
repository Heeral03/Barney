"""Price history for every product Barney shows, not only wishlisted ones.

Each time a product is shown at a store, its price is noted. After a few sightings Barney can say whether today's price is
good: "12% below its usual price" or "18% above its usual price, worth waiting". With too little history he says nothing
rather than guess.
"""
import logging
import re
import statistics

from app.db import pool

log = logging.getLogger(__name__)

WINDOW_DAYS = 90
MIN_SAMPLES = 3  # sightings needed before a judgment is made
BAND = 0.07  # within 7% of the usual price counts as fair

with pool.connection() as conn:
    conn.execute("""
        create table if not exists price_observations (
            id bigserial primary key,
            key text not null,
            domain text not null default '',
            price numeric not null,
            at timestamptz not null default now()
        )""")
    conn.execute("create index if not exists price_obs_key_idx on price_observations (key, at)")


def key_of(title: str) -> str:
    """The same product spelled slightly differently by different listings should land on one key."""
    words = sorted(set(re.findall(r"[a-z0-9]+", (title or "").lower())))
    return " ".join(words)[:200]


def observe(title: str, price: float | None, domain: str = "") -> dict:
    """Note this sighting and judge the price against the history. Returns {"verdict", "text", "usual_inr", "samples"}.
    Never raises: history is a bonus and must not break a turn."""
    empty = {"verdict": "new", "text": "", "usual_inr": None, "samples": 0}
    if not title or not price:
        return empty
    key = key_of(title)
    try:
        with pool.connection() as conn:
            past = [float(r["price"]) for r in conn.execute(
                "select price from price_observations where key = %s and at > now() - make_interval(days => %s)",
                (key, WINDOW_DAYS)).fetchall()]
            recent = conn.execute(
                "select 1 from price_observations where key = %s and domain = %s and price = %s and at > now() - interval '6 hours'",
                (key, domain, price)).fetchone()
            if not recent:  # the same price at the same store within hours adds nothing
                conn.execute("insert into price_observations (key, domain, price) values (%s, %s, %s)", (key, domain, price))
        return judge(price, past)
    except Exception as e:
        log.warning("price history unavailable: %s", e)
        return empty


def judge(price: float, past: list[float]) -> dict:
    """Compare a price with earlier sightings of the same product."""
    if len(past) < MIN_SAMPLES:
        return {"verdict": "new", "text": "", "usual_inr": None, "samples": len(past)}
    usual = statistics.median(past)
    change = (price - usual) / usual
    pct = round(abs(change) * 100)
    if change <= -BAND:
        verdict, text = "good", f"{pct}% below its usual price. A good time to buy."
    elif change >= BAND:
        verdict, text = "high", f"{pct}% above its usual price. Worth waiting if you can."
    else:
        verdict, text = "fair", "About its usual price."
    return {"verdict": verdict, "text": text, "usual_inr": round(usual), "samples": len(past)}
