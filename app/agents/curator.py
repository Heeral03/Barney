import math
import re

from app.state import RESET, chatState

LIMIT = 6  # the first shortlist: the best pick first, the rest are the "other options" shown on request
MORE_BATCH = 4  # how many new listings a "more options" search adds
RESERVE = 30  # ranked listings kept un-numbered, so more options usually need no new search

_MEN = re.compile(r"\b(men|mens|men's|male|boys?)\b", re.I)
_WOMEN = re.compile(r"\b(women|womens|women's|ladies|female|girls?)\b", re.I)


def _score(o: dict, position: int) -> float:
    """Rating shrunk toward 3 when there are few reviews, minus a small penalty for lower search relevance."""
    reviews = o.get("rating_count") or 0
    confidence = reviews / (reviews + 20)
    rating = o.get("rating") or 3.0
    return rating * confidence + 3.0 * (1 - confidence) - 0.25 * position + 0.1 * math.log10(reviews + 1)


def _key(o: dict) -> str:
    return " ".join(sorted(set(o["title"].lower().split())))


def _dedupe(raw: list[dict], skip: set[str]) -> list[dict]:
    """Merge the workers' listings. The same product listed by several sellers keeps its cheapest price."""
    groups: dict[str, list[dict]] = {}
    for o in sorted(raw, key=lambda o: o.get("rank", 0)):
        if _key(o) not in skip:
            groups.setdefault(_key(o), []).append(o)
    unique = []
    for group in groups.values():
        priced = [o for o in group if o.get("price_inr")]
        best = min(priced, key=lambda o: o["price_inr"]) if priced else group[0]
        unique.append({**best, "rank": min(o.get("rank", 0) for o in group)})
    return unique


def _audience(profile: dict, queries: list[str]) -> str | None:
    """"women" or "men" when the request is clearly for one of them."""
    text = " ".join([profile.get("product") or "", *map(str, (profile.get("facts") or {}).values()), *queries])
    women, men = bool(_WOMEN.search(text)), bool(_MEN.search(text))
    return "women" if women and not men else "men" if men and not women else None


def _right_audience(offers: list[dict], audience: str | None) -> list[dict]:
    """Drop listings made for the other audience (Men's shoes in a women's search). Never empties the list."""
    if not audience:
        return offers
    wrong = _MEN if audience == "women" else _WOMEN
    kept = [o for o in offers if not wrong.search(o["title"])]
    return kept if len(kept) >= 3 else offers


def _tag(offers: list[dict]) -> list[dict]:
    """Facts the presenter can lean on: which listing is cheapest, best rated, most reviewed."""
    priced = [o for o in offers if o.get("price_inr")]
    tags: dict[int, list[str]] = {}
    if len(priced) > 1:
        tags.setdefault(id(min(priced, key=lambda o: o["price_inr"])), []).append("lowest price")
    rated = [o for o in offers if o.get("rating") and (o.get("rating_count") or 0) >= 20]
    if len(rated) > 1:
        tags.setdefault(id(max(rated, key=lambda o: (o["rating"], o["rating_count"]))), []).append("best rated")
    busy = [o for o in offers if (o.get("rating_count") or 0) >= 100]
    if len(busy) > 1:
        tags.setdefault(id(max(busy, key=lambda o: o["rating_count"])), []).append("most reviewed")
    return [{**o, "tags": tags[id(o)]} if id(o) in tags else o for o in offers]


def curator_node(state: chatState) -> chatState:
    """Curator: merges what the research workers found, applies the budget, ranks, and keeps a shortlist.

    No LLM, and no image lookups (the presenter fetches those only for the listings it actually shows).
    Steps: de-duplicate, drop the wrong audience, apply the budget (the minimum is only a preference), rank by
    rating, review count and search relevance, make sure the cheapest fitting option is on the list, tag it.
    The ranked remainder is kept in `reserve` for "more options". If listings exist but none fit the budget, the
    cheapest are kept and flagged `over_budget` instead of returning nothing. In "more" mode the new listings are
    appended to the existing ones instead of replacing them.
    """
    profile = state.get("profile") or {}
    search = state.get("search") or {}
    more = search.get("mode") == "more"
    existing = list(state.get("offers") or []) if more else []
    hi, lo = profile.get("budget_max"), profile.get("budget_min")
    if hi and lo and lo >= hi:
        lo = None  # "around ₹2,000" is a ceiling, not an exact price

    skip = {_key(o) for o in [*existing, *(state.get("reserve") or [])]} if more else set()
    unique = _right_audience(_dedupe(state.get("raw_offers") or [], skip), _audience(profile, search.get("queries") or []))
    priced = [o for o in unique if o.get("price_inr")]
    unpriced = [o for o in unique if not o.get("price_inr")]  # web results with no price in their text
    fits = [o for o in priced if (hi is None or o["price_inr"] <= hi) and (lo is None or o["price_inr"] >= lo)]
    if not fits and lo is not None:
        fits = [o for o in priced if hi is None or o["price_inr"] <= hi]

    relaxed = False
    if fits:
        ranked = sorted(fits, key=lambda o: -_score(o, o.get("rank", 0))) + unpriced
    elif unpriced:
        ranked = unpriced
    else:
        ranked = [{**o, "over_budget": True} for o in sorted(priced, key=lambda o: o["price_inr"])]
        relaxed = bool(ranked)

    take = MORE_BATCH if more else LIMIT
    chosen = ranked[:take]
    if fits and not more:
        cheapest = min(fits, key=lambda o: o["price_inr"])
        if cheapest not in chosen:
            chosen[-1] = cheapest  # a "cheaper option" is the most common follow-up, so always have one ready
    reserve = [o for o in ranked if o not in chosen][:RESERVE]

    start = len(existing) + 1
    new = [{**o, "number": n} for n, o in enumerate(_tag(chosen), start)]
    apis = {o.get("api") for o in new}
    meta = {
        "raw": len(unique),
        "cheapest": min((o["price_inr"] for o in priced), default=None),
        "relaxed": relaxed,
        "source": "web" if apis and apis <= {"duckduckgo", "tavily"} else "shopping",
    }
    update = {"offers": existing + new, "reserve": reserve, "search_meta": meta, "raw_offers": RESET}
    if not more:
        update["shown"] = []
    return update
