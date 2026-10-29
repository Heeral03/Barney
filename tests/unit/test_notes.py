from datetime import date

from app.notes import checked_ago, notes_for

Y = date.today().year


def texts(notes, kind):
    return [n["text"] for n in notes if n["kind"] == kind]


def test_a_strong_current_listing_gets_good_notes_and_no_warnings():
    offer = {"title": "Sony IER-EX15C Wired In Ear Type C Headphones", "price_inr": 1290, "rating": 4.6, "rating_count": 1300,
             "seller_trusted": True, "price_verified": True, "stores": [{}], "tags": ["lowest price"]}
    notes = notes_for(offer, {"budget_max": 5000, "facts": {"connector": "Type C", "mode": "open to suggestions"}})
    assert texts(notes, "warn") == []
    assert {"Rated 4.6 by 1,300 buyers", "Within your budget", "Mentions your Type C"} <= set(texts(notes, "good"))


def test_weaknesses_are_always_said():
    offer = {"title": f"Lenovo Yoga i7 13th Gen {Y - 3}", "price_inr": 9, "rating": None, "seller_trusted": False,
             "stores": [{}], "price_verified": False}
    warn = texts(notes_for(offer, {}), "warn")
    assert "No reviews yet" in warn and any(w.startswith("Older model") for w in warn)
    assert len(warn) == 3  # capped, most important first
    few = texts(notes_for({"title": "x", "rating": 4.9, "rating_count": 3}, {}), "warn")
    assert few == ["Only 3 reviews, so the rating is weak evidence"]
    assert texts(notes_for({"title": "x", "rating": 4.0, "rating_count": 500, "over_budget": True}, {}), "warn") == ["Over your budget"]


def test_checked_ago():
    assert checked_ago(None) == "" and checked_ago(1000, now=1010) == "just now"
    assert checked_ago(0, now=300) == "5 min ago" and checked_ago(0, now=7300) == "2 h ago" and checked_ago(0, now=200000) == "2 d ago"
