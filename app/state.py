from typing import Annotated, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


RESET = [{"__reset__": True}]  # return this for `raw_offers` to empty it


def collect(old: list[dict] | None, new: list[dict]) -> list[dict]:
    """Reducer for `raw_offers`: parallel research workers each append their listings; RESET empties it."""
    if new and new[0].get("__reset__"):
        return []
    return (old or []) + new


class chatState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    # What Barney has learned so far: {"product", "facts": {topic: value}, "asked": [topics],
    # "budget_min", "budget_max"}. Persisted per thread so he never re-asks.
    profile: dict
    # The requirements agent's proposal for this turn (decision, question, queries...). The supervisor applies it.
    plan: dict
    # Set by the supervisor when it hands off to research: {"queries": [...]}.
    search: dict
    # Parallel research: each worker appends its listings to `raw_offers`; the curator consumes and clears it.
    # `wave` is 1 for the first fan-out and 2 if the fallback sources were needed; `next_tasks` is what to fan out next.
    raw_offers: Annotated[list[dict], collect]
    wave: int
    next_tasks: list[dict]
    # Every listing curated so far, numbered. Kept so "other options" needs no second search.
    offers: list[dict]
    # Ranked listings not yet numbered or shown: "more options" draws from here before searching again.
    reserve: list[dict]
    # Numbers of the offers already shown to the shopper as cards.
    shown: list[int]
    # {"raw": n, "cheapest": price} from the last search, used to explain empty results.
    search_meta: dict
    # Short-term memory: a rolling summary of the older messages that were trimmed from `messages`.
    summary: str
    # Short-term memory: long-term memories loaded into this thread because they matched a query.
    # Accumulates across turns (newest first, capped) so a short follow-up like "S" keeps its context.
    recalled: list[dict]  # {"text", "category", "kind"}
    # What the semantic search matched on this turn only; decides between loading and learning.
    fresh: list[dict]
    # What was saved or updated in long-term memory this turn. Overwritten every turn.
    saved: list[str]
    # Things the shopper saved to their wishlist (title, product), most recent first: a signal of their taste.
    wishlist: list[dict]
    # The side-by-side comparison shown this turn (None otherwise): normalized specs, how each option matches the shopper's needs.
    table: Optional[dict]
    # Per-turn output for the UI. Overwritten on every turn.
    options: list[str]
    cards: list[dict]
    route: Optional[str]
