import math
import re
from datetime import date

from app.freshness import model_year
from app.pricing import is_trusted
from app.state import RESET, chatState

LIMIT = 6  # the first shortlist: the best pick first, the rest are the "other options" shown on request
MORE_BATCH = 4  # how many new listings a "more options" search adds
RESERVE = 30  # ranked listings kept un-numbered, so more options usually need no new search

_MEN = re.compile(r"\b(men|mens|men's|male|boys?)\b", re.I)
_WOMEN = re.compile(r"\b(women|womens|women's|ladies|female|girls?)\b", re.I)


_OLD_OK = re.compile(r"\b(refurbished|renewed|used|second[- ]?hand|pre[- ]?owned|old|older|vintage|retro)\b", re.I)
STALE_AFTER = 2  # a model year more than this many years behind the current one is an old model


def _year(o: dict) -> int | None:
    """The year a listing's product came out, from its title ("2019 Edition", "i7 13th Gen", "MacBook Air M1")."""
    return model_year(o.get("title") or "")


def _latest(offers: list[dict], profile: dict, queries: list[str]) -> list[dict]:
    """Drop listings whose title names an old model year (a 2019 laptop in 2026). Skipped when the shopper asked for
    refurbished or older models, or named that year themselves. Never empties the list."""
    said = [*map(str, (profile.get("facts") or {}).values()), *queries]
    if _OLD_OK.search(" ".join(said)):
        return offers
    this_year = date.today().year
    named = {y for s in said if (y := model_year(s))}  # they asked for that very generation or year
    fresh = [o for o in offers if (y := _year(o)) is None or y in named or y >= this_year - STALE_AFTER]
    return fresh if len(fresh) >= 3 else offers


_PLUGS = {
    "usb-c": re.compile(r"\b(usb[ -]?c|type[ -]?c)\b", re.I),
    "lightning": re.compile(r"\blightning\b", re.I),
    "3.5mm": re.compile(r"\b3\.5\s?mm\b|\baux\b", re.I),
    "micro-usb": re.compile(r"\bmicro[ -]?usb\b", re.I),
}


def _compatible(offers: list[dict], profile: dict, queries: list[str]) -> list[dict]:
    """When the shopper named the plug they need (USB-C, Lightning, 3.5 mm), drop listings whose title names a different
    one. A title that names none stays. Never empties the list."""
    said = " ".join([*map(str, (profile.get("facts") or {}).values()), *queries])
    wanted = {name for name, rx in _PLUGS.items() if rx.search(said)}
    if len(wanted) != 1:  # none asked, or several acceptable: nothing to enforce
        return offers
    kept = [o for o in offers if not any(rx.search(o["title"]) for name, rx in _PLUGS.items() if name not in wanted)
            or _PLUGS[next(iter(wanted))].search(o["title"])]
    return kept if len(kept) >= 3 else offers


JUNK_BELOW = 0.3  # priced under this share of the median price: counterfeits, empty boxes, wrong category
MIN_FOR_MEDIAN = 5


def _trustworthy(offers: list[dict]) -> list[dict]:
    """Drop what looks like junk: a price far below everything else for the same search, and listings nobody has rated
    that come from a seller we do not recognise. Never empties the list."""
    prices = sorted(o["price_inr"] for o in offers if o.get("price_inr"))
    floor = prices[len(prices) // 2] * JUNK_BELOW if len(prices) >= MIN_FOR_MEDIAN else 0
    kept = [o for o in offers
            if not (o.get("price_inr") and o["price_inr"] < floor)
            and (o.get("rating") or o.get("rating_count") or is_trusted(o.get("seller") or ""))]
    return kept if len(kept) >= 3 else offers


def _score(o: dict, position: int) -> float:
    """Rating shrunk toward 3 when there are few reviews, minus a small penalty for lower search relevance and for
    a model year that is behind the current one."""
    reviews = o.get("rating_count") or 0
    confidence = reviews / (reviews + 20)
    rating = o.get("rating") or 3.0
    year = _year(o)
    age = min(max(date.today().year - year, 0), 5) if year else 0
    return rating * confidence + 3.0 * (1 - confidence) - 0.25 * position + 0.1 * math.log10(reviews + 1) - 0.5 * age


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
    queries = search.get("queries") or []
    unique = _trustworthy(_compatible(_latest(_right_audience(_dedupe(state.get("raw_offers") or [], skip), _audience(profile, queries)), profile, queries), profile, queries))
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
        # A "cheaper option" is a common follow-up, but the cheapest listing must be a real candidate: not an older
        # model than the shortlist, and not one nobody has rated while rated ones exist.
        newest = max((y for o in chosen if (y := _year(o))), default=0)
        decent = [o for o in fits if (_year(o) or newest) >= newest - 1 and (o.get("rating") or not any(c.get("rating") for c in chosen))]
        cheapest = min(decent or fits, key=lambda o: o["price_inr"])
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
