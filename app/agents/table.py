"""Side-by-side comparison: the options the shopper has seen, with specifications normalised across them, how each
one matches what the shopper told us, the verified price and the seller. This is the decision-ready view: nothing to
open in other tabs, and every buy link goes to the original seller."""
from typing import Optional

from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field, field_validator

from app.agents.common import budget_label, remembered_text, reply, requirement_labels, requirements_text, within_budget
from app.agents.presenter import _listing_text, _merge, prepare_all
from app.commands import ACCEPT, CHANGE, SHOW_ALTERNATIVES
from app.llm import Structured, load_prompt
from app.state import chatState

PROMPT = load_prompt("barney_table.txt")
MAX_OPTIONS = 5
MATCH = {"yes", "no", "unknown"}


class Row(BaseModel):
    number: int
    values: dict[str, Optional[str]] = Field(default_factory=dict)
    matches: dict[str, str] = Field(default_factory=dict)

    @field_validator("values", mode="before")
    @classmethod
    def _values(cls, v):
        return {str(k): (str(x).strip() or None) if x is not None else None for k, x in (v or {}).items()}

    @field_validator("matches", mode="before")
    @classmethod
    def _matches(cls, v):
        return {str(k): (str(x).strip().lower() if str(x).strip().lower() in MATCH else "unknown") for k, x in (v or {}).items()}


class SpecTable(BaseModel):
    specs: list[str] = Field(default_factory=list)
    rows: list[Row] = Field(default_factory=list)
    verdict: str = ""

    @field_validator("specs", "rows", mode="before")
    @classmethod
    def _none(cls, v):
        return v or []

    @field_validator("verdict", mode="before")
    @classmethod
    def _text(cls, v):
        return (v or "").strip()


extractor = Structured(
    SpecTable,
    '{"specs":["RAM","Storage"],"rows":[{"number":1,"values":{"RAM":"16GB","Storage":null},"matches":{"<requirement label>":"yes|no|unknown"}}],"verdict":""}',
)


def compare_node(state: chatState) -> chatState:
    profile = dict(state.get("profile") or {})
    offers = list(state.get("offers") or [])
    shown = set(state.get("shown") or [])
    seen = [o for o in offers if o["number"] in shown]
    options = (seen if len(seen) >= 2 else offers)[:MAX_OPTIONS]
    if len(options) < 2:
        return reply("I need at least two options to put side by side.", route="end", profile=profile)

    options = prepare_all(options)  # pictures, plus every store's price and a link to each seller
    pick = profile.get("pick")
    labels = [label for label, _ in requirement_labels(profile, state.get("recalled"))]
    money = budget_label(profile)
    context = "\n\n".join(p for p in (
        requirements_text(profile), remembered_text(state.get("recalled"), profile.get("product")),
        "Requirement labels (use these exact strings as keys in \"matches\"): " + (" | ".join(labels) or "none"),
        f"Barney's current recommendation is #{pick}." if pick else "",
        "Listings:\n" + _listing_text(options)) if p)
    result: SpecTable = extractor.invoke([PROMPT, SystemMessage(content=context)])
    by_number = {r.number: r for r in result.rows}

    rows = []
    for o in options:
        r = by_number.get(o["number"]) or Row(number=o["number"])
        rows.append({
            "number": o["number"], "title": o["title"], "image_url": o.get("image_url"), "best": o["number"] == pick,
            "price_inr": o.get("price_inr"), "price_display": o["price_display"], "price_verified": bool(o.get("price_verified")), "seller": o["seller"],
            "seller_trusted": o.get("seller_trusted", True), "link": o.get("link"), "token": o.get("token"),
            "stores": [{k: s.get(k) for k in ("name", "price_display", "link", "trusted", "verified")} for s in (o.get("stores") or [])[:4]],
            "rating": o.get("rating"), "rating_count": o.get("rating_count"),
            "values": {spec: r.values.get(spec) for spec in result.specs[:6]},
            # the budget is a fact about the real price, so it is computed here, never guessed from a title
            "matches": {label: (within_budget(profile, o.get("price_inr")) if label == money else r.matches.get(label, "unknown"))
                        for label in labels},
        })
    table = {"specs": result.specs[:6], "requirements": labels, "rows": rows}
    text = result.verdict or "Here they are side by side."
    return reply(text, [ACCEPT[1], SHOW_ALTERNATIVES, CHANGE], table=table, profile=profile,
                 offers=_merge(offers, options), route="end")
