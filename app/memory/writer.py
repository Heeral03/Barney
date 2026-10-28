"""The write side of long-term memory: filters what the requirements agent wants remembered, then saves it."""
import logging
import re

from app.memory.store import remember

log = logging.getLogger(__name__)

MAX_PER_TURN = 2
_SENSITIVE = re.compile(r"@|\d{8,}|\bpassword\b|\bcvv\b", re.I)
KINDS = ("profile", "preference", "dislike", "constraint")


def clean(items: list[dict]) -> list[dict]:
    """Keep short, non-sensitive statements. Anything about one purchase belongs in the profile, not here."""
    out = []
    for m in items or []:
        text = str(m.get("text") or "").strip()
        if len(text.split()) < 2 or len(text) > 140 or _SENSITIVE.search(text):  # a full statement, not a bare word
            continue
        category = (str(m.get("category") or "general").strip().lower().split() or ["general"])[0]
        kind = m.get("kind") if m.get("kind") in KINDS else "preference"
        out.append({"text": text, "category": category, "kind": kind, "key": m.get("key") or None})
    return out[:MAX_PER_TURN]


def save(store, user_id: str, items: list[dict]) -> list[str]:
    """Save each memory (or update the one that says the same thing). Returns events like "Saved: Wears size 5"."""
    events = []
    for m in clean(items):
        action, _ = remember(store, user_id, m["text"], m["category"], m["kind"], m["key"])
        if action == "unchanged":
            continue
        events.append(f"{'Saved' if action == 'added' else 'Updated'}: {m['text']}")
    return events
