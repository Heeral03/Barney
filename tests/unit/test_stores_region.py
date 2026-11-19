import pytest

import app.region as region
import app.stores as stores


def test_a_link_is_genuine_only_on_a_registered_stores_own_domain():
    assert stores.usable("https://www.amazon.in/dp/B0123", "IN")
    assert stores.usable("https://m.flipkart.com/p/x", "IN")  # a subdomain of the store's own domain
    for fake in ("https://amazon.in.deals-now.xyz/p", "https://notamazon.in/p", "https://flipkart.com.evil.example/p",
                 "ftp://amazon.in/p", "javascript:alert(1)", "", "amazon.in/p"):
        assert not stores.usable(fake, "IN"), fake


def test_plain_http_links_to_a_genuine_store_are_upgraded_not_refused():
    assert stores.usable("http://www.myntra.com/p", "IN") and stores.secure("http://www.myntra.com/p") == "https://www.myntra.com/p"
    assert stores.secure("https://www.myntra.com/p") == "https://www.myntra.com/p" and not stores.usable("http://evil.example/p", "IN")


def test_a_store_must_deliver_to_the_shoppers_country():
    assert stores.usable("https://www.amazon.in/p", "IN") and not stores.usable("https://www.amazon.in/p", "US")
    assert stores.usable("https://www.walmart.com/ip/1", "US") and not stores.usable("https://www.walmart.com/ip/1", "IN")
    assert stores.usable("https://www.asos.com/p", "BR")  # ships worldwide


def test_a_seller_name_alone_is_never_enough_but_it_can_rule_a_store_out():
    assert stores.name_verdict("Amazon.in", "IN") is True
    assert stores.name_verdict("Amazon.in", "US") is False  # known, and does not deliver there
    assert stores.name_verdict("Amazon Deals Outlet", "IN") is None  # not the store, only starts with its name
    assert stores.name_verdict("Bestdeals4u", "IN") is None
    assert stores.name_verdict("Decathlon", "US") is True  # a brand with a store per country: any that serves counts


def test_extra_stores_can_be_added_without_code(monkeypatch):
    assert not stores.usable("https://shop.example.com/p", "IN")
    monkeypatch.setenv("EXTRA_STORES", "shop.example.com:IN|US")
    assert stores.usable("https://shop.example.com/p", "IN") and stores.usable("https://shop.example.com/p", "US")
    assert not stores.usable("https://shop.example.com/p", "GB")


def test_search_domains_are_the_stores_that_serve_a_country():
    in_domains = stores.domains_for("IN")
    assert "amazon.in" in in_domains and "walmart.com" not in in_domains


def test_the_country_comes_from_the_shopper_then_the_connection_then_india():
    assert region.resolve("us", "IN") == "US"
    assert region.resolve(None, "gb") == "GB" and region.resolve("", "uk") == "GB"
    assert region.resolve(None, None) == "IN" and region.resolve(None, "zz1") == "IN"
    assert region.from_accept_language("en-AU,en;q=0.9") == "AU" and region.from_accept_language("en") == ""
    assert region.supported("IN") and not region.supported("BR")


def test_the_search_uses_the_shoppers_market(monkeypatch):
    import app.sources.serpapi as serpapi
    seen = []
    monkeypatch.setattr(serpapi, "_get", lambda params, timeout=15: seen.append(params) or {"shopping_results": []})
    serpapi.search_shopping.__wrapped__("jeans", "GB")
    assert seen[0]["gl"] == "uk" and seen[0]["location"] == "United Kingdom"


@pytest.mark.parametrize("country,expected", [("IN", "₹1,200"), ("US", "$1,200")])
def test_money_follows_the_market(country, expected):
    assert region.money(1200, country) == expected
