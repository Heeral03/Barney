"""Presenter: the single best pick first, then more options in small batches whenever the shopper asks."""
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from langchain_core.messages import SystemMessage
from pydantic import BaseModel, field_validator

from app import pricing
from app.agents.common import matched_on_text, remembered_text, reply, requirements_text
from app.commands import ACCEPT, BROADEN, CHANGE, COMPARE, RAISE_BUDGET, RESTART, SHOW_ALTERNATIVES
from app.llm import Structured, load_prompt
from app.sources.serpkite import find_media_many
from app.state import chatState
from app.tools.products import inr

PRESENTER_PROMPT = load_prompt("barney_presenter.txt")
COMPARE_PROMPT = load_prompt("barney_compare.txt")
BATCH = 4  # options shown per "more options" request
PREFETCH = 1  # candidates whose pictures and store prices are fetched while the model is still choosing

_media_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="media")
_prepare_pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="prepare")


def _clean(v) -> str:
    return str(v or "").strip(' "[]\'')


class Recommendation(BaseModel):
    best_number: int
    intro: str = ""
    reasons: list[str]
    watch_out: str = ""
    follow_up: str = ""
    follow_up_topic: str = ""
    follow_up_options: list[str] = []

    @field_validator("reasons", mode="before")
    @classmethod
    def _split_reasons(cls, v):
        # The model sometimes glues several reasons into one string with stray `","` separators or brackets.
        items = [v] if isinstance(v, str) else (v or [])
        return [c for r in items for p in str(r).split('","') if (c := _clean(p))]

    @field_validator("intro", "watch_out", "follow_up", "follow_up_topic", mode="before")
    @classmethod
    def _text(cls, v):
        return _clean(v)

    @field_validator("follow_up_options", mode="before")
    @classmethod
    def _options(cls, v):
        return [c for o in (v or []) if (c := _clean(o))][:4]


class Tradeoff(BaseModel):
    number: int
    line: str


class Comparison(BaseModel):
    tradeoffs: list[Tradeoff]
    verdict: str


recommender = Structured(
    Recommendation,
    '{"best_number":1,"intro":"","reasons":["",""],"watch_out":"","follow_up":"","follow_up_topic":"","follow_up_options":[""]}',
)
comparer = Structured(Comparison, '{"tradeoffs":[{"number":2,"line":""}],"verdict":""}')


def _listing_text(offers: list[dict], vs: Optional[dict] = None) -> str:
    """One line per offer. With `vs`, adds a computed price gap so the model never does that arithmetic."""
    def gap(o: dict) -> str:
        if not vs or o["number"] == vs["number"] or o.get("price_inr") is None or vs.get("price_inr") is None:
            return ""
        diff = o["price_inr"] - vs["price_inr"]
        return f" | {inr(abs(diff))} {'MORE' if diff > 0 else 'LESS'} than #{vs['number']}" if diff else f" | same price as #{vs['number']}"

    return "\n".join(
        f"{o['number']}. {o['title'][:110]} | {o['price_display']}{gap(o)}{' | OVER BUDGET' if o.get('over_budget') else ''}"
        f" | seller: {o['seller']} | rating: {o.get('rating') or 'none'} ({o.get('rating_count') or 0} reviews)"
        f"{' | ' + ', '.join(o['tags']) if o.get('tags') else ''}"
        for o in offers
    )


def _context(state: chatState, listings: str) -> SystemMessage:
    profile = state.get("profile") or {}
    parts = [requirements_text(profile), remembered_text(state.get("recalled"), profile.get("product")),
             f"Questions already asked: {', '.join(profile.get('asked') or []) or 'none'}", listings]
    return SystemMessage(content="\n\n".join(p for p in parts if p))


def _with_media(offers: list[dict]) -> list[dict]:
    """Links and pictures, looked up only for the listings about to be shown (each lookup is a search call)."""
    need = [o for o in offers if not o.get("link") and not o.get("image_url")]
    found = iter(find_media_many([(o["title"], o["seller"]) for o in need]) if need else [])
    return [o if o.get("link") else {**o, **next(found, {})} for o in offers]


def _prepare(offer: dict) -> dict:
    """Everything a card needs before it is shown: a picture, and the price at every store (with a link to each seller),
    so the shopper never has to leave Barney to compare. Already-compared offers are returned as they are."""
    offer = _with_media([offer])[0]
    if offer.get("token") and not offer.get("stores"):
        offer = pricing.apply_to_offer(offer, pricing.compare(offer["token"]))
    return offer


def prepare_all(offers: list[dict]) -> list[dict]:
    """`_prepare` for several offers at once (each store lookup is a network call)."""
    return list(_prepare_pool.map(_prepare, offers)) if offers else []


def _merge(offers: list[dict], updated: list[dict]) -> list[dict]:
    by_number = {o["number"]: o for o in updated}
    return [by_number.get(o["number"], o) for o in offers]


def present_node(state: chatState) -> chatState:
    """The single best offer with 2-3 reasons, and one tailored follow-up question."""
    profile = dict(state.get("profile") or {})
    offers = state.get("offers") or []
    if not offers:
        profile.pop("pick", None)
        return reply(
            "I couldn't find good listings for that search. 😕 I can try again with simpler wording, or we can start fresh.",
            [BROADEN, RESTART[0]], profile=profile,
        )

    # The model almost always picks one of the top few, so fetch their pictures and compare their stores while it thinks.
    prefetch = {o["number"]: _media_pool.submit(_prepare, o) for o in offers[:PREFETCH]}
    prices = [o["price_inr"] for o in offers if o.get("price_inr")]
    spread = (f"No budget is set. These listings range from {inr(min(prices))} to {inr(max(prices))}.\n\n"
              if prices and not profile.get("budget_max") and max(prices) > 1.5 * min(prices) else "")
    rec: Recommendation = recommender.invoke(
        [PRESENTER_PROMPT, _context(state, f"{spread}Listings:\n{_listing_text(offers)}")])
    best_listing = next((o for o in offers if o["number"] == rec.best_number), offers[0])
    ready = [f.result() for f in prefetch.values()]
    best = next((o for o in ready if o["number"] == best_listing["number"]), None) or _prepare(best_listing)
    profile["pick"] = best["number"]
    if rec.follow_up and rec.follow_up_topic:
        profile["asked"] = [*(profile.get("asked") or []), rec.follow_up_topic]

    reasons = "\n".join(f"{i}. {r}" for i, r in enumerate(rec.reasons[:3], 1))
    text = (
        f"{rec.intro or 'Okay, I\'ve got one for you 🎯'}\n\n**{best['title'][:90]}** at **{best['price_display']}**"
        f"{' ✓' if best.get('price_verified') else ''} from {best['seller']}\n\n**Why it fits you**\n{reasons}"
    )
    matched = matched_on_text(profile, state.get("recalled"))
    if matched:
        text += f"\n\n{matched}"
    deal = pricing.comparison_text(best.get("stores"))
    if deal:
        text += f"\n\n{deal}"
    cap, source = profile.get("budget_max"), (state.get("search_meta") or {}).get("source")
    if best.get("over_budget") and cap:
        text += (f"\n\n⚠️ _Nothing I found fits your {inr(cap)} budget, so this is the closest option, "
                 f"{inr(best['price_inr'] - cap)} over._")
    elif rec.watch_out:
        text += f"\n\n_Heads up: {rec.watch_out}_"
    if source == "web":
        text += "\n\n_I found these through a general web search, so please confirm the price and size on the page._"
    text += f"\n\n{rec.follow_up or 'Want to see a few other options too?'}"

    options = [*rec.follow_up_options[:3], SHOW_ALTERNATIVES, *([COMPARE] if len(offers) > 1 else []), ACCEPT[0]]
    if best.get("over_budget"):
        options.insert(0, f"{RAISE_BUDGET}{inr(best['price_inr'])}")
    return reply(text, options, cards=[{**best, "best": True}], profile=profile,
                 offers=_merge(offers, [*ready, best]), shown=[best["number"]])


def more_node(state: chatState) -> chatState:
    """The next few listings the shopper has not seen: from what was already found, then the reserve, then a new search."""
    profile = dict(state.get("profile") or {})
    offers, reserve = list(state.get("offers") or []), list(state.get("reserve") or [])
    shown = set(state.get("shown") or [])
    batch = [o for o in offers if o["number"] not in shown][:BATCH]
    if len(batch) < BATCH and reserve:  # promote ranked leftovers instead of searching again
        take, reserve = reserve[:BATCH - len(batch)], reserve[BATCH - len(batch):]
        moved = [{**o, "number": len(offers) + i} for i, o in enumerate(take, 1)]
        offers += moved
        batch += moved

    if not batch:
        if state.get("route") == "research":  # we just searched and found nothing new
            return reply("That's everything I could find for this. 🤷 Want me to loosen the budget or change what you're after?",
                         [CHANGE, RESTART[0]], profile=profile, route="end")
        simple = (profile.get("product") or "").replace("_", " ")
        return {"route": "research", "search": {"queries": [simple], "mode": "more"}, "options": [], "cards": []}

    batch = prepare_all(batch)  # pictures and every store's price, for each card shown
    offers = _merge(offers, batch)
    pick = profile.get("pick") or 1
    best = next((o for o in offers if o["number"] == pick), offers[0])
    cmp: Comparison = comparer.invoke(
        [COMPARE_PROMPT, _context(state, f"Recommended: #{best['number']}\n\nListings:\n{_listing_text([best, *batch], vs=best)}")]
    )
    lines = {t.number: t.line for t in cmp.tradeoffs}
    rows = "\n".join(f"- **#{o['number']}**: {lines[o['number']]}" for o in batch if o["number"] in lines)
    intro = "Here's one more" if len(batch) == 1 else f"Here are {len(batch)} more"
    text = f"{intro} to look at, compared with my pick (#{best['number']}):\n\n{rows}\n\n{cmp.verdict}"
    shown |= {o["number"] for o in batch}
    options = [SHOW_ALTERNATIVES, COMPARE, ACCEPT[1]] if reserve or any(o["number"] not in shown for o in offers) \
        else [BROADEN, COMPARE, ACCEPT[1]]
    return reply(text, options, cards=batch, profile=profile, offers=offers, reserve=reserve, shown=sorted(shown),
                 route="end")  # "end" matters: after a fresh search `route` is still "research" and would loop back


def route_after_curator(state: chatState) -> str:
    return "more" if (state.get("search") or {}).get("mode") == "more" else "present"


def route_after_more(state: chatState) -> str:
    return "plan_research" if state.get("route") == "research" else "__end__"
