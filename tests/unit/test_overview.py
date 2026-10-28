import uuid

import pytest
from fastapi.testclient import TestClient

import app.overview as ov
import app.wishlist as wl
from app import history
from app.db import pool
from app.memory import store as ltm_store


@pytest.fixture
def uid():
    u = f"test-{uuid.uuid4().hex[:8]}"
    yield u
    with pool.connection() as conn:
        for table in ("wishlist", "budget", "chat_log"):
            conn.execute(f"delete from {table} where user_id = %s", (u,))
    for m in ltm_store.all_memories(ltm_store.ltm, u):
        ltm_store.forget(ltm_store.ltm, u, m["key"])


def row(n, title, price, rating=None, best=False, stores=0):
    return {"number": n, "title": title, "price_inr": price, "price_display": f"₹{price}", "rating": rating, "rating_count": 100,
            "image_url": f"img{n}", "best": best, "stores": [{"name": "S"}] * stores}


# ----------------------------------------------------------------- one comparison, summarised
def test_a_comparison_card_summarises_the_pick_and_the_price_range():
    table = {"specs": ["Fit"], "rows": [row(1, "Pick", 700, 4.4, best=True, stores=3), row(2, "Dear", 1999, 4.5), row(3, "Cheap", 379, 4.0)]}
    card = ov.comparison_card(table, "thread-1")
    assert card == {"thread_id": "thread-1", "title": "Pick", "image_url": "img1", "options": 3, "price_low": 379, "price_high": 1999,
                    "rating": 4.4, "rating_count": 100, "stores": 3, "tag": "Barney's pick", "specs": ["Fit"]}


def test_the_tag_says_why_the_pick_stands_out():
    cheapest = {"rows": [row(1, "A", 300, 4.0, best=True), row(2, "B", 900, 4.5)]}
    assert ov.comparison_card(cheapest)["tag"] == "Lowest price"
    top_rated = {"rows": [row(1, "A", 900, 4.8, best=True), row(2, "B", 300, 4.0)]}
    assert ov.comparison_card(top_rated)["tag"] == "Best overall"
    assert ov.comparison_card({"rows": [row(1, "Only", 500, 4.0)]})["tag"] == "Barney's pick"  # nothing to beat
    assert ov.comparison_card({"rows": []}) is None


def test_older_tables_without_a_numeric_price_still_work():
    old = {"rows": [{"title": "A", "price_display": "₹1,499", "best": True}, {"title": "B", "price_display": "₹2,000"}]}
    card = ov.comparison_card(old)
    assert (card["price_low"], card["price_high"], card["stores"]) == (1499, 2000, 1)


# ----------------------------------------------------------------- stored things
def test_budget_roundtrip_and_clear(uid):
    assert ov.get_budget(uid) is None
    ov.set_budget(uid, 12500)
    ov.set_budget(uid, 15000)  # replaces
    assert ov.get_budget(uid) == 15000
    ov.set_budget(uid, None)
    assert ov.get_budget(uid) is None


def test_wishlist_target_prices(uid):
    item = wl.add(uid, {"title": "Nike Air Force", "price_inr": 7995, "price_display": "₹7,995", "link": "https://x/1"}, "sneakers")
    assert wl.items(uid)[0]["target_inr"] is None
    wl.set_target(uid, item, 6500)
    assert wl.items(uid)[0]["target_inr"] == 6500
    wl.set_target("someone-else", item, 1)  # not theirs
    assert wl.items(uid)[0]["target_inr"] == 6500
    wl.set_target(uid, item, None)
    assert wl.items(uid)[0]["target_inr"] is None


def seed(uid):
    t1 = {"specs": ["Fit"], "rows": [row(1, "Sony WH-CH720N", 7990, 4.4, best=True, stores=3), row(2, "Bose", 9990, 4.5)]}
    history.append("t-1", uid, [("user", "headphones", {}), ("assistant", "Here", {"table": t1}), ("user", "thanks", {}),
                                ("assistant", "No problem", {"table": None})])
    history.append("t-2", uid, [("assistant", "Another", {"table": {"rows": [row(1, "MacBook Air", 69900, 4.7, best=True)]}})])


def test_recent_comparisons_come_from_past_tables_newest_first(uid):
    seed(uid)
    assert [c["title"] for c in ov.comparisons(uid)] == ["MacBook Air", "Sony WH-CH720N"]  # turns without a table are ignored
    assert [c["thread_id"] for c in ov.comparisons(uid, 1)] == ["t-2"]
    assert ov.comparisons("nobody") == []


def test_the_overview_adds_it_all_up(uid):
    seed(uid)
    ltm_store.remember(ltm_store.ltm, uid, "Name is Aanya", "person", "profile")
    ltm_store.remember(ltm_store.ltm, uid, "Wears size 5 in shoes", "shoes", "profile")
    wl.add(uid, {"title": "Nike", "price_inr": 7995, "price_display": "₹7,995", "link": "https://x/1"}, "sneakers")
    wl.add(uid, {"title": "Bose", "price_inr": 4000, "price_display": "₹4,000", "link": "https://x/2"}, "headphones")
    wl.add(uid, {"title": "No price", "price_display": "See site", "link": "https://x/3"}, "bags")
    ov.set_budget(uid, 20000)
    o = ov.overview(uid)
    assert o["name"] == "Aanya" and o["stats"] == {"wishlist": 3, "comparisons": 2, "preferences": 2}
    assert o["budget"] == {"amount": 20000, "wishlist_total": 11995, "remaining": 8005}
    assert [w["title"] for w in o["wishlist"]] == ["No price", "Bose", "Nike"] and len(o["comparisons"]) == 2


def test_a_new_shopper_gets_an_empty_overview_not_an_error(uid):
    o = ov.overview(uid)
    assert o == {"name": None, "stats": {"wishlist": 0, "comparisons": 0, "preferences": 0},
                 "budget": {"amount": None, "wishlist_total": 0, "remaining": None}, "wishlist": [], "comparisons": []}


def test_the_endpoints(uid):
    import app.api.main as api
    client = TestClient(api.app)
    seed(uid)
    item = wl.add(uid, {"title": "Nike", "price_inr": 7995, "price_display": "₹7,995", "link": "https://x/1"}, "sneakers")
    assert client.put("/budget", json={"user_id": uid, "amount_inr": 10000}).json() == {"amount": 10000, "wishlist_total": 7995, "remaining": 2005}
    assert client.get("/budget", params={"user_id": uid}).json()["amount"] == 10000
    assert client.put(f"/wishlist/{item}/target", json={"user_id": uid, "target_inr": 6500}).json() == {"ok": True}
    assert client.get("/wishlist", params={"user_id": uid}).json()[0]["target_inr"] == 6500
    assert client.get("/overview", params={"user_id": uid}).json()["stats"]["wishlist"] == 1
    assert len(client.get("/comparisons", params={"user_id": uid, "limit": 5}).json()) == 2
    assert client.put("/budget", json={"user_id": uid, "amount_inr": None}).json()["amount"] is None
