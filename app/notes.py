"""The plain-words notes under every card: what is good about a listing for THIS shopper, and what to watch.

Computed from facts only (no model): the shopper's answers, the listing's own title, rating and price, and what was
checked on the store's page. So every card, not just the pick, says why it is on the list, and none hides a weakness.
Each note is {"kind": "good" | "warn", "text": str}.
"""
import re
import time
from datetime import date

from app.freshness import model_year

STALE_AFTER = 2  # same rule the curator uses for "old model"
FEW_REVIEWS = 20
MAX_GOOD = 3


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9][a-z0-9.+-]*", (text or "").lower()) if len(w) > 1}


def _matches(offer: dict, profile: dict) -> list[str]:
    """Things the shopper asked for that the listing's own title mentions ("USB-C", "13 inch", "wired")."""
    title = _words(offer.get("title"))
    hits = []
    for topic, value in (profile.get("facts") or {}).items():
        for part in re.split(r"[,/]", str(value)):
            words = _words(part)
            if words and "open" not in words and words <= title:
                hits.append(part.strip())
    return hits[:2]


def checked_ago(checked_at: float | None, now: float | None = None) -> str:
    if checked_at is None:
        return ""
    minutes = max(0, int(((now or time.time()) - checked_at) // 60))
    return "just now" if minutes < 1 else f"{minutes} min ago" if minutes < 60 else f"{minutes // 60} h ago" if minutes < 1440 else f"{minutes // 1440} d ago"


def notes_for(offer: dict, profile: dict) -> list[dict]:
    good, warn = [], []
    year, this_year = model_year(offer.get("title") or ""), date.today().year
    if year and year <= this_year - STALE_AFTER:
        warn.append(f"Older model (around {year})")
    elif year and year >= this_year - 1:
        good.append(f"Current generation ({year})")

    rating, count = offer.get("rating"), offer.get("rating_count") or 0
    if not rating:
        warn.append("No reviews yet")
    elif count < FEW_REVIEWS:
        warn.append(f"Only {count} review{'s' if count != 1 else ''}, so the rating is weak evidence")
    elif rating >= 4.3 and count >= 100:
        good.append(f"Rated {rating} by {count:,} buyers")
    elif rating < 3.8:
        warn.append(f"Rated only {rating}")

    for hit in _matches(offer, profile):
        good.append(f"Mentions your {hit}")
    hi, price = profile.get("budget_max"), offer.get("price_inr")
    if offer.get("over_budget"):
        warn.append("Over your budget")
    elif hi and price and price <= hi:
        good.append("Within your budget")
    if "lowest price" in (offer.get("tags") or []):
        good.append("Lowest price of these options")

    if offer.get("seller_trusted") is False:
        warn.append("Seller I can't vouch for")
    if offer.get("stores") and not offer.get("price_verified"):
        warn.append("Price not checked on the store's page")
    return [{"kind": "warn", "text": t} for t in warn[:3]] + [{"kind": "good", "text": t} for t in good[:MAX_GOOD]]


def annotate(offers: list[dict], profile: dict) -> list[dict]:
    return [{**o, "notes": notes_for(o, profile)} for o in offers]
