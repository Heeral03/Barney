import json
import uuid
from datetime import date

import pytest

import app.api.main as api
import app.reviews as reviews
import app.settings as settings
import app.signals as signals
from app.db import pool
from app.memory import store as ltm_store
from app.timing import advice
from tests.conftest import client_for, token_for


@pytest.fixture
def who():
    u = f"google:feat-{uuid.uuid4().hex[:8]}"
    yield u
    with pool.connection() as conn:
        for sql in ("delete from user_settings where user_id = %s", "delete from profiles where user_id = %s", "delete from events where user_id = %s",
                    "delete from feedback where user_id = %s", "delete from analytics where user_id = %s", "delete from wishlist where user_id = %s"):
            conn.execute(sql, (u,))
        conn.execute("delete from suggestions where memory_id like %s", (u + "%",))
    for mid in (u, f"{u}#Mom"):
        for m in ltm_store.all_memories(ltm_store.ltm, mid):
            ltm_store.forget(ltm_store.ltm, mid, m["key"])


def test_profiles_keep_tastes_apart_and_an_unknown_profile_is_just_me(who):
    me = client_for(who)
    assert me.post("/profiles", json={"name": "Mom"}).json()["profiles"] == ["me", "Mom"]
    ltm_store.remember(ltm_store.ltm, who, "Likes black shoes", "shoes")
    ltm_store.remember(ltm_store.ltm, f"{who}#Mom", "Likes beige sandals", "shoes")
    assert [m["text"] for m in me.get("/memories").json()] == ["Likes black shoes"]
    assert [m["text"] for m in me.get("/memories", headers={"x-barney-profile": "Mom"}).json()] == ["Likes beige sandals"]
    assert [m["text"] for m in me.get("/memories", headers={"x-barney-profile": "Nobody"}).json()] == ["Likes black shoes"]
    assert me.delete("/profiles/Mom").json()["profiles"] == ["me"]


def test_memories_can_be_edited_and_say_where_they_came_from(who):
    ltm_store.remember(ltm_store.ltm, who, "Likes dark blue jeans", "jeans", source="inferred")
    me = client_for(who)
    got = me.get("/memories").json()[0]
    assert got["source"] == "inferred"
    assert me.put(f"/memories/{got['key']}", json={"text": "Likes black jeans"}).status_code == 200
    again = me.get("/memories").json()[0]
    assert again["text"] == "Likes black jeans" and again["source"] == "said"  # what you write yourself counts as said
    assert me.put(f"/memories/{got['key']}", json={"text": "x"}).status_code == 400


def test_pausing_learning_stops_hearts_and_opens_from_teaching(who, monkeypatch):
    me = client_for(who)
    assert me.get("/settings").json()["learning"] is True
    assert me.put("/settings", json={"learning": False}).json()["learning"] is False
    assert signals.record_event(who, who, "open", "headphones", "Sony WH-1000XM5") is False
    assert me.post("/events", json={"kind": "open", "product": "headphones", "title": "Sony"}).json() == {"recorded": False}
    me.put("/settings", json={"learning": True})
    assert signals.record_event(who, who, "open", "headphones", "Sony WH-1000XM5") is True


def test_opens_become_suggestions_that_need_a_yes(who, monkeypatch):
    class T:
        traits = ["Likes over-ear headphones", "Prefers Sony"]

    monkeypatch.setattr(signals, "extractor", type("E", (), {"invoke": lambda self, m: T()})())
    for title in ("Sony WH-1000XM5", "Sony WH-CH720N", "Bose QC45"):
        signals.record_event(who, who, "open", "headphones", title)
    assert signals.distil(who, "headphones") == 2
    me = client_for(who)
    pending = me.get("/suggestions").json()
    assert [p["text"] for p in pending] == ["Prefers Sony", "Likes over-ear headphones"]
    assert me.get("/memories").json() == []  # nothing is learned until they accept
    assert me.post(f"/suggestions/{pending[0]['id']}/accept").status_code == 200
    assert me.post(f"/suggestions/{pending[1]['id']}/dismiss").status_code == 200
    assert [(m["text"], m["source"]) for m in me.get("/memories").json()] == [("Prefers Sony", "inferred")]
    assert me.get("/suggestions").json() == []
    assert me.post(f"/suggestions/{pending[0]['id']}/accept").status_code == 404


def test_onboarding_saves_three_answers_once(who):
    me = client_for(who)
    out = me.post("/onboarding", json={"categories": ["laptops", "shoes"], "priority": "Best quality", "spend": "up to ₹30,000"}).json()
    assert out["onboarded"] is True
    texts = {m["text"] for m in me.get("/memories").json()}
    assert texts == {"Usually shops for laptops, shoes", "Prefers quality over the lowest price", "Usually spends up to ₹30,000 on a purchase"}


def test_feedback_tracking_and_the_admin_only_numbers(who, monkeypatch):
    me = client_for(who)
    assert me.post("/feedback", json={"title": "x", "verdict": "wrong"}).status_code == 200
    assert me.post("/feedback", json={"title": "x", "verdict": "meh"}).status_code == 400
    me.post("/track", json={"name": "form_submitted"})
    me.post("/track", json={"name": "not_allowed"})
    assert me.get("/metrics").status_code == 403
    monkeypatch.setenv("ADMIN_USERS", who)
    out = me.get("/metrics").json()
    assert out["questionnaire"]["submitted"] >= 1 and out["feedback"]["wrong"] >= 1


def test_a_shared_comparison_is_public_and_leaves_out_private_things(who):
    table = {"specs": ["RAM"], "requirements": ["under ₹1,00,000"], "rows": [
        {"number": 1, "title": "Dell XPS", "price_display": "₹90,000", "token": "SECRET-TOKEN", "values": {"RAM": "16GB"}, "matches": {}}]}
    share_id = client_for(who).post("/share", json={"title": "Laptops", "table": table}).json()["id"]
    from fastapi.testclient import TestClient
    got = TestClient(api.app).get(f"/share/{share_id}").json()  # no token at all
    assert got["title"] == "Laptops" and got["table"]["rows"][0]["title"] == "Dell XPS" and "token" not in got["table"]["rows"][0]
    assert TestClient(api.app).get("/share/nope").status_code == 404


def test_review_summary_uses_the_stores_call_and_never_invents(monkeypatch):
    monkeypatch.setattr(reviews.serpapi, "reviews", lambda token: {
        "rating": 4.6, "count": 100, "histogram": [{"stars": s, "amount": a} for s, a in ((1, 5), (2, 5), (3, 10), (4, 30), (5, 50))],
        "snippets": [{"text": "Great noise cancelling", "rating": 5, "source": "x"}]})

    class S:
        praise, complaints, verdict = ["Strong noise cancelling"], ["Heavy"], "Good for travel."

    monkeypatch.setattr(reviews, "summariser", type("M", (), {"invoke": lambda self, m: S()})())
    reviews._cache.clear()
    out = reviews.summarize("tok")
    assert out["split"][0] == {"stars": 5, "percent": 50} and out["praise"] == ["Strong noise cancelling"] and out["verdict"] == "Good for travel."
    monkeypatch.setattr(reviews.serpapi, "reviews", lambda token: {"rating": 4.0, "count": 9, "histogram": [], "snippets": []})
    reviews._cache.clear()
    empty = reviews.summarize("tok2")
    assert empty["praise"] == [] and empty["complaints"] == [] and empty["split"] == []


def test_timing_advice_is_hedged_and_quiet_when_there_is_nothing_to_say():
    assert "on right now" in advice("laptop", date(2026, 10, 29))
    assert "usually begin" in advice("shoes", date(2026, 10, 1))
    assert "not confirmed" in advice("iphone", date(2026, 8, 20))
    assert advice("shoes", date(2026, 3, 1)) == ""
