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


def test_old_model_years_are_dropped_unless_asked_for():
    from app.agents.curator import _latest

    def offer(t):
        return {"title": t}
    offers = [offer("HP Laptop 2019"), offer("Dell XPS 2026"), offer("Lenovo 2025 Edition"), offer("Asus Zenbook"), offer("Acer 2024")]
    kept = [o["title"] for o in _latest(offers, {}, ["laptop"])]
    assert "HP Laptop 2019" not in kept and len(kept) == 4
    assert len(_latest(offers, {}, ["refurbished laptop"])) == 5
    assert len(_latest(offers, {"facts": {"model": "2019"}}, ["laptop"])) == 5
    assert len(_latest(offers[:2], {}, ["laptop"])) == 2  # never empties the list


def test_old_generations_are_recognised_from_the_chip_not_just_a_year():
    from app.agents.curator import _latest
    from app.freshness import model_year

    assert model_year("Lenovo Yoga Slim 7 Intel Core i7 13th Gen 1360p") == 2023
    assert model_year("MSI Prestige 13 Evo i7-1360P") == 2023
    assert model_year("Lenovo 83DV i7-13650HX") == 2023
    assert model_year("Apple MacBook Air M1") == 2020 and model_year("Apple MacBook Air 13 M4") == 2024
    assert model_year("iPhone 15 128GB") == 2023 and model_year("Samsung Galaxy S24") == 2024
    assert model_year("Dell XPS Intel Core Ultra 7 256V") is None and model_year("Levi's 511 Jeans") is None
    titles = ["Lenovo i7 13th Gen", "MSI i7-1360P", "Apple MacBook Air M1", "Dell XPS Core Ultra 7", "Apple MacBook Air M4", "HP Spectre Core Ultra 9"]
    kept = [o["title"] for o in _latest([{"title": t} for t in titles], {}, ["laptop"])]
    assert kept == ["Dell XPS Core Ultra 7", "Apple MacBook Air M4", "HP Spectre Core Ultra 9"]


def test_lead_search_for_yearly_products_carries_the_current_year():
    from datetime import date

    from app.freshness import with_current_year

    y = date.today().year
    assert with_current_year("laptop", ["laptop 32GB RAM", "thin laptop"]) == [f"laptop 32GB RAM {y}", "thin laptop"]
    assert with_current_year("laptop", ["laptop 2024"]) == ["laptop 2024"]
    assert with_current_year("laptop", ["laptop i7 13th gen"]) == ["laptop i7 13th gen"]
    assert with_current_year("laptop", ["refurbished laptop"]) == ["refurbished laptop"]
    assert with_current_year("jeans", ["women straight jeans"]) == ["women straight jeans"]


def test_legacy_plugs_count_as_old_and_a_named_plug_filters_the_rest():
    from app.agents.curator import _compatible, _latest
    from app.freshness import model_year

    assert model_year("Apple EarPods with Lightning Connector") == 2022
    assert model_year("Apple EarPods with 3.5mm Headphone Plug") == 2016
    assert model_year("Apple EarPods (USB-C) For iPhone 15") is None
    titles = ["Apple EarPods Lightning", "Apple EarPods 3.5mm", "Apple EarPods (USB-C)", "Sony IER-EX15C Type C Headphones",
              "Sennheiser CX 80u", "Xiaomi Type-C Earphones"]
    offers = [{"title": t} for t in titles]
    assert [o["title"] for o in _latest(offers, {}, ["headphones"])] == titles[2:]
    usbc = {"facts": {"connector": "USB-C"}}
    kept = [o["title"] for o in _compatible(offers, usbc, ["usb-c wired earphones"])]
    assert kept == ["Apple EarPods (USB-C)", "Sony IER-EX15C Type C Headphones", "Sennheiser CX 80u", "Xiaomi Type-C Earphones"]
    assert len(_compatible(offers, {"facts": {"connector": "USB-C or Lightning"}}, [])) == 6  # two acceptable: nothing enforced


def test_junk_listings_are_dropped_but_a_thin_result_is_kept():
    from app.agents.curator import _trustworthy

    def o(title, price, rating=None, count=None, seller="Flipkart"):
        return {"title": title, "price_inr": price, "rating": rating, "rating_count": count, "seller": seller}
    offers = [o("EarPods", 1500, 4.5, 900), o("EarPods USB-C", 1650, 4.6, 25000), o("Sony Type-C", 1290, 4.6, 1300),
              o("Sennheiser CX", 1790, 4.2, 57), o("AirPods Pro TWS", 234, 4.4, 4300, "Digihaat"), o("USB-C earphones", 79, None, None, "Amazon.in"),
              o("Noname", 1400, None, None, "randomshop.xyz")]
    kept = [x["title"] for x in _trustworthy(offers)]
    assert kept == ["EarPods", "EarPods USB-C", "Sony Type-C", "Sennheiser CX"]  # cheap fakes and an unrated unknown seller are out
    assert len(_trustworthy(offers[:2] + offers[6:])) == 3  # too little would be left after filtering: keep all
