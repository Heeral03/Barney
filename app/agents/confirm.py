"""Human-in-the-loop: when the best pick is a genuine judgement call, the shopper makes it.

Between `curator` and `present`, this node looks at the top candidates. Usually one is clearly best and nothing happens
(no model call, no pause). But sometimes the shortlist holds a real trade-off: a listing that is much cheaper and one that
is slightly better rated, with nothing separating them except what the shopper values. Choosing for them is a guess, so the
graph pauses with LangGraph's `interrupt()` and asks. The run resumes with their answer, and the presenter honours it.

The pause is stored by the Postgres checkpointer, so it survives a refresh or a restart. The question is delivered as the
ordinary reply with option buttons, so a tap arrives as a normal message; `pending` and `match_choice` turn it back into
the resume value. Typing something else instead simply starts a new turn.

The node has no side effects before `interrupt()` because LangGraph re-runs a resumed node from its first line.
"""
import os

from langgraph.types import interrupt

from app.state import chatState

MIN_PRICE_GAP = 0.25   # the cheaper listing costs at least 25% less
MAX_RATING_GAP = 0.3   # ...while the better-rated one is ahead by 0.3 stars or less
MIN_REVIEWS = 20       # both ratings must rest on enough reviews to mean something
CONSIDERED = 3         # only the top of the shortlist can be a "close call"
AUTO = "You decide"


def enabled() -> bool:
    return os.getenv("CONFIRM_CLOSE_CALLS", "1") != "0"


def close_call(offers: list[dict], profile: dict) -> tuple[dict, dict] | None:
    """(cheaper, better_rated) when the top candidates are a real price-versus-rating trade-off, else None."""
    if profile.get("skip") or not enabled():
        return None  # the shopper already said "you decide"
    top = [o for o in offers[:CONSIDERED]
           if o.get("price_inr") and o.get("rating") and (o.get("rating_count") or 0) >= MIN_REVIEWS and not o.get("over_budget")]
    if len(top) < 2:
        return None
    cheap = min(top, key=lambda o: o["price_inr"])
    strong = max(top, key=lambda o: (o["rating"], o["rating_count"]))
    if cheap is strong:
        return None  # one listing wins on both counts: nothing to decide
    price_gap = 1 - cheap["price_inr"] / strong["price_inr"]
    rating_gap = strong["rating"] - cheap["rating"]
    return (cheap, strong) if price_gap >= MIN_PRICE_GAP and rating_gap <= MAX_RATING_GAP else None


def _candidate(o: dict) -> dict:
    return {k: o.get(k) for k in ("number", "title", "price_display", "seller", "rating", "rating_count", "image_url")}


def confirm_pick_node(state: chatState) -> chatState:
    profile = dict(state.get("profile") or {})
    profile.pop("pick_hint", None)  # a choice made for an earlier search does not apply to this one
    offers = state.get("offers") or []
    pair = close_call(offers, profile)
    if pair is None:
        return {"profile": profile}
    cheap, strong = pair
    choices = [
        {"label": f"Save money: {cheap['price_display']}", "number": cheap["number"]},
        {"label": f"Higher rated: {strong['price_display']}, {strong['rating']}★", "number": strong["number"]},
        {"label": AUTO, "number": None},
    ]
    saving = strong["price_inr"] - cheap["price_inr"]
    answer = interrupt({
        "type": "confirm_pick",
        "question": (f"This one is a close call, so I'd rather you choose. **{cheap['title'][:70]}** is ₹{saving:,} cheaper "
                     f"({cheap['rating']}★), while **{strong['title'][:70]}** is rated a little higher ({strong['rating']}★). "
                     "Which matters more to you?"),
        "choices": choices,
        "candidates": [_candidate(cheap), _candidate(strong)],
    })
    if isinstance(answer, int) and any(o["number"] == answer for o in offers):
        profile["pick_hint"] = answer
    return {"profile": profile}


# --- helpers for the API: is a thread waiting on this question, and does a message answer it? -------------------------

def pending(snapshot) -> dict | None:
    """The `confirm_pick` question a paused thread is waiting on, or None."""
    for task in getattr(snapshot, "tasks", ()) or ():
        for item in task.interrupts:
            if isinstance(item.value, dict) and item.value.get("type") == "confirm_pick":
                return item.value
    return None


def match_choice(question: dict, message: str):
    """(True, resume value) when `message` is one of the offered buttons, else (False, None)."""
    for c in question.get("choices", []):
        if c["label"] == message:
            return True, c["number"] if c["number"] is not None else AUTO
    return False, None
