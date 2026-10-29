"""Small helpers shared by the agents."""
import re
from datetime import date

from langchain_core.messages import AIMessage, HumanMessage

from app.commands import MAX_QUESTIONS


_SYNONYMS = {"colour": "color", "colours": "color", "colors": "color", "budget": "budget", "price": "budget", "cut": "fit"}


def topic_key(topic: str) -> str:
    """"Colour", "colors" and "color" are the same question; so are "price" and "budget"."""
    word = re.sub(r"[^a-z]", "", (topic or "").lower())
    return _SYNONYMS.get(word, word.rstrip("s"))


def answered_topics(profile: dict) -> set[str]:
    """Question topics that need no asking: already asked, or already known from the facts or the budget."""
    keys = {topic_key(t) for t in [*(profile.get("asked") or []), *(profile.get("facts") or {})]}
    if profile.get("budget_min") or profile.get("budget_max"):
        keys.add("budget")
    return keys


def next_attribute(profile: dict) -> dict | None:
    """The next product-specific question still worth asking, from the question plan the requirements agent wrote."""
    done = answered_topics(profile)
    return next((a for a in profile.get("attrs") or [] if topic_key(a["topic"]) not in done), None)


def last_user_text(messages: list) -> str:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return str(m.content).strip()
    return ""


def reply(text: str, options: list[str] | None = None, cards: list[dict] | None = None, **extra) -> dict:
    return {"messages": [AIMessage(content=text)], "options": options or [], "cards": cards or [], "table": None, **extra}


def _words(text: str) -> set:
    return {w.rstrip("s") for w in re.findall(r"[a-z0-9]+", (text or "").lower())}


def as_memory(m) -> dict:
    """A recalled memory as {"text", "category", ...}. Threads saved by older versions hold plain "text (category)" strings."""
    if isinstance(m, dict):
        return m
    found = re.match(r"^(.*) \(([^()]+)\)$", str(m).strip())
    return {"text": found.group(1), "category": found.group(2)} if found else {"text": str(m).strip(), "category": "general"}


def relevant_memories(recalled: list[dict] | None, product: str | None) -> list[dict]:
    """Memories about the person always apply; product ones only when they are about what is being bought.
    Without this, laptop habits would leak into a shoe search."""
    words = _words(product or "")
    return [
        m for m in map(as_memory, recalled or [])
        if not words or m.get("category") == "person" or (m.get("category") == "general" and "kind" not in m)  # old threads only
        or _words(m.get("category")) & words or _words(m.get("text")) & words
    ]


def _short(text: str, limit: int) -> str:
    """Cut at a word boundary, never mid-word."""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:-· ") + "…"


_PLAIN_TOPICS = {"gender", "type", "category", "product", "audience", "for"}


def _label(topic: str, value: str, product: str | None) -> str | None:
    topic = topic.replace("_", " ")
    """"High" + "rise" -> "High rise"; "women" stays "women"; the product's own name ("jeans") is not a requirement."""
    value = value.strip()
    if not value or "open to suggestions" in value or topic_key(topic) == "budget" or _words(value) <= _words(product or ""):
        return None
    if topic_key(topic) in _PLAIN_TOPICS or topic.lower() in value.lower() or len(value.split()) >= 3:
        return _short(value, 32)
    return _short(f"{value} {topic.lower()}", 32)


def budget_label(profile: dict) -> str | None:
    from app.tools.products import inr
    lo, hi = profile.get("budget_min"), profile.get("budget_max")
    return f"{inr(lo)} to {inr(hi)}" if lo and hi else f"under {inr(hi)}" if hi else f"over {inr(lo)}" if lo else None


def within_budget(profile: dict, price: float | None) -> str:
    """"yes" / "no" / "unknown", from the actual price. A fact we hold, so it is never left to a model to guess."""
    lo, hi = profile.get("budget_min"), profile.get("budget_max")
    if price is None or not (lo or hi):
        return "unknown"
    return "yes" if (hi is None or price <= hi) and (lo is None or price >= lo) else "no"


def requirement_labels(profile: dict, recalled: list[dict] | None = None, limit: int = 6) -> list[tuple[str, bool]]:
    """The shopper's explicit requirements as short labels, [(label, remembered)]: what they told us this time (answers,
    budget) plus what we remember about them for this kind of product. Shown to them and used to judge each option."""
    product = profile.get("product")
    labels: list[tuple[str, bool]] = []
    for topic, value in (profile.get("facts") or {}).items():
        label = _label(str(topic), str(value), product)
        if label and label.lower() not in [l.lower() for l, _ in labels]:
            labels.append((label, False))
    if budget_label(profile):
        labels.append((budget_label(profile), False))
    have = " ".join(label.lower() for label, _ in labels)
    for m in relevant_memories(recalled, product):
        text = m["text"].split(":")[-1].strip() if "preference for" in m["text"] else m["text"]
        if m.get("kind") != "dislike" and text and text.lower() not in have:
            labels.append((_short(text, 40), True))
    return labels[:limit]


def matched_on_text(profile: dict, recalled: list[dict] | None = None) -> str:
    """"Matched on: straight · high rise · under ₹1,500 · 🧠 Wears size 5": the shopper's context, made explicit."""
    labels = requirement_labels(profile, recalled)
    if not labels:
        return ""
    return "**Matched on:** " + " · ".join(("🧠 " if remembered else "") + label for label, remembered in labels)


def requirements_text(profile: dict) -> str:
    """The shopper's requirements as plain lines, for the prompts."""
    lo, hi = profile.get("budget_min"), profile.get("budget_max")
    lines = [f"Product: {profile.get('product') or 'unknown'}"]
    if lo or hi:
        lines.append(f"Budget: {lo or 0} to {hi or 'no limit'} rupees")
    lines += [f"{k}: {v}" for k, v in (profile.get("facts") or {}).items()]
    return "\n".join(lines)


def remembered_text(recalled: list[dict] | None, product: str | None = None) -> str:
    mems = relevant_memories(recalled, product)
    if not mems:
        return ""
    return "What you remember about this shopper from earlier chats:\n" + "\n".join(f"- {m['text']}" for m in mems)


def question_plan_text(profile: dict) -> str:
    if not profile.get("attrs"):
        return ""
    done, facts = answered_topics(profile), {topic_key(k): v for k, v in (profile.get("facts") or {}).items()}
    lines = [f"- {a['topic']}: " + (f"answered ({facts.get(topic_key(a['topic']), 'asked')})" if topic_key(a["topic"]) in done else "NOT YET ASKED")
             for a in profile["attrs"]]
    return "Question plan for this product:\n" + "\n".join(lines)


def wishlist_text(wishlist: list[dict] | None, product: str | None) -> str:
    """Things the shopper hearted for this kind of product: what they like the look of."""
    words = _words(product or "")
    items = [w for w in wishlist or [] if not words or _words(w.get("product")) & words or _words(w.get("title")) & words][:5]
    if not items:
        return ""
    return "Saved to their wishlist (what they like the look of):\n" + "\n".join(f"- {w['title'][:90]}" for w in items)


def shortlist_text(offers: list[dict] | None, shown: list[int] | None, pick: int | None) -> str:
    """The listings found so far, compactly, so the agent can answer "which is lighter?" or know what "cheaper" means."""
    if not offers:
        return ""
    shown = set(shown or [])
    lines = [
        f"#{o['number']}{' (recommended)' if o['number'] == pick else ' (shown)' if o['number'] in shown else ''}: "
        f"{o['title'][:70]} | {o['price_display']} | rating {o.get('rating') or 'none'} ({o.get('rating_count') or 0})"
        for o in offers[:12]
    ]
    return "Listings found so far:\n" + "\n".join(lines)


def known_text(profile: dict, summary: str = "", recalled: list[dict] | None = None,
               offers: list[dict] | None = None, shown: list[int] | None = None, wishlist: list[dict] | None = None) -> str:
    """Everything the requirements agent already knows, so it never asks for it again."""
    today = f"Today's date: {date.today().isoformat()}. Shoppers want what is current: the newest generation of every product.\n\n"
    if not profile:
        known = today + "Known so far: nothing yet."
    else:
        asked = profile.get("asked") or []
        known = today + "Known so far:\n" + requirements_text(profile) + (
            f"\nQuestions already asked ({len(asked)} of {MAX_QUESTIONS} max): {', '.join(asked) or 'none'}"
        )
    for block in (
        question_plan_text(profile or {}),
        shortlist_text(offers, shown, (profile or {}).get("pick")),
        f"Conversation so far (summary of older messages):\n{summary}" if summary else "",
        remembered_text(recalled, (profile or {}).get("product")),
        wishlist_text(wishlist, (profile or {}).get("product")),
    ):
        if block:
            known += "\n\n" + block
    return known
