"""Fit check: one model call that reads the shortlist against what the shopper asked for and removes what clearly does not fit.

This replaces judging relevance with hand-written rules per product category. The curator's own filters (budget, junk prices,
old model years, audience, plugs) stay as a cheap first pass and as the fallback when the model is unavailable: a rate limit
or a bad answer never blocks a turn, it just means this pass is skipped.

Only listings that have not been checked yet are sent (`fit_checked`), and at most CHECK_LIMIT of them per search, so a
"more options" request costs one small call and a repeat of the same listings costs none.
"""
import logging
from datetime import date

from langchain_core.messages import SystemMessage
from pydantic import BaseModel, field_validator

from app.agents.common import remembered_text, requirements_text
from app.llm import Structured, load_prompt
from app.state import chatState

log = logging.getLogger(__name__)

PROMPT = load_prompt("barney_specfit.txt")
CHECK_LIMIT = 12
MIN_KEPT = 2  # if the check would leave fewer than this, it is not trusted and nothing is removed


class Verdict(BaseModel):
    number: int
    fits: bool = True
    why: str = ""

    @field_validator("why", mode="before")
    @classmethod
    def _text(cls, v):
        return str(v or "").strip()


class Verdicts(BaseModel):
    verdicts: list[Verdict] = []

    @field_validator("verdicts", mode="before")
    @classmethod
    def _list(cls, v):
        return v or []


checker = Structured(Verdicts, '{"verdicts":[{"number":1,"fits":true,"why":""}]}', attempts=2)


def _lines(offers: list[dict]) -> str:
    return "\n".join(f"{o['number']}. {o['title'][:140]} | {o.get('price_display') or ''} | {o.get('seller') or ''}" for o in offers)


def spec_check_node(state: chatState) -> chatState:
    offers = list(state.get("offers") or [])
    todo = [o for o in offers if not o.get("fit_checked")][:CHECK_LIMIT]
    profile = state.get("profile") or {}
    if not todo or not profile.get("product"):
        return {"offers": offers}
    context = "\n\n".join(p for p in (
        f"Today's date: {date.today().isoformat()}.", requirements_text(profile),
        remembered_text(state.get("recalled"), profile.get("product")), "Listings:\n" + _lines(todo)) if p)
    try:
        result = checker.invoke([PROMPT, SystemMessage(content=context)])
    except Exception as e:  # includes rate limits: the curator's own filters already ran, so carry on without this pass
        log.warning("fit check skipped: %s: %s", type(e).__name__, str(e)[:160])
        return {"offers": offers}

    failed = {v.number for v in result.verdicts if not v.fits}
    checked = {o["number"] for o in todo}
    if len(checked - failed) < MIN_KEPT:  # it would wipe the list out: more likely the check is wrong than every result
        failed = set()
    if failed:
        log.info("fit check removed %s", {v.number: v.why for v in result.verdicts if not v.fits})
    kept = [{**o, "fit_checked": True} if o["number"] in checked else o for o in offers if o["number"] not in failed]
    return {"offers": kept}
