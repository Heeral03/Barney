"""Memory Agent: short-term and long-term memory, as two LangGraph subgraphs around the requirements agent.

    memory_in :  recall --(hit)--> load          before: look up long-term memory, load matches into short-term
    memory_out:  commit -> shrink                after:  save what is worth keeping, trim + summarise the chat

- recall: semantic search (pgvector) over this user's long-term memories for something relevant to the request,
  plus the memories about the person themselves (name...), which apply to every search.
- load: the matches are loaded into short-term memory (`recalled`), where the requirements and presenting agents
  read them. Product-specific memories are only shown for that product (see `relevant_memories`).
- commit: saves what the requirements agent judged worth remembering (a durable fact about the shopper, never the
  details of one purchase). When the shopper accepts the recommendation, what they chose is saved too. No LLM call:
  the requirements agent already read the whole turn, so it decides, and a miss and a hit are treated alike.
  A fact that is already stored (same meaning) is updated in place, so corrections replace old values.
- shrink: keeps the chat history short. When it grows past TRIGGER messages the older ones are folded
  into a rolling `summary` and removed (trimming + summarising); the last KEEP stay verbatim.

Memory is never allowed to break a turn: if a step fails (rate limit, model error) it is logged and skipped.
"""
import logging
import re

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.store.base import BaseStore

from app.agents.common import as_memory, last_user_text
from app.commands import ACCEPT, is_command
from app.llm import llm, load_prompt
from app.memory import store as ltm
from app.memory import writer
from app import settings, wishlist
from app.state import chatState

log = logging.getLogger(__name__)

TRIGGER = 12  # summarise once the chat holds more than this many messages
KEEP = 6  # ...and keep this many of the newest verbatim
HARD_LIMIT = 30  # if summarising keeps failing, drop the oldest without a summary beyond this
MAX_LOADED = 8  # most long-term memories held in short-term memory at once
SUMMARY_PROMPT = load_prompt("barney_summary.txt")


def _user_id(config: RunnableConfig) -> str:
    return (config.get("configurable") or {}).get("user_id") or "anonymous"


def _memory_id(config: RunnableConfig) -> str:
    """Whose tastes this conversation reads and writes: the account's, or one of its profiles ("Mom", "Gift for Riya")."""
    return (config.get("configurable") or {}).get("memory_id") or _user_id(config)


# ------------------------------------------------------------------ before: long-term -> short-term
def recall_node(state: chatState, config: RunnableConfig, *, store: BaseStore) -> chatState:
    said = last_user_text(state["messages"])
    if not said or is_command(said):
        return {"fresh": [], "saved": []}  # a button press says nothing new; keep what was loaded earlier
    product = (state.get("profile") or {}).get("product") or ""
    uid, mid = _user_id(config), _memory_id(config)
    try:
        hits = ltm.recall(store, mid, f"{product.replace('_', ' ')} {said}".strip()) + ltm.about_the_person(store, mid)
    except Exception as e:
        log.warning("memory recall failed: %s", e)
        hits = []
    unique = {h["key"]: h for h in hits}.values()
    try:
        hearted = wishlist.recent(uid)
    except Exception as e:
        log.warning("wishlist load failed: %s", e)
        hearted = state.get("wishlist") or []
    return {"fresh": [{k: h.get(k) for k in ("text", "category", "kind")} for h in unique], "saved": [], "wishlist": hearted}


def route_after_recall(state: chatState) -> str:
    return "load" if state.get("fresh") else "__end__"


def load_node(state: chatState) -> chatState:
    """Put the memories the search matched into short-term memory, newest first, without duplicates."""
    merged: dict[str, dict] = {}
    for m in map(as_memory, [*state.get("fresh", []), *state.get("recalled", [])]):  # old threads hold strings
        merged.setdefault(m["text"], m)
    return {"recalled": list(merged.values())[:MAX_LOADED]}


# ------------------------------------------------------------------ after: save what is worth keeping
def commit_node(state: chatState, config: RunnableConfig, *, store: BaseStore) -> chatState:
    said = last_user_text(state["messages"])
    items: list[dict] = []
    if said in ACCEPT:  # the shopper chose: behaviour worth knowing (explicit, so no LLM is needed)
        profile, product = state.get("profile") or {}, ((state.get("profile") or {}).get("product") or "").replace("_", " ")
        pick = next((o for o in state.get("offers") or [] if o.get("number") == profile.get("pick")), None)
        if pick and product:
            items = [{"text": f"Picked {pick['title'][:60]} ({pick['price_display']}) as their {product}",
                      "category": product.split()[0].lower(), "kind": "preference"}]
    elif not is_command(said):
        items = (state.get("plan") or {}).get("remember") or []
    try:
        if not settings.learning_on(_user_id(config)):  # the shopper paused learning
            return {"saved": []}
        events = writer.save(store, _memory_id(config), items, source="inferred" if said in ACCEPT else "said")
    except Exception as e:  # includes Groq rate limits: skip saving this turn, don't fail the chat
        log.warning("memory commit failed: %s", e)
        return {}
    return {"saved": events}


# ------------------------------------------------------------------ short-term memory
def _transcript(messages: list) -> str:
    lines = []
    for m in messages:
        text = re.sub(r"\s+", " ", re.sub(r"[*_`#]", "", str(m.content))).strip()
        if isinstance(m, HumanMessage):
            lines.append(f"Shopper: {text[:400]}")
        elif isinstance(m, AIMessage) and text:
            lines.append(f"Barney: {text[:400]}")
    return "\n".join(lines)


def shrink_node(state: chatState) -> chatState:
    """Trim the chat history; fold what is dropped into the rolling summary."""
    msgs = state["messages"]
    if len(msgs) <= TRIGGER:
        return {}
    cut = len(msgs) - KEEP
    while cut > 0 and not isinstance(msgs[cut], HumanMessage):  # the kept part must start on a user message
        cut -= 1
    if cut <= 0:
        return {}
    dropped = msgs[:cut]
    remove = [RemoveMessage(id=m.id) for m in dropped if m.id]

    try:
        prompt = f"Previous summary:\n{state.get('summary') or '(none)'}\n\nOlder messages:\n{_transcript(dropped)}"
        summary = str(llm.invoke([SUMMARY_PROMPT, HumanMessage(content=prompt)]).content).strip()
    except Exception as e:
        log.warning("summarising failed: %s", e)
        # Keep the full history for now (it is still trimmed when the prompt is built), unless it is huge.
        return {"messages": remove} if len(msgs) > HARD_LIMIT else {}
    return {"summary": summary, "messages": remove}


# ------------------------------------------------------------------ the subgraphs
_in = StateGraph(chatState)
_in.add_node("recall", recall_node)
_in.add_node("load", load_node)
_in.add_edge(START, "recall")
_in.add_conditional_edges("recall", route_after_recall, {"load": "load", "__end__": END})
_in.add_edge("load", END)
memory_in = _in.compile()

_out = StateGraph(chatState)
_out.add_node("commit", commit_node)
_out.add_node("shrink", shrink_node)
_out.add_edge(START, "commit")
_out.add_edge("commit", "shrink")
_out.add_edge("shrink", END)
memory_out = _out.compile()
