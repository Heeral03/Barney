import httpx
import pytest
from fastapi.testclient import TestClient

import app.agents.researcher as researcher
import app.pricing as pricing
import app.sources.serpapi as serpapi
from app.sources import verify


def resp(data, status=200):
    return httpx.Response(status, json=data, request=httpx.Request("GET", "https://serpapi.com"))


# ----------------------------------------------------------------- SerpAPI parsing
def test_shopping_results_become_offers(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "k")
    rows = [{"title": "Kotty Straight Jeans", "extracted_price": 600, "price": "₹600", "source": "Myntra", "rating": 4.2, "reviews": 618,
             "thumbnail": "https://img/1", "product_link": "https://google.com/p1", "immersive_product_page_token": "tok1", "position": 1},
            {"title": "No price", "position": 2}, {"extracted_price": 100, "position": 3}]
    seen = {}
    monkeypatch.setattr(serpapi.httpx, "get", lambda url, **k: seen.update(k["params"]) or resp({"shopping_results": rows}))
    serpapi.search_shopping.__wrapped__("women jeans")
    out = serpapi.search_shopping.__wrapped__("women jeans")
    assert seen["engine"] == "google_shopping" and seen["gl"] == "in" and seen["q"] == "women jeans"
    assert len(out) == 1 and out[0] == {
        "title": "Kotty Straight Jeans", "price_inr": 600, "price_display": "₹600", "seller": "Myntra", "rating": 4.2,
        "rating_count": 618, "image_url": "https://img/1", "link": None,  # never a Google link: the seller's page comes from `stores`
        "token": "tok1", "api": "serpapi", "rank": 0}


def test_stores_parse_and_skip_rows_without_a_price_or_link(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "k")
    rows = [{"name": "Myntra", "extracted_price": 600, "price": "₹600", "link": "https://myntra.com/x", "tag": "Most popular"},
            {"name": "No link", "extracted_price": 5}, {"name": "No price", "link": "https://x"}]
    monkeypatch.setattr(serpapi.httpx, "get", lambda url, **k: resp({"product_results": {"stores": rows}}))
    assert serpapi.stores.__wrapped__("tok") == [
        {"name": "Myntra", "price_inr": 600, "price_display": "₹600", "link": "https://myntra.com/x", "tag": "Most popular"}]


def test_running_out_of_searches_switches_it_off(monkeypatch, real_availability):
    monkeypatch.setenv("SERPAPI_API_KEY", "k")
    monkeypatch.setattr(serpapi, "_blocked_until", 0.0)
    monkeypatch.setattr(serpapi, "searches_left", lambda: 100)
    monkeypatch.setattr(serpapi.httpx, "get", lambda url, **k: resp({"error": "Your account has run out of searches."}, 429))
    assert serpapi.available()
    with pytest.raises(serpapi.SerpApiError):
        serpapi.search_shopping.__wrapped__("jeans")
    assert not serpapi.available()  # skipped for the next hour, no more wasted calls


def test_a_nearly_used_up_plan_is_left_alone(monkeypatch, real_availability):
    monkeypatch.setenv("SERPAPI_API_KEY", "k")
    monkeypatch.setattr(serpapi, "_blocked_until", 0.0)
    monkeypatch.setattr(serpapi, "searches_left", lambda: serpapi.KEEP_FREE)
    assert not serpapi.available()
    monkeypatch.setattr(serpapi, "searches_left", lambda: 50)
    assert serpapi.available()
    monkeypatch.delenv("SERPAPI_API_KEY")
    assert not serpapi.available()


# ----------------------------------------------------------------- reading a store's page
def test_prices_are_read_from_structured_data():
    ld = '<script type="application/ld+json">{"@type":"Product","offers":{"@type":"Offer","price":"558","priceCurrency":"INR"}}</script>'
    assert verify.price_in_html(f"<html>{ld}</html>") == 558
    nested = '<script type="application/ld+json">[{"@type":"Product","offers":[{"price":999,"x":0},{"lowPrice":"1,299.50"}]}]</script>'
    assert verify.price_in_html(nested) == 999  # the first price on the page, not the last
    assert verify.price_in_html('<meta property="product:price:amount" content="1,040">') == 1040
    assert verify.price_in_html('<span class="a-offscreen">₹1,299</span>') == 1299
    assert verify.price_in_html("<html>nothing</html>") is None
    assert verify.price_in_html('<script type="application/ld+json">{broken</script>') is None


def test_unreadable_pages_claim_nothing(monkeypatch):
    monkeypatch.setattr(verify.httpx, "get", lambda *a, **k: httpx.Response(403, text="denied", request=httpx.Request("GET", "x")))
    assert verify.page_price("https://ajio.com/x") is None
    monkeypatch.setattr(verify.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("down")))
    assert verify.page_price("https://flipkart.com/x") is None
    assert verify.page_price("file:///etc/passwd") is None


# ----------------------------------------------------------------- comparing stores
STORES = [{"name": "Myntra", "price_inr": 600, "price_display": "₹600", "link": "https://myntra.com/p", "tag": None},
          {"name": "AJIO.com", "price_inr": 375, "price_display": "₹375", "link": "https://ajio.com/p", "tag": "Best price"},
          {"name": "Flipkart", "price_inr": 558, "price_display": "₹558", "link": "https://flipkart.com/p", "tag": None},
          {"name": "Bestdeals4u", "price_inr": 300, "price_display": "₹300", "link": "https://bestdeals4u.in/p", "tag": None}]


def compare(monkeypatch, pages, stores=STORES):
    monkeypatch.setattr(serpapi, "available", lambda: True)
    monkeypatch.setattr(serpapi, "stores", lambda token: [dict(s) for s in stores])
    monkeypatch.setattr(pricing, "page_price", lambda url, timeout=0: pages.get(url.split("/")[2]))
    return pricing.compare("tok")


def test_picks_the_cheapest_reliable_store_and_confirms_its_price(monkeypatch):
    info = compare(monkeypatch, {"myntra.com": 600.0, "flipkart.com": 558.0, "ajio.com": None})  # AJIO refuses to be read
    names = [s["name"] for s in info["stores"]]
    assert names == ["Bestdeals4u", "AJIO.com", "Flipkart", "Myntra"]
    assert info["cheapest"]["name"] == "AJIO.com" or info["cheapest"]["name"] == "AJIO.com"
    by = {s["name"]: s for s in info["stores"]}
    assert by["Flipkart"]["verified"] is True and by["Myntra"]["verified"] is True and by["AJIO.com"]["verified"] is None
    assert by["Bestdeals4u"]["trusted"] is False


def test_the_page_price_wins_when_it_differs_from_the_listing(monkeypatch):
    info = compare(monkeypatch, {"flipkart.com": 640.0, "myntra.com": 600.0, "ajio.com": 375.0}, stores=STORES[:3])
    flip = next(s for s in info["stores"] if s["name"] == "Flipkart")
    assert flip["price_inr"] == 640 and flip["listed_price_inr"] == 558 and flip["verified"] == "corrected" and flip["price_display"] == "₹640"
    assert [s["name"] for s in info["stores"]] == ["AJIO.com", "Myntra", "Flipkart"]  # re-sorted by the real prices
    assert info["cheapest"]["name"] == "AJIO.com" and info["cheapest"]["verified"] is True


def test_a_store_we_cannot_vouch_for_is_never_the_one_to_buy_from(monkeypatch):
    stores = [STORES[3], STORES[1]]  # unknown shop at 300, AJIO at 375
    info = compare(monkeypatch, {"ajio.com": 375.0}, stores=stores)
    assert info["cheapest"]["name"] == "AJIO.com"
    only_unknown = compare(monkeypatch, {}, stores=[STORES[3]])
    assert only_unknown["cheapest"] is None and len(only_unknown["stores"]) == 1


def test_a_failed_store_lookup_is_harmless(monkeypatch):
    def boom(token):
        raise serpapi.SerpApiError("out of searches")
    monkeypatch.setattr(serpapi, "stores", boom)
    assert pricing.compare("tok") == {"stores": [], "cheapest": None}


def test_the_offer_is_shown_at_the_cheapest_reliable_stores_price_and_link(monkeypatch):
    info = compare(monkeypatch, {"flipkart.com": 558.0, "myntra.com": 600.0, "ajio.com": 375.0}, stores=STORES[:3])
    offer = {"title": "Kotty Jeans", "price_inr": 600, "price_display": "₹600", "seller": "Myntra", "link": None, "token": "tok"}
    shown = pricing.apply_to_offer(offer, info)
    assert (shown["price_display"], shown["seller"], shown["link"]) == ("₹375", "AJIO.com", "https://ajio.com/p")
    assert shown["price_verified"] is True and shown["seller_trusted"] is True and shown["token"] == "tok" and len(shown["stores"]) == 3
    assert pricing.apply_to_offer(offer, {"stores": [], "cheapest": None}) == offer  # nothing found: unchanged
    # only a store we cannot vouch for sells it: still the seller's own page (never Google), flagged as unreliable
    lone = compare(monkeypatch, {}, stores=[STORES[3]])
    flagged = pricing.apply_to_offer(offer, lone)
    assert flagged["link"] == "https://bestdeals4u.in/p" and flagged["seller_trusted"] is False and flagged["price_verified"] is False


def test_the_explanation_is_honest_about_what_was_checked(monkeypatch):
    info = compare(monkeypatch, {"myntra.com": 600.0, "flipkart.com": 558.0, "ajio.com": None})
    text = pricing.comparison_text(info["stores"])
    assert "Prices differ across stores" in text
    assert "AJIO.com at ₹375** (as listed; I couldn't open the page to check it)" in text  # reliable, cheapest, unconfirmed
    assert "Listed even lower at Bestdeals4u (₹300)" in text and "a store I can't vouch for" in text
    assert "Flipkart ₹558 ✓" in text and "Myntra ₹600 ✓" in text
    confirmed = pricing.comparison_text(compare(monkeypatch, {"flipkart.com": 558.0}, stores=STORES[2:3] + STORES[0:1])["stores"])
    assert "Flipkart at ₹558** (checked on the store's own page)" in confirmed
    assert pricing.comparison_text([{"name": "A", "price_inr": 5, "trusted": True}]) == ""
    assert "Same price" in pricing.comparison_text([{"name": "A", "price_inr": 5}, {"name": "B", "price_inr": 5}])
    assert "can't vouch" in pricing.comparison_text([{"name": "X", "price_inr": 5, "trusted": False}, {"name": "Y", "price_inr": 9, "trusted": False}])


# ----------------------------------------------------------------- routing the research
def test_serpapi_leads_and_the_others_back_it_up(monkeypatch):
    import app.sources.serpkite as sk
    monkeypatch.setattr(serpapi, "available", lambda: True)
    monkeypatch.setattr(sk, "_exhausted_until", 0.0)
    tasks = researcher.shopping_tasks(["a", "b", "c"])
    assert [(t["source"], t["query"]) for t in tasks] == [("serpapi", "a"), ("shopping", "b"), ("shopping", "c")]
    monkeypatch.setattr(sk, "_exhausted_until", 9e18)
    assert [t["source"] for t in researcher.shopping_tasks(["a", "b"])] == ["serpapi"]
    monkeypatch.setattr(serpapi, "available", lambda: False)
    assert [t["source"] for t in researcher.shopping_tasks(["a", "b"])] == ["tavily", "tavily", "web"]
    monkeypatch.setattr(sk, "_exhausted_until", 0.0)
    assert [t["source"] for t in researcher.shopping_tasks(["a", "b"])] == ["shopping", "shopping"]
    assert researcher.shopping_tasks([]) == []


def test_worker_runs_serpapi(monkeypatch):
    monkeypatch.setattr(researcher.serpapi, "search_shopping", lambda q: [{"title": q}])
    assert researcher.worker({"source": "serpapi", "query": "x"}) == {"raw_offers": [{"title": "x"}]}


def test_compare_endpoint(monkeypatch):
    import app.api.main as api
    monkeypatch.setattr(serpapi, "available", lambda: True)
    monkeypatch.setattr(serpapi, "stores", lambda token: [dict(s) for s in STORES[:3]])
    monkeypatch.setattr(pricing, "page_price", lambda url, timeout=0: {"myntra.com": 600.0, "flipkart.com": 558.0}.get(url.split("/")[2]))
    out = TestClient(api.app).post("/compare", json={"token": "tok"}).json()
    assert [s["name"] for s in out["stores"]] == ["AJIO.com", "Flipkart", "Myntra"]
    assert out["cheapest"]["seller"] == "AJIO.com" and out["cheapest"]["link"] == "https://ajio.com/p" and "Prices differ" in out["text"]


def test_brand_stores_written_as_domains_are_recognised():
    for name in ("hm.com", "H&M IN", "Wrangler India", "Campus Shoes", "nike.com"):
        assert pricing.is_trusted(name), name
    for name in ("Bestdeals4u", "Himalaya Fashion", "Shreeji Traders", "Leemarts"):
        assert not pricing.is_trusted(name), name


def test_no_store_lookups_when_serpapi_is_unavailable(monkeypatch):
    called = []
    monkeypatch.setattr(serpapi, "stores", lambda t: called.append(t) or [])
    assert pricing.compare("tok") == {"stores": [], "cheapest": None} and called == []
