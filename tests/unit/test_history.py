import uuid

import pytest
from tests.conftest import client_for
from langchain_core.messages import AIMessage

from app import history
from app.db import pool


@pytest.fixture
def ids():
    t, u = f"google:test-{uuid.uuid4().hex[:8]}", f"google:test-{uuid.uuid4().hex[:8]}"
    yield t, u
    with pool.connection() as conn:
        conn.execute("delete from chat_log where thread_id = %s", (t,))


def test_roundtrip_keeps_order_and_payload(ids):
    t, u = ids
    history.append(t, u, [("user", "laptop", {}), ("assistant", "Budget?", {"options": ["50k"], "products": []})])
    history.append(t, u, [("user", "50k", {}), ("assistant", "Here", {"products": [{"title": "X"}]})])
    got = history.load(t, u)
    assert [(m["role"], m["content"]) for m in got] == [("user", "laptop"), ("assistant", "Budget?"), ("user", "50k"), ("assistant", "Here")]
    assert got[1]["options"] == ["50k"] and got[3]["products"] == [{"title": "X"}]


def test_other_users_cannot_read_a_thread(ids):
    t, u = ids
    history.append(t, u, [("user", "secret", {})])
    assert history.load(t, "someone-else") == []
    assert history.load("no-such-thread", u) == []


def test_chat_endpoint_saves_the_turn_and_history_serves_it(ids, monkeypatch):
    import app.api.main as api
    t, u = ids
    fake = type("G", (), {"invoke": lambda self, *a, **k: {
        "messages": [AIMessage(content="Hi!")], "options": ["Laptop"], "cards": [], "recalled": [], "saved": ["Saved: x"]}})()
    monkeypatch.setattr(api, "chatbot", fake)
    client = client_for(u)
    assert client.post("/chat", json={"message": "hello", "thread_id": t}).json()["reply"] == "Hi!"
    got = client.get("/history", params={"thread_id": t}).json()
    assert [m["role"] for m in got] == ["user", "assistant"]
    assert got[1]["options"] == ["Laptop"] and got[1]["memory"]["saved"] == ["Saved: x"]
    assert client_for("google:intruder").get("/history", params={"thread_id": t}).json() == []


def test_failed_turns_are_saved_too(ids, monkeypatch):
    import app.api.main as api
    t, u = ids

    def boom(*a, **k):
        raise RuntimeError("model not found")

    monkeypatch.setattr(api, "chatbot", type("G", (), {"invoke": boom})())
    client = client_for(u)
    assert "went wrong" in client.post("/chat", json={"message": "hi", "thread_id": t}).json()["reply"]
    got = client.get("/history", params={"thread_id": t}).json()
    assert [m["role"] for m in got] == ["user", "assistant"] and "went wrong" in got[1]["content"]
