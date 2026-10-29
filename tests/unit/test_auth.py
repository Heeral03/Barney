import uuid

import pytest
from fastapi.testclient import TestClient

import app.accounts as accounts
import app.api.main as api
import app.wishlist as wl
from app.db import pool
from app.memory import store as ltm_store
from tests.conftest import client_for, token_for

OFFER = {"title": "Levi's 724", "price_display": "₹1,999", "price_inr": 1999, "seller": "Myntra", "link": "https://m/l"}


@pytest.fixture
def people():
    n = uuid.uuid4().hex[:8]
    guest, user = f"guest:{n}", f"google:{n}"
    yield guest, user
    with pool.connection() as conn:
        for who in (guest, user):
            conn.execute("delete from wishlist where user_id = %s", (who,))
            conn.execute("delete from budget where user_id = %s", (who,))
            conn.execute("delete from chat_log where user_id = %s", (who,))
    for who in (guest, user):
        for m in ltm_store.all_memories(ltm_store.ltm, who):
            ltm_store.forget(ltm_store.ltm, who, m["key"])


def test_requests_without_a_valid_token_are_refused():
    anon = TestClient(api.app)
    assert anon.get("/wishlist").status_code == 401
    assert anon.get("/wishlist", params={"user_id": "google:someone"}).status_code == 401  # a claimed id proves nothing
    for bad in ("Bearer nonsense", "Basic abc", f"Bearer {token_for('google:x1234567', secret='y' * 40)}",
                f"Bearer {token_for('google:x1234567', ttl=-10)}", f"Bearer {token_for('admin')}"):
        assert anon.get("/wishlist", headers={"Authorization": bad}).status_code == 401, bad


def test_the_server_refuses_to_run_without_a_secret(monkeypatch):
    monkeypatch.setenv("BACKEND_JWT_SECRET", "short")
    assert TestClient(api.app).get("/wishlist", headers={"Authorization": f"Bearer {token_for('google:abcdefgh')}"}).status_code == 503


def test_people_only_see_their_own_data(people):
    guest, user = people
    client_for(user).post("/wishlist", json={"product": "jeans", "offer": OFFER})
    assert len(client_for(user).get("/wishlist").json()) == 1
    assert client_for(guest).get("/wishlist").json() == []


def test_a_guest_can_be_claimed_only_with_both_proofs(people):
    guest, user = people
    me = client_for(user)
    assert me.post("/me/claim-guest", json={"guest_token": token_for(user)}).status_code == 400  # not a guest token
    assert client_for(guest).post("/me/claim-guest", json={"guest_token": token_for(guest)}).status_code == 403  # a guest cannot claim
    assert me.post("/me/claim-guest", json={"guest_token": "junk"}).status_code == 401


def test_claiming_moves_the_guests_data_and_the_accounts_own_data_wins(people):
    guest, user = people
    wl.add(guest, OFFER, "jeans")
    wl.add(guest, {**OFFER, "title": "Only guest", "link": "https://m/g"}, "jeans")
    wl.add(user, OFFER, "jeans")  # the same listing already on the account
    ltm_store.remember(ltm_store.ltm, guest, "Likes dark blue jeans", "jeans", key="pref:jeans:colour")
    ltm_store.remember(ltm_store.ltm, user, "Likes black jeans", "jeans", key="pref:jeans:colour")
    ltm_store.remember(ltm_store.ltm, guest, "Wears size 30", "jeans", key="pref:jeans:size")
    client_for(guest).put("/budget", json={"amount_inr": 5000})
    client_for(user).put("/budget", json={"amount_inr": 9000})

    out = client_for(user).post("/me/claim-guest", json={"guest_token": token_for(guest)}).json()
    assert out["claimed"] and out["wishlist"] == 1 and out["memories"] == 1
    assert sorted(w["title"] for w in client_for(user).get("/wishlist").json()) == ["Levi's 724", "Only guest"]
    assert client_for(guest).get("/wishlist").json() == []
    texts = {m["text"] for m in client_for(user).get("/memories").json()}
    assert texts == {"Likes black jeans", "Wears size 30"}
    assert client_for(user).get("/budget").json()["amount"] == 9000 and client_for(guest).get("/budget").json()["amount"] is None


def test_nobody_can_continue_someone_elses_conversation(people, monkeypatch):
    from langchain_core.messages import AIMessage

    guest, user = people
    t = f"thread-{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(api, "chatbot", type("G", (), {"invoke": lambda self, *a, **k: {"messages": [AIMessage(content="Hi!")]}})())
    assert client_for(user).post("/chat", json={"message": "hello", "thread_id": t}).json()["reply"] == "Hi!"
    assert client_for(guest).post("/chat", json={"message": "hello", "thread_id": t}).status_code == 403
    assert client_for(user).post("/chat", json={"message": "again", "thread_id": t}).status_code == 200
