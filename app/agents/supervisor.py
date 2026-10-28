"""Supervisor: routes each turn. No LLM, so it costs nothing and behaves the same every time.

Button presses are commands and are handled here. For everything else it takes the requirements agent's
proposal (`plan`) and applies the rules that keep the conversation natural and fast:
  - understand first: before the first results it asks the next unanswered attribute of the product's question plan,
    one tappable question at a time, at most MAX_QUESTIONS_BEFORE_RESULTS of them, and stops as soon as the shopper
    says "just show me" (`skip`);
  - never more than MAX_QUESTIONS in total, and never the same question topic twice;
  - never search before a product is known;
  - "other options" reuses what was already found (the `more` node), and only searches again when that runs out.
"""
import re

from app.agents.common import last_user_text, next_attribute, reply
from app.commands import (
    ACCEPT, BROADEN, CHANGE, MAX_QUESTIONS, MAX_QUESTIONS_BEFORE_RESULTS, NOT_SURE, RAISE_BUDGET, RESTART,
    COMPARE, SHOW_ALTERNATIVES, SKIP,
)
from app.state import chatState


def _research(profile: dict, queries: list[str], mode: str = "new") -> dict:
    return {"profile": profile, "search": {"queries": queries, "mode": mode}, "options": [], "cards": [], "route": "research"}


def _command(said: str, state: chatState) -> dict | None:
    profile = dict(state.get("profile") or {})
    product = profile.get("product")
    if said == SHOW_ALTERNATIVES:
        if state.get("offers"):
            return {"options": [], "cards": [], "route": "more"}
        if product:  # nothing found yet, so there is nothing to compare: look now
            return _research(profile, [product])
        return reply("I haven't shown you anything yet. What are you looking to buy?", route="end")
    if said == COMPARE:
        return _compare(state)
    if said in ACCEPT:
        return reply("Great choice! 🙌 Tap **View** on the card to open it, and double-check the seller and "
                     "variant on the page. Anything else I can help you find?", ["Find something else"], route="end")
    if said in RESTART:
        return reply("Sure, fresh start! What are you looking to buy?", profile={}, offers=[], reserve=[], shown=[],
                     summary="", route="end")
    if said == BROADEN:
        return _research(profile, [product or ""], "more")
    if said.startswith(RAISE_BUDGET):
        profile["budget_max"] = int(re.sub(r"\D", "", said[len(RAISE_BUDGET):]) or 0) or profile.get("budget_max")
        return _research(profile, (state.get("search") or {}).get("queries") or [product or ""], "refine")
    if said == CHANGE:
        return reply("No problem! What would you like to change?",
                     ["Budget", "Brand", "Key features", "How I'll use it"], route="end")
    return None


def _compare(state: chatState) -> dict:
    if len(state.get("offers") or []) >= 2:
        return {"options": [], "cards": [], "route": "compare"}
    return reply("I need at least two options to put side by side. Tell me what you're after and I'll find some.", route="end")


def _first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!])\s", text.strip(), maxsplit=1)[0]


def supervisor_node(state: chatState) -> chatState:
    said = last_user_text(state["messages"])
    handled = _command(said, state)
    if handled is not None:
        return handled

    plan = state.get("plan") or {}
    profile = dict(state.get("profile") or {})
    offers = state.get("offers") or []
    queries = [q for q in plan.get("queries") or [] if q]
    question, topic = plan.get("question") or "", plan.get("question_topic") or ""
    asked = profile.get("asked") or []
    mode = plan.get("mode") or "new"
    if mode == "more" and not offers:
        mode = "new"

    intent = plan.get("decision") or "chat"
    message = (plan.get("message") or "").strip()
    if intent == "compare":
        return _compare(state)
    if intent == "alternatives":
        if queries:
            intent = "search"  # a concrete change ("cheaper", "other brand") needs fresh results
        elif not offers:
            intent = "search"

    # Understand first: with no results yet, walk through the product's question plan before searching.
    attribute = next_attribute(profile)
    if intent in ("ask", "search") and profile.get("product") and not offers and not profile.get("skip") \
            and attribute and len(asked) < MAX_QUESTIONS_BEFORE_RESULTS:
        question, topic = attribute["question"], attribute["topic"]
        plan = {**plan, "options": attribute.get("options") or [], "durable": attribute.get("durable", False)}
        intent = "ask"
    elif intent == "ask" and (not question or len(asked) >= MAX_QUESTIONS or (topic and topic in asked)):
        intent = "search"  # out of questions, or the model repeated one
    if intent in ("ask", "search") and not profile.get("product"):
        intent = "chat"

    if intent == "ask":
        profile["asked"] = [*asked, topic or question[:30]]
        options = [o for o in plan.get("options") or [] if o and o.lower() != "other"][:5]
        profile["pending"] = {"topic": topic or question[:30], "options": options, "durable": bool(plan.get("durable"))}
        chips = [*options, NOT_SURE] + ([SKIP] if asked else [])  # a way out from the second question on
        lead = "" if "?" in message else _first_sentence(message)
        return reply(f"{lead}\n\n**{question}**".strip(), chips, profile=profile, route="end")
    profile.pop("pending", None)  # whatever was asked last is moot once we search or chat
    if intent == "search":
        return _research(profile, queries or [profile["product"]], mode)
    if intent == "alternatives":
        return {"profile": profile, "options": [], "cards": [], "route": "more"}
    options = [SHOW_ALTERNATIVES, ACCEPT[1]] if offers else []  # keep the conversation moving after an answer
    return reply(message or "Hey! 👋 I'm Barney. What are you looking to buy today?", options, profile=profile, route="end")


def route_after_supervisor(state: chatState) -> str:
    return {"research": "plan_research", "more": "more", "compare": "compare"}.get(state.get("route"), "__end__")
