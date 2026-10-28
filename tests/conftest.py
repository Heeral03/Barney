"""Tests run against the real Postgres from docker-compose, but never call an LLM, a search API or the embedding model."""
import hashlib
import math
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.memory.embeddings as embeddings  # noqa: E402


def fake_embed(texts):
    """Bag-of-words hashing into 384 normalised dims: similar wording scores high, like the real model."""
    out = []
    for t in texts:
        v = [0.0] * 384
        for w in t.lower().replace(":", " ").split():
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 384] += 1
        n = math.sqrt(sum(x * x for x in v)) or 1
        out.append([x / n for x in v])
    return out


embeddings.embed = fake_embed  # must happen before app.memory.store is imported


@pytest.fixture
def user_id():
    uid = f"test-{uuid.uuid4().hex[:8]}"
    yield uid
    from app.memory import store

    for m in store.all_memories(store.ltm, uid):
        store.forget(store.ltm, uid, m["key"])


@pytest.fixture
def thread_id():
    tid = f"test-{uuid.uuid4().hex[:8]}"
    yield tid
    from app.graph import checkpointer

    checkpointer.delete_thread(tid)


import app.sources.serpapi as _serpapi  # noqa: E402

_REAL_AVAILABLE = _serpapi.available


@pytest.fixture
def real_availability(monkeypatch):
    """For the few tests of SerpAPI's own availability logic (still no network: searches_left is stubbed there)."""
    monkeypatch.setattr(_serpapi, "available", _REAL_AVAILABLE)


@pytest.fixture(autouse=True)
def no_paid_apis(monkeypatch):
    """Tests never spend SerpAPI credits or call the network; tests of that path switch it on with stubs."""
    import app.sources.serpapi as serpapi

    monkeypatch.setattr(serpapi, "available", lambda: False)
    monkeypatch.setattr(serpapi, "searches_left", lambda: None)
