"""Requirements Agent: understands what the shopper wants. One LLM call per turn, none for button presses.

It reads the latest message together with the conversation summary, the profile built so far, the long-term
memories loaded by the memory agent and the wishlist, then:
  - updates the profile (product, budget, facts), starting fresh when the shopper moves to a different product;
  - the first time it sees a product, writes the question plan: the few attributes that decide which products are
    right for THIS kind of product (jeans: fit, rise, colour, occasion, budget...), each with tappable answers;
  - proposes what to do next (`plan`): chat, ask, search, or show alternatives.

A tapped answer to the question just asked is recorded without calling the model at all.

It also says what, if anything, is worth remembering about the shopper (`remember`); the memory agent saves it.
It only proposes. The supervisor applies the guards (question budget, no repeated questions) and routes.
"""
import logging
import re
from typing import Literal, Optional

from groq import RateLimitError
from langchain_core.messages import SystemMessage, trim_messages
from langchain_core.runnables import RunnableConfig
from langgraph.store.base import BaseStore
from langchain_core.messages.utils import count_tokens_approximately
from pydantic import BaseModel, Field, field_validator

from app.agents.smalltalk import is_small_talk, small_talk_reply
from app.agents.common import answered_topics, known_text, last_user_text, next_attribute, topic_key
from app.commands import MAX_QUESTIONS_BEFORE_RESULTS, NOT_SURE, SKIP, is_command
from app.memory import store as ltm_store
from app.llm import Structured, load_prompt, prose_from_error
from app.state import chatState
from app.tools.products import parse_budget

PROMPT = load_prompt("barney_requirements.txt")
log = logging.getLogger(__name__)


class Fact(BaseModel):
    topic: str
    value: str


class Remember(BaseModel):
    text: str
    category: str = "general"
    kind: str = "preference"
    key: Optional[str] = None  # set for answers to the question plan: one slot per topic, never merged with others

    @field_validator("category", "kind", mode="before")
    @classmethod
    def _none_to_str(cls, v):
        return v or ""


class Attribute(BaseModel):
    topic: str
    question: str
    options: list[str] = Field(default_factory=list)
    durable: bool = False  # a lasting taste (fit, colour, brand...) worth remembering; false for occasion, budget...

    @field_validator("options", mode="before")
    @classmethod
    def _options(cls, v):
        return [str(o).strip() for o in (v or []) if str(o).strip() and str(o).strip().lower() != "other"][:6]

    @field_validator("durable", mode="before")
    @classmethod
    def _durable(cls, v):
        return bool(v)


class Plan(BaseModel):
    decision: Literal["chat", "ask", "search", "alternatives", "compare"]
    message: str = ""
    product: Optional[str] = None
    restart: bool = False
    facts: list[Fact] = Field(default_factory=list)
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    question: str = ""
    question_topic: str = ""
    options: list[str] = Field(default_factory=list)
    queries: list[str] = Field(default_factory=list)
    mode: Literal["new", "refine", "more"] = "new"
    remember: list[Remember] = Field(default_factory=list)
    attributes: list[Attribute] = Field(default_factory=list)
    skip: bool = False  # the shopper wants results now ("just show me", "you decide")

    # The model sends null for "empty"; treat that as the default.
    @field_validator("message", "question", "question_topic", mode="before")
    @classmethod
    def _none_to_str(cls, v):
        return "" if v is None else v

    @field_validator("mode", mode="before")
    @classmethod
    def _mode(cls, v):
        return v if v in ("new", "refine", "more") else "new"

    @field_validator("facts", "options", "queries", "remember", "attributes", mode="before")
    @classmethod
    def _none_to_list(cls, v):
        return [] if v is None else v

    @field_validator("restart", "skip", mode="before")
    @classmethod
    def _none_to_false(cls, v):
        return bool(v)


decider = Structured(
    Plan,
    '{"decision":"chat|ask|search|alternatives|compare","message":"","product":null,"restart":false,'
    '"facts":[{"topic":"","value":""}],"budget_min":null,"budget_max":null,"question":"",'
    '"question_topic":"","options":[""],"queries":[""],"mode":"new|refine|more",'
    '"remember":[{"text":"","category":"","kind":"profile|preference|dislike|constraint"}],'
    '"attributes":[{"topic":"","question":"","options":[""],"durable":true}],"skip":false}',
)


def same_product(a: str, b: str) -> bool:
    """Loose match: "macbook" vs "MacBook Pro laptop" is the same purchase, "macbook" vs "bamboo t-shirt" is not."""
    words = lambda t: {w.rstrip("s") for w in re.findall(r"[a-z0-9]+", t.lower())}
    return bool(words(a) & words(b))


def apply_plan(profile: dict, d: Plan) -> tuple[dict, bool]:
    """The profile after this turn's answer. Returns (profile, restarted)."""
    profile = dict(profile)
    restart = d.restart or bool(d.product and profile.get("product") and not same_product(d.product, profile["product"]))
    if restart:  # budget and facts for a MacBook must not leak into a T-shirt search
        profile = {}
    if d.product:
        profile["product"] = d.product
    facts = dict(profile.get("facts") or {})
    facts.update({f.topic: f.value for f in d.facts if f.topic and f.value})
    profile["facts"] = facts
    if d.budget_min is not None:
        profile["budget_min"] = d.budget_min
    if d.budget_max is not None:
        profile["budget_max"] = d.budget_max
    lo, hi = profile.get("budget_min"), profile.get("budget_max")
    if lo and hi and lo >= hi:
        profile.pop("budget_min")  # "around ₹2,000" is a ceiling, not "exactly ₹2,000"
    if d.attributes and not profile.get("attrs"):  # the question plan is written once per product
        profile["attrs"] = [a.model_dump() for a in d.attributes][:6]
    if d.skip:
        profile["skip"] = True
    return profile, restart


def record_answer(profile: dict, said: str) -> tuple[dict, list[dict]]:
    """Store the shopper's answer to the question we just asked. Returns (profile, memories worth keeping)."""
    profile = dict(profile)
    pending = profile.pop("pending", None) or {}
    topic = pending.get("topic")
    if not topic:
        return profile, []
    facts = dict(profile.get("facts") or {})
    if said == SKIP:
        profile["skip"] = True
        return profile, []
    if said == NOT_SURE:
        facts[topic] = "open to suggestions"
        profile["facts"] = facts
        return profile, []
    if topic_key(topic) == "budget":
        lo, hi = parse_budget(said)
        if lo is not None:
            profile["budget_min"] = lo
        if hi is not None:
            profile["budget_max"] = hi
    else:
        facts[topic] = said[:80]
    profile["facts"] = facts
    memories = []
    product = (profile.get("product") or "").replace("_", " ")
    if pending.get("durable") and product:  # a lasting taste, so it is saved without asking the model
        memories = [{"text": f"{topic.capitalize()} preference for {product}: {said[:60]}",
                     "category": product.split()[-1].lower(), "kind": "preference",
                     "key": f"pref:{product.split()[-1].lower()}:{topic_key(topic)}"}]  # one slot per question
    return profile, memories


def remembered_slots(store: BaseStore, user_id: str, product: str) -> dict[str, str]:
    """What this shopper told Barney last time about this kind of product: {topic key: answer}, from the saved slots."""
    prefix = f"pref:{product.replace('_', ' ').split()[-1].lower()}:"
    return {m["key"][len(prefix):]: m["text"].split(": ", 1)[-1]
            for m in ltm_store.all_memories(store, user_id) if m["key"].startswith(prefix)}


def prefill_from_memory(profile: dict, slots: dict[str, str]) -> dict:
    """Answer the question plan from memory: anything they already told us about this product is applied (never asked
    again), unless this message already answered it. `from_memory` records what was used so Barney can say so."""
    profile = dict(profile)
    facts, used, done = dict(profile.get("facts") or {}), {}, answered_topics(profile)
    for a in profile.get("attrs") or []:
        key = topic_key(a["topic"])
        if key in slots and key not in done:
            facts[a["topic"]] = used[a["topic"]] = slots[key]
    profile["facts"], profile["prefilled"] = facts, True
    if used:
        profile["from_memory"] = used
    return profile


def record_form(profile: dict, answers: dict) -> tuple[dict, list[dict]]:
    """Store a submitted questionnaire: {topic: [values]}. Returns (profile, memories worth keeping)."""
    profile = dict(profile)
    pending = profile.pop("pending", None) or {}
    durable = {topic_key(q["topic"]) for q in pending.get("questions", []) if q.get("durable")}
    facts = dict(profile.get("facts") or {})
    product = (profile.get("product") or "").replace("_", " ")
    memories = []
    for topic, values in answers.items():
        values = [str(v).strip()[:80] for v in values or [] if str(v).strip()]
        if not values:
            continue
        if topic_key(topic) == "budget":
            bands = [parse_budget(v) for v in values]
            lows, highs = [b[0] for b in bands if b[0] is not None], [b[1] for b in bands if b[1] is not None]
            if lows and len(lows) == len(bands):
                profile["budget_min"] = min(lows)
            if highs and len(highs) == len(bands):
                profile["budget_max"] = max(highs)
            continue
        value = ", ".join(values)
        facts[topic] = value
        if topic_key(topic) in durable and product:
            memories.append({"text": f"{topic.capitalize()} preference for {product}: {value[:60]}",
                             "category": product.split()[-1].lower(), "kind": "preference",
                             "key": f"pref:{product.split()[-1].lower()}:{topic_key(topic)}"})
    profile["facts"] = facts
    return profile, memories


def requirements_node(state: chatState, config: RunnableConfig | None = None, *, store: BaseStore | None = None) -> chatState:
    said = last_user_text(state["messages"])
    if is_command(said):
        return {"plan": {}, "table": None}  # a button says nothing new about the requirements

    profile = dict(state.get("profile") or {})
    pending = profile.get("pending") or {}
    kept: list[dict] = []
    if pending.get("form") and state.get("answers"):
        # The shopper filled in the questionnaire: everything is recorded at once. The model is still called below,
        # but only to write good search queries from the complete picture.
        profile, kept = record_form(profile, state["answers"])
    elif pending.get("form") and said == SKIP:
        profile.pop("pending", None)
        profile["skip"] = True
    elif pending and (said in pending.get("options", []) or said in (NOT_SURE, SKIP)):
        # A tapped answer: record it. If more questions are due, no model call is needed at all.
        profile, kept = record_answer(profile, said)
        more = next_attribute(profile)
        if more and not profile.get("skip") and not state.get("offers") \
                and len(profile.get("asked") or []) < MAX_QUESTIONS_BEFORE_RESULTS:
            return {"profile": profile, "plan": {"decision": "ask", "remember": kept}, "table": None}

    if not profile.get("pending") and is_small_talk(said):
        # "hey", "thanks": one plain, fast chat call, not the shopping pipeline
        return {"profile": profile, "table": None,
                "plan": {"decision": "chat", "message": small_talk_reply(said, profile, state.get("recalled"))}}

    # Trimming: the memory agent already folds old turns into `summary`; this caps what is sent regardless.
    recent = trim_messages(
        state["messages"], strategy="last", max_tokens=1800, token_counter=count_tokens_approximately,
        start_on="human", include_system=False,
    )
    known = known_text(profile, state.get("summary") or "", state.get("recalled"),
                       state.get("offers"), state.get("shown"), state.get("wishlist"))
    prompt = [PROMPT, SystemMessage(content=known)] + recent
    try:
        d: Plan = decider.invoke(prompt)
    except RateLimitError:
        raise  # the app tells the shopper to wait; another attempt would only burn more of the quota
    except Exception as e:  # the model kept answering outside JSON: if it spoke plainly, that is the reply; else apologise
        log.warning("requirements model failed: %s: %s", type(e).__name__, str(e)[:200])
        said_plainly = prose_from_error(e)
        return {"profile": profile, "table": None, "plan": {"decision": "chat", "message": said_plainly or
                "Sorry, I lost my train of thought for a second. Could you say that again?"}}
    if d.decision != "chat" and not d.product and not profile.get("product"):
        # Asking or searching needs a product; the model sometimes forgets to name it. One nudge, not a loop.
        d = decider.invoke(prompt + [SystemMessage(content="Your answer left `product` null. Name the product now.")])

    if d.budget_min is None and d.budget_max is None:  # the model often leaves a stated budget out
        d.budget_min, d.budget_max = parse_budget(said)

    profile, restarted = apply_plan(profile, d)
    if store is not None and profile.get("product") and profile.get("attrs") and not profile.get("prefilled"):
        try:  # their earlier answers for this kind of product apply from the start
            cfg = (config or {}).get("configurable") or {}
            uid = cfg.get("memory_id") or cfg.get("user_id") or "anonymous"
            profile = prefill_from_memory(profile, remembered_slots(store, uid, profile["product"]))
        except Exception as e:
            log.warning("could not apply remembered preferences: %s", e)
    if restarted:
        kept = []
    elif profile.get("pending") and d.decision in ("ask", "search") and not any(
            topic_key(profile["pending"].get("topic")) == topic_key(f.topic) for f in d.facts):
        # They answered in their own words and the model did not file it under the question we asked.
        profile, kept = record_answer(profile, said)
    plan = d.model_dump()
    plan["remember"] = [*plan["remember"], *kept]
    update = {"profile": profile, "plan": plan, "table": None}
    if restarted:
        update["offers"] = []
    return update
