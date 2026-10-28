import uuid

import pytest
from fastapi.testclient import TestClient

import app.agents.memory as memory
import app.wishlist as wl
from app.agents.common import known_text, wishlist_text
from app.db import pool
from app.memory import store as ltm_store

OFFER = {"title": "Levi's Women's 724 High Rise Straight Jeans", "price_display": "₹1,999", "price_inr": 1999, "seller": "Myntra",
         "link": "https://myntra.com/levis", "image_url": "img", "rating": 4.4, "extra_junk": "dropped"}


@pytest.fixture
def uid():
    u = f"test-{uuid.uuid4().hex[:8]}"
    yield u
    with pool.connection() as conn:
        conn.execute("delete from wishlist where user_id = %s", (u,))
    for m in ltm_store.all_memories(ltm_store.ltm, u):
        ltm_store.forget(ltm_store.ltm, u, m["key"])


def test_add_list_remove_and_no_duplicates(uid):
    first = wl.add(uid, OFFER, "jeans")
    assert first and wl.add(uid, OFFER, "jeans") is None  # the same listing is not saved twice
    items = wl.items(uid)
    assert len(items) == 1 and items[0]["title"] == OFFER["title"] and "extra_junk" not in items[0] and items[0]["product"] == "jeans"
    assert wl.recent(uid) == [{"title": OFFER["title"], "product": "jeans"}]
    wl.remove(uid, first)
    assert wl.items(uid) == []


def test_other_users_cannot_remove_or_see_it(uid):
    item = wl.add(uid, OFFER, "jeans")
    wl.remove("someone-else", item)
    assert len(wl.items(uid)) == 1 and wl.items("someone-else") == []


def test_a_hearted_listing_teaches_a_taste(uid, monkeypatch):
    monkeypatch.setattr(wl.extractor, "invoke", lambda m: wl.Taste(traits=["Likes high-rise straight-fit jeans", "Likes blue denim", "Likes"]))
    events = wl.learn_taste(ltm_store.ltm, uid, OFFER, "jeans")
    assert events == ["Saved: Likes high-rise straight-fit jeans", "Saved: Likes blue denim"]
    assert {m["category"] for m in ltm_store.all_memories(ltm_store.ltm, uid)} == {"jeans"}


def test_taste_learning_never_raises(uid, monkeypatch):
    def boom(m):
        raise RuntimeError("rate limited")
    monkeypatch.setattr(wl.extractor, "invoke", boom)
    assert wl.learn_taste(ltm_store.ltm, uid, OFFER, "jeans") == []


def test_wishlist_reaches_the_planner_only_for_the_same_product():
    items = [{"title": "Levi's High Rise Straight Jeans", "product": "jeans"}, {"title": "Nike Quest", "product": "running_shoes"}]
    assert "Levi's High Rise" in wishlist_text(items, "women jeans") and "Nike" not in wishlist_text(items, "women jeans")
    assert wishlist_text(items, "laptop") == ""
    assert "Saved to their wishlist" in known_text({"product": "jeans"}, wishlist=items)


def test_recall_loads_the_wishlist(uid):
    from langchain_core.messages import HumanMessage
    wl.add(uid, OFFER, "jeans")
    out = memory.recall_node({"messages": [HumanMessage(content="jeans")], "profile": {}}, {"configurable": {"user_id": uid}}, store=ltm_store.ltm)
    assert out["wishlist"] == [{"title": OFFER["title"], "product": "jeans"}]


def test_wishlist_endpoints(uid, monkeypatch):
    import app.api.main as api
    learned = []
    monkeypatch.setattr(api.wishlist, "learn_taste", lambda *a: learned.append(a))
    client = TestClient(api.app)
    body = {"user_id": uid, "product": "jeans", "offer": OFFER}
    first = client.post("/wishlist", json=body).json()
    assert first["new"] and len(learned) == 1  # learning is scheduled for new hearts only
    assert not client.post("/wishlist", json=body).json()["new"] and len(learned) == 1
    listed = client.get("/wishlist", params={"user_id": uid}).json()
    assert [w["title"] for w in listed] == [OFFER["title"]]
    assert client.delete(f"/wishlist/{first['id']}", params={"user_id": uid}).json() == {"ok": True}
    assert client.get("/wishlist", params={"user_id": uid}).json() == []
