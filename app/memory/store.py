"""Long-term memory (LTM): what Barney remembers about a shopper across chats.

Backed by LangGraph's PostgresStore with a pgvector index, so `search(query=...)` is a semantic search.
One namespace per user: ("memories", user_id). Each item:
    {"text": "Wears size S in tops", "category": "clothing", "kind": "profile",
     "search_text": "clothing: Wears size S in tops", "created_at": ..., "updated_at": ..., "revisions": 0}
"""
import time
import uuid

from langgraph.store.base import BaseStore
from langgraph.store.postgres import PostgresStore

from app.db import pool
from app.memory.embeddings import DIMS, embed

RECALL_MIN_SCORE = 0.15  # below this a memory is not about the current request (loose: the agent filters further)
SAME_FACT_SCORE = 0.85  # above this a new memory is the same fact restated or corrected, so it replaces

# pgvector does the semantic search; "cosine" keeps `score` a cosine similarity, so the thresholds above hold.
ltm = PostgresStore(pool, index={"dims": DIMS, "embed": embed, "fields": ["search_text"], "distance_type": "cosine"})
ltm.setup()  # creates the store tables and the pgvector extension on first run


def _ns(user_id: str) -> tuple:
    return ("memories", user_id or "anonymous")


def recall(store: BaseStore, user_id: str, query: str, k: int = 6) -> list[dict]:
    """The memories most similar to `query` that are relevant enough to use."""
    if not query.strip():
        return []
    hits = store.search(_ns(user_id), query=query, limit=k)
    return [{"key": h.key, **h.value, "score": h.score} for h in hits if (h.score or 0) >= RECALL_MIN_SCORE]


def about_the_person(store: BaseStore, user_id: str, k: int = 4) -> list[dict]:
    """Memories about the shopper themselves (name, who they shop for...). They apply to every search."""
    hits = store.search(_ns(user_id), filter={"category": "person"}, limit=k)
    return [{"key": h.key, **h.value} for h in hits]


def remember(store: BaseStore, user_id: str, text: str, category: str = "general", kind: str = "preference",
             key: str | None = None, source: str = "said") -> tuple[str, str]:
    """Save a memory, or update the existing one if it is the same fact. Returns ("added" | "updated" | "unchanged", key)."""
    search_text = f"{category}: {text}"
    now = time.time()
    if key:  # a fixed slot (one per question topic): the answer replaces the old one, and nothing else is touched
        old = store.get(_ns(user_id), key)
        if old and old.value.get("text", "").strip().lower() == text.strip().lower():
            return "unchanged", key
        store.put(_ns(user_id), key, {
            "text": text, "category": category, "kind": kind, "search_text": search_text, "source": source,
            "created_at": old.value.get("created_at", now) if old else now, "updated_at": now,
            "revisions": old.value.get("revisions", 0) + 1 if old else 0,
        })
        return ("updated" if old else "added"), key
    near = store.search(_ns(user_id), query=search_text, limit=1)
    if near and (near[0].score or 0) >= SAME_FACT_SCORE:
        old = near[0]
        if old.value.get("text", "").strip().lower() == text.strip().lower():
            return "unchanged", old.key  # already known: no write, nothing to report
        store.put(_ns(user_id), old.key, {
            **old.value, "text": text, "category": category, "kind": kind, "search_text": search_text, "source": source,
            "updated_at": now, "revisions": old.value.get("revisions", 0) + 1,
        })
        return "updated", old.key
    key = uuid.uuid4().hex
    store.put(_ns(user_id), key, {
        "text": text, "category": category, "kind": kind, "search_text": search_text, "source": source,
        "created_at": now, "updated_at": now, "revisions": 0,
    })
    return "added", key


def all_memories(store: BaseStore, user_id: str) -> list[dict]:
    items = store.search(_ns(user_id), limit=200)
    return sorted(({"key": i.key, **i.value} for i in items), key=lambda m: -m.get("updated_at", 0))


def edit(store: BaseStore, user_id: str, key: str, text: str) -> bool:
    """Reword a memory. What the shopper writes themselves counts as said, whatever it was before."""
    old = store.get(_ns(user_id), key)
    text = " ".join((text or "").split())[:140]
    if not old or len(text.split()) < 2:
        return False
    store.put(_ns(user_id), key, {**old.value, "text": text, "search_text": f"{old.value.get('category', 'general')}: {text}",
                                  "source": "said", "updated_at": time.time(), "revisions": old.value.get("revisions", 0) + 1})
    return True


def forget(store: BaseStore, user_id: str, key: str) -> None:
    store.delete(_ns(user_id), key)
