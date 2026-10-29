import json
import uuid

import pytest
from langchain_core.messages import AIMessage

import app.alerts as alerts
import app.api.main as api
import app.wishlist as wl
from app.db import pool
from tests.conftest import client_for

OFFER = {"title": "Sony IER-EX15C", "price_display": "₹1,590", "price_inr": 1590, "seller": "Reliance Digital", "link": "https://reliance.example/p"}


@pytest.fixture
def uid():
    u = f"google:alerts-{uuid.uuid4().hex[:8]}"
    yield u
    with pool.connection() as conn:
        conn.execute("delete from price_checks where wishlist_id in (select id from wishlist where user_id = %s)", (u,))
        conn.execute("delete from alerts where user_id = %s", (u,))
        conn.execute("delete from user_emails where user_id = %s", (u,))
        conn.execute("delete from wishlist where user_id = %s", (u,))
        conn.execute("delete from chat_log where user_id = %s", (u,))


def test_a_price_at_the_target_raises_one_alert_and_an_email(uid, monkeypatch):
    sent = []
    monkeypatch.setattr(alerts, "send_email", lambda to, subject, body: sent.append((to, subject)) or True)
    me = client_for(uid)
    item = me.post("/wishlist", json={"product": "headphones", "offer": OFFER}).json()["id"]
    me.put(f"/wishlist/{item}/target", json={"target_inr": 1300})
    alerts.remember_email(uid, "shopper@example.com")

    monkeypatch.setattr(alerts, "page_price", lambda url, timeout=0: 1450.0)
    assert me.post(f"/wishlist/{item}/check").json()["alert"] is False  # above the target: just recorded
    monkeypatch.setattr(alerts, "page_price", lambda url, timeout=0: 1290.0)
    assert me.post(f"/wishlist/{item}/check").json()["alert"] is True
    assert me.post(f"/wishlist/{item}/check").json()["alert"] is False  # the same price does not alert twice
    assert sent == [("shopper@example.com", "Price drop: Sony IER-EX15C is now ₹1,290")]

    assert [a["price_inr"] for a in me.get("/alerts").json()] == [1290.0]
    assert me.get("/overview").json()["alerts"] == 1
    me.post("/alerts/seen")
    assert me.get("/alerts").json() == []

    got = me.get("/wishlist").json()[0]
    assert got["price_inr"] == 1290 and got["price_low"] == 1290 and got["price_high"] == 1450 and got["checks"] == 3
    assert [p["price_inr"] for p in me.get(f"/wishlist/{item}/history").json()] == [1450.0, 1290.0, 1290.0]


def test_an_unreadable_page_claims_nothing_and_only_the_owner_can_check(uid, monkeypatch):
    me = client_for(uid)
    item = me.post("/wishlist", json={"product": "headphones", "offer": OFFER}).json()["id"]
    monkeypatch.setattr(alerts, "page_price", lambda url, timeout=0: None)
    assert me.post(f"/wishlist/{item}/check").json()["price"] is None
    assert me.get("/wishlist").json()[0]["price_inr"] == 1590 and "checks" not in me.get("/wishlist").json()[0]
    assert client_for("google:someone-else").post(f"/wishlist/{item}/check").status_code == 404


def test_email_is_off_unless_smtp_is_configured(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert alerts.send_email("a@b.c", "s", "b") is False


def test_the_turn_streams_progress_then_the_full_answer(monkeypatch):
    class G:
        def stream(self, *a, **k):
            yield "updates", {"memory_in": {}}
            yield "updates", {"supervisor": {"route": "research"}}
            yield "updates", {"worker": {"raw_offers": []}}
            yield "updates", {"curator": {"offers": [{"number": 1, "title": "Sony", "price_display": "₹1", "seller": "x", "junk": 1}]}}
            yield "values", {"messages": [AIMessage(content="Here you go")], "cards": [{"number": 1, "title": "Sony"}], "options": ["More"]}

    monkeypatch.setattr(api, "chatbot", G())
    t = f"thread-{uuid.uuid4().hex[:8]}"
    me = f"google:stream-{uuid.uuid4().hex[:6]}"
    try:
        res = client_for(me).post("/chat/stream", json={"message": "hi", "thread_id": t})
        events = [json.loads(line) for line in res.text.splitlines()]
        assert [e["type"] for e in events] == ["status", "status", "status", "preview", "done"]
        assert events[0]["text"] == "Understanding what you need…" and events[1]["text"] == "Searching the stores…"
        assert events[3]["products"] == [{"number": 1, "title": "Sony", "price_display": "₹1", "seller": "x", "image_url": None, "rating": None, "rating_count": None}]
        assert events[-1]["answer"]["reply"] == "Here you go" and events[-1]["answer"]["products"][0]["title"] == "Sony"
        assert [m["role"] for m in client_for(me).get("/history", params={"thread_id": t}).json()] == ["user", "assistant"]
        assert client_for("google:intruder").post("/chat/stream", json={"message": "x", "thread_id": t}).status_code == 403
    finally:
        with pool.connection() as conn:
            conn.execute("delete from chat_log where user_id = %s", (me,))


def test_a_failing_turn_still_ends_with_a_done_event(monkeypatch):
    class G:
        def stream(self, *a, **k):
            raise RuntimeError("boom")
            yield

    monkeypatch.setattr(api, "chatbot", G())
    me = f"google:stream-{uuid.uuid4().hex[:6]}"
    t = f"thread-{uuid.uuid4().hex[:8]}"
    try:
        events = [json.loads(x) for x in client_for(me).post("/chat/stream", json={"message": "hi", "thread_id": t}).text.splitlines()]
        assert events[-1]["type"] == "done" and "went wrong" in events[-1]["answer"]["reply"]
    finally:
        with pool.connection() as conn:
            conn.execute("delete from chat_log where user_id = %s", (me,))
