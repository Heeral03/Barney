import uuid

import pytest

import app.agents.specfit as specfit
import app.feed as feed
import app.pricehistory as ph
from app.db import pool


# ----------------------------------------------------------------- the model fit check
def offers(n=5):
    return [{"number": i, "title": f"Listing {i}", "price_display": "₹1", "seller": "Shop"} for i in range(1, n + 1)]


def state(offs):
    return {"offers": offs, "profile": {"product": "running shoes", "facts": {"gender": "women"}}}


def verdicts(*failed):
    return lambda messages: specfit.Verdicts(verdicts=[specfit.Verdict(number=n, fits=False, why="men's") for n in failed])


def test_listings_that_clearly_do_not_fit_are_removed(monkeypatch):
    monkeypatch.setattr(specfit.checker, "invoke", verdicts(2, 4))
    out = specfit.spec_check_node(state(offers()))["offers"]
    assert [o["number"] for o in out] == [1, 3, 5] and all(o["fit_checked"] for o in out)


def test_a_failing_model_never_blocks_the_search(monkeypatch):
    def boom(messages):
        raise RuntimeError("rate limited")
    monkeypatch.setattr(specfit.checker, "invoke", boom)
    assert len(specfit.spec_check_node(state(offers()))["offers"]) == 5


def test_a_check_that_would_wipe_out_the_list_is_not_trusted(monkeypatch):
    monkeypatch.setattr(specfit.checker, "invoke", verdicts(1, 2, 3, 4))
    assert len(specfit.spec_check_node(state(offers()))["offers"]) == 5


def test_listings_already_checked_are_not_sent_again(monkeypatch):
    sent = []
    monkeypatch.setattr(specfit.checker, "invoke", lambda m: sent.append(m) or specfit.Verdicts(verdicts=[]))
    offs = [{**o, "fit_checked": True} for o in offers(3)]
    specfit.spec_check_node(state(offs))
    assert sent == []


# ----------------------------------------------------------------- price history
def test_a_price_is_judged_against_the_usual_one():
    assert ph.judge(100, [100, 100])["verdict"] == "new"  # too little history to say anything
    past = [100, 102, 98, 100]
    assert ph.judge(85, past)["verdict"] == "good" and "below" in ph.judge(85, past)["text"]
    assert ph.judge(120, past)["verdict"] == "high" and "waiting" in ph.judge(120, past)["text"]
    assert ph.judge(101, past)["verdict"] == "fair"


def test_sightings_are_remembered_and_the_same_product_has_one_key():
    title = f"Test Gadget {uuid.uuid4().hex[:8]}"
    assert ph.key_of(title) == ph.key_of(title.upper() + "  ")
    with pool.connection() as conn:
        for p in (1000, 1010, 990):
            conn.execute("insert into price_observations (key, domain, price) values (%s, 'amazon.in', %s)", (ph.key_of(title), p))
    got = ph.observe(title, 800, "amazon.in")
    assert got["verdict"] == "good" and got["samples"] == 3
    with pool.connection() as conn:
        conn.execute("delete from price_observations where key = %s", (ph.key_of(title),))


# ----------------------------------------------------------------- the "Barney noticed" feed
@pytest.fixture
def uid():
    u = f"google:feed-{uuid.uuid4().hex[:8]}"
    yield u
    with pool.connection() as conn:
        conn.execute("delete from feed_items where user_id = %s", (u,))
        conn.execute("delete from price_checks where wishlist_id in (select id from wishlist where user_id = %s)", (u,))
        conn.execute("delete from wishlist where user_id = %s", (u,))
        conn.execute("delete from events where user_id = %s", (u,))


def test_a_price_drop_on_a_saved_product_is_announced_once(uid):
    import json
    with pool.connection() as conn:
        wid = conn.execute("insert into wishlist (user_id, key, title, offer) values (%s, %s, 'Sony earphones', %s) returning id",
                           (uid, uid, json.dumps({"link": "https://www.amazon.in/p"}))).fetchone()["id"]
        for price in (1500, 1300):
            conn.execute("insert into price_checks (wishlist_id, price_inr) values (%s, %s)", (wid, price))
    feed.wishlist_drops()
    feed.wishlist_drops()  # a second pass must not repeat it
    items = feed.unseen(uid)
    assert len(items) == 1 and "dropped" in items[0]["title"].lower() and "₹1,300" in items[0]["body"]
    feed.mark_seen(uid)
    assert feed.unseen(uid) == []


def test_a_small_wobble_is_not_news(uid):
    import json
    with pool.connection() as conn:
        wid = conn.execute("insert into wishlist (user_id, key, title, offer) values (%s, %s, 'Mouse', %s) returning id",
                           (uid, uid, json.dumps({}))).fetchone()["id"]
        for price in (1000, 980):
            conn.execute("insert into price_checks (wishlist_id, price_inr) values (%s, %s)", (wid, price))
    feed.wishlist_drops()
    assert feed.unseen(uid) == []


def test_a_clicked_product_that_got_cheaper_is_announced(uid, monkeypatch):
    with pool.connection() as conn:
        conn.execute("insert into events (user_id, memory_id, kind, product, title, link, price) values (%s, %s, 'check', 'mouse', 'Logi Mouse', 'https://www.amazon.in/p', 2000)", (uid, uid))
    monkeypatch.setattr(feed, "page_price", lambda url, timeout=0: 1700.0)
    monkeypatch.setattr(feed, "observe", lambda *a, **k: {})
    feed.clicked_drops()
    assert [i["title"] for i in feed.unseen(uid)] == ["Cheaper now: Logi Mouse"]


def test_only_a_genuine_stores_link_is_kept_from_a_click(uid):
    from tests.conftest import client_for
    me = client_for(uid)
    me.post("/events", json={"kind": "buy", "product": "mouse", "title": "Fake", "link": "https://evil.example/p", "price": 10})
    me.post("/events", json={"kind": "buy", "product": "mouse", "title": "Real", "link": "https://www.amazon.in/p", "price": 10})
    with pool.connection() as conn:
        rows = {r["title"]: r["link"] for r in conn.execute("select title, link from events where user_id = %s", (uid,)).fetchall()}
    assert rows.get("Fake") is None and rows.get("Real") == "https://www.amazon.in/p"
