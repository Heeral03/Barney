import logging
import re
from typing import Optional

from app.sources.cache import ttl_cache
from app.sources.serpkite import note_failure, quota_exhausted, sk

log = logging.getLogger(__name__)


def inr(n: float) -> str:
    s = str(int(round(n)))
    if len(s) <= 3:
        return f"₹{s}"
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return "₹" + ",".join(parts + [tail])


_MONEY = re.compile(
    r"(?i)\b(?:under|below|within|around|about|upto|up to|max|budget(?: of)?)?\s*"
    r"(?:(?:₹|rs\.?|inr)\s*[\d,.]+\s*(?:k|lakhs?|lacs?)?|[\d,.]+\s*(?:k|lakhs?|lacs?|inr|rupees?|rs)\b)"
)


_UNITS = {"k": 1_000, "lakh": 100_000, "lac": 100_000, "crore": 10_000_000, "cr": 10_000_000}
_AMOUNT = re.compile(r"(?i)(₹|rs\.?\s*|inr\s*)?(\d[\d,]*(?:\.\d+)?)\s*(k|lakhs?|lacs?|crores?|cr)?\b")
_BUDGET_WORDS = re.compile(r"(?i)budget|under|below|around|about|upto|up to|within|max|upper|above|over|min|at least")
_FLOOR_WORDS = re.compile(r"(?i)above|over|min|at least")


def parse_budget(text: str) -> tuple[Optional[int], Optional[int]]:
    """(min, max) rupees from a message like "around 1 lakh", "under 80k", "₹50,000", "between 50k and 80k".

    A safety net for when the model leaves the budget out. A number only counts when it is written like money:
    a currency sign, a unit (k, lakh, crore), "rupees", or a budget word right before it. So "16GB" is ignored.
    """
    found = []
    for m in _AMOUNT.finditer(text or ""):
        currency, num, unit = m.group(1), m.group(2), (m.group(3) or "").lower().rstrip("s")
        value = float(num.replace(",", "")) * _UNITS.get(unit, 1)
        before = text[max(0, m.start() - 14):m.start()]
        context = bool(_BUDGET_WORDS.search(before))
        rupees = bool(re.match(r"(?i)\s*(rupees?|rs|inr)\b", text[m.end():]))
        if unit == "k" and not (currency or context or rupees):
            ok = value >= 10_000  # "80k" is a price, "4K display" is not
        else:
            ok = bool(currency or unit or rupees or (context and value >= 1_000))
        if ok and value >= 500:
            found.append((int(value), bool(_FLOOR_WORDS.search(before))))
    if not found:
        return None, None
    if len(found) >= 2:
        values = [v for v, _ in found]
        return min(values), max(values)
    value, is_floor = found[0]
    return (value, None) if is_floor else (None, value)


def clean_query(q: str) -> str:
    """Make a model-written query safe for a shopping search.

    Budgets, currency and "India" in the query make Google Shopping return nothing, and the model
    adds them despite being told not to. Also fixes underscores from internal product ids.
    """
    q = q.replace("_", " ").replace("‑", "-")
    q = _MONEY.sub(" ", q)
    q = re.sub(r"(?i)\b(?:under|below|upto|up to|within|around|about)\s+\d[\d,.]*\b", " ", q)  # "under 1000" with no sign
    q = re.sub(r"(?i)\b(india|indian|budget|rupees?|inr)\b|₹", " ", q)
    return re.sub(r"\s+", " ", q).strip(" ,.-")


def clean_queries(queries: list[str]) -> list[str]:
    seen, out = set(), []
    for q in map(clean_query, queries or []):
        if q and q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out[:3]


def _shopping(query: str) -> list[dict]:
    if quota_exhausted():
        return []
    try:
        res = sk.shopping(query, country="in", num=10)
        res = res.model_dump() if hasattr(res, "model_dump") else res
    except Exception as e:
        log.warning("shopping search %r failed: %s", query, e)
        note_failure(e)
        return []
    return res.get("results") or []


@ttl_cache(900)
def shopping_offers(query: str) -> list[dict]:
    """Google Shopping (via SerpKite) for ONE query, normalised, in relevance order (`rank` 0 is the best match).

    Budget filtering, de-duplication, ranking and link/image lookup all happen later, in the curator.
    """
    offers = []
    for rank, item in enumerate(_shopping(query)):
        title, price = item.get("title"), item.get("price_value")
        if not title or not price:
            continue
        offers.append(
            {
                "title": title,
                "price_inr": price,
                "price_display": inr(price),
                "seller": item.get("source") or "Unknown",
                "rating": item.get("rating"),
                "rating_count": item.get("rating_count"),
                "api": "google_shopping",
                "rank": rank,
            }
        )
    return offers
