import app.agents.curator as curator


def offer(title, price, rating=4.5, count=100, rank=0, **kw):
    return {"title": title, "price_inr": price, "price_display": f"₹{price}", "seller": "S", "rating": rating,
            "rating_count": count, "rank": rank, **kw}


def run(raw, profile=None, **state):
    return curator.curator_node({"raw_offers": raw, "profile": profile or {}, **state})


def test_dedupes_across_workers_and_clears_raw():
    out = run([offer("Alpha Laptop 16GB", 50000, rank=3), offer("16GB Laptop Alpha", 50000, rank=0), offer("Beta", 40000)])
    assert len(out["offers"]) == 2 and out["raw_offers"][0].get("__reset__") and out["shown"] == []
    assert [o["number"] for o in out["offers"]] == [1, 2]


def test_no_image_lookups_happen_here():
    assert not hasattr(curator, "find_media_many")


def test_budget_filters_and_flags_over_budget():
    raw = [offer("A", 30000), offer("B", 90000)]
    assert [o["title"] for o in run(raw, {"budget_max": 50000})["offers"]] == ["A"]
    out = run(raw, {"budget_max": 10000})
    assert all(o["over_budget"] for o in out["offers"]) and out["offers"][0]["title"] == "A"
    assert out["search_meta"]["relaxed"]


def test_cheapest_fit_always_on_shortlist_and_tags():
    raw = [offer(f"Item {i}", 50000 + i, rating=4.9, count=500, rank=i) for i in range(8)]
    raw.append(offer("Cheap one", 20000, rating=3.0, count=30, rank=9))
    out = run(raw)
    assert len(out["offers"]) == curator.LIMIT
    cheap = next(o for o in out["offers"] if o["title"] == "Cheap one")
    assert "lowest price" in cheap["tags"]
    assert any("best rated" in o.get("tags", []) for o in out["offers"])
    assert len(out["reserve"]) == 3 and all("number" not in o for o in out["reserve"])  # ranked leftovers, kept for later


def test_nothing_found():
    out = run([])
    assert out["offers"] == [] and out["search_meta"]["cheapest"] is None


def test_wrong_audience_is_dropped():
    raw = [offer("Nike Women's Quest", 3000), offer("Puma Men's Softride", 3100), offer("Skechers Womens Go Run", 3300),
           offer("Asics Ladies Gel", 3400), offer("Brooks Women's Ghost", 3500)]
    profile = {"product": "running_shoes", "facts": {"gender": "women"}}
    titles = [o["title"] for o in run(raw, profile)["offers"]]
    assert "Puma Men's Softride" not in titles and len(titles) == 4
    # never leaves the shopper with nothing: too few right-audience listings keeps everything
    few = [offer("Nike Women's Quest", 3000), offer("Puma Men's Softride", 3100)]
    assert len(run(few, profile)["offers"]) == 2
    # no audience in the request: nothing is filtered
    assert len(run(raw, {"product": "running_shoes"})["offers"]) == 5


def test_more_mode_appends_new_listings_and_skips_ones_already_found():
    existing = [{**offer("Alpha", 100), "number": 1}, {**offer("Beta", 200), "number": 2}]
    reserve = [offer("Gamma", 300)]
    raw = [offer("Alpha", 100), offer("Gamma", 300)] + [offer(f"New {i}", 400 + i, rank=i) for i in range(6)]
    out = run(raw, offers=existing, reserve=reserve, search={"mode": "more", "queries": ["x"]})
    assert [o["number"] for o in out["offers"]] == [1, 2, 3, 4, 5, 6]
    assert [o["title"] for o in out["offers"][:2]] == ["Alpha", "Beta"]
    new_titles = [o["title"] for o in out["offers"][2:]]
    assert "Alpha" not in new_titles and "Gamma" not in new_titles and len(new_titles) == curator.MORE_BATCH
    assert "shown" not in out  # what was already shown stays shown
