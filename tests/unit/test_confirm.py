"""When is a pick a genuine judgement call? (The pause itself is covered in tests/graph/test_flow.py.)"""
from types import SimpleNamespace

from app.agents import confirm


def offer(n, price, rating, count=200, **kw):
    return {"number": n, "title": f"Item {n}", "price_inr": price, "price_display": f"₹{price}", "rating": rating, "rating_count": count, **kw}


def test_cheaper_but_slightly_worse_is_a_close_call():
    pair = confirm.close_call([offer(1, 4000, 4.6), offer(2, 2500, 4.4), offer(3, 3900, 4.3)], {})
    assert [o["number"] for o in pair] == [2, 1]  # (cheaper, better rated)


def test_no_decision_when_one_listing_wins_on_both():
    assert confirm.close_call([offer(1, 2000, 4.6), offer(2, 3000, 4.4)], {}) is None


def test_no_decision_when_the_prices_are_close_or_the_rating_gap_is_large():
    assert confirm.close_call([offer(1, 4000, 4.6), offer(2, 3500, 4.5)], {}) is None  # only 12% cheaper
    assert confirm.close_call([offer(1, 4000, 4.8), offer(2, 2000, 4.0)], {}) is None  # a clearly worse rating: not a toss-up


def test_ratings_must_rest_on_enough_reviews():
    assert confirm.close_call([offer(1, 4000, 4.6, 300), offer(2, 2500, 4.4, 3)], {}) is None


def test_skipped_over_budget_and_switched_off():
    offers = [offer(1, 4000, 4.6), offer(2, 2500, 4.4)]
    assert confirm.close_call(offers, {"skip": True}) is None
    assert confirm.close_call([{**o, "over_budget": True} for o in offers], {}) is None
    import os
    os.environ["CONFIRM_CLOSE_CALLS"] = "0"
    try:
        assert confirm.close_call(offers, {}) is None
    finally:
        del os.environ["CONFIRM_CLOSE_CALLS"]


def test_only_the_top_of_the_shortlist_counts():
    offers = [offer(1, 4000, 4.6), offer(2, 3900, 4.6), offer(3, 3950, 4.6), offer(4, 2000, 4.5)]
    assert confirm.close_call(offers, {}) is None


def test_match_choice_maps_a_button_tap_and_ignores_free_text():
    q = {"choices": [{"label": "Save money: ₹2500", "number": 2}, {"label": "You decide", "number": None}]}
    assert confirm.match_choice(q, "Save money: ₹2500") == (True, 2)
    assert confirm.match_choice(q, "You decide") == (True, confirm.AUTO)
    assert confirm.match_choice(q, "show me laptops") == (False, None)


def test_pending_reads_only_this_kind_of_question():
    snap = lambda v: SimpleNamespace(tasks=[SimpleNamespace(interrupts=[SimpleNamespace(value=v)])])
    assert confirm.pending(snap({"type": "confirm_pick", "choices": []})) == {"type": "confirm_pick", "choices": []}
    assert confirm.pending(snap({"type": "something else"})) is None
    assert confirm.pending(SimpleNamespace(tasks=[])) is None
