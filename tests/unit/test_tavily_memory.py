import httpx
import pytest
from langchain_core.messages import HumanMessage

import app.agents.memory as memory
import app.sources.tavily as tavily
from app.agents.common import relevant_memories
from app.commands import ACCEPT, SHOW_ALTERNATIVES
from app.memory import store as ltm_store
from app.memory import writer


# ----------------------------------------------------------------- Tavily
def test_price_reader_ignores_emi_and_mrp():
    assert tavily.read_price("Shoes MRP: ₹9999. Starting from ₹352/month. Get this for only ₹4,999") == 4999
    assert tavily.read_price("Discount Price ₹1099. MRP: ₹1999. incl taxes") == 1099
    assert tavily.read_price("₹899 with EMI from ₹150 per month") == 899
    assert tavily.read_price("no price here") is None


def test_tavily_offers_parse_and_skip_search_pages(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    rows = [
        {"title": "Search", "url": "https://www.amazon.in/s?k=shoes", "content": "₹100"},
        {"title": "Nike Quest", "url": "https://www.amazon.in/dp/1", "content": "Price ₹3,499. EMI ₹300/month"},
        {"title": "No price", "url": "https://www.flipkart.com/p/2", "content": "great shoes"},
    ]
    monkeypatch.setattr(tavily.httpx, "post", lambda *a, **k: httpx.Response(200, json={"results": rows}, request=httpx.Request("POST", "x")))
    out = tavily.tavily_offers("running shoes")
    assert [o["title"] for o in out] == ["Nike Quest", "No price"]  # priced first, search page skipped
    assert out[0]["price_inr"] == 3499 and out[0]["seller"] == "amazon.in" and out[0]["api"] == "tavily"
    assert out[1]["price_display"] == "See price on site"


def test_tavily_failure_or_missing_key_returns_nothing(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert tavily.tavily_offers("x") == []
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    monkeypatch.setattr(tavily.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("down")))
    assert tavily.tavily_offers("x") == []


# ----------------------------------------------------------------- memory
MEMS = [{"text": "Name is Heeral", "category": "person"}, {"text": "Uses a laptop for heavy coding", "category": "laptop"},
        {"text": "Wears size 5 in shoes", "category": "shoes"}]


def test_memories_are_scoped_to_the_product():
    texts = lambda p: [m["text"] for m in relevant_memories(MEMS, p)]
    assert texts("running_shoes") == ["Name is Heeral", "Wears size 5 in shoes"]
    assert texts("gaming laptop") == ["Name is Heeral", "Uses a laptop for heavy coding"]
    assert len(texts(None)) == 3  # product not known yet: nothing is hidden


def test_writer_filters_what_is_saved():
    items = [{"text": "Wears size 5 in shoes", "category": "Shoes Footwear", "kind": "bogus"},
             {"text": "my email is a@b.com", "category": "person"}, {"text": "  "}, {"text": "x" * 200},
             {"text": "Second fact"}, {"text": "Third fact"}, {"text": "Heeral"}]
    out = writer.clean(items)
    assert out[0] == {"text": "Wears size 5 in shoes", "category": "shoes", "kind": "preference", "key": None}
    assert [m["text"] for m in out] == ["Wears size 5 in shoes", "Second fact"]  # capped, and "Heeral" (one word) is not a statement
    assert len(out) == writer.MAX_PER_TURN


def test_commit_saves_what_the_plan_says_and_updates_restated_facts(user_id):
    cfg = {"configurable": {"user_id": user_id}}
    plan = {"remember": [{"text": "Wears size 5 in shoes", "category": "shoes", "kind": "profile"}]}
    state = {"messages": [HumanMessage(content="size 5")], "plan": plan}
    assert memory.commit_node(state, cfg, store=ltm_store.ltm)["saved"] == ["Saved: Wears size 5 in shoes"]
    plan["remember"][0]["text"] = "Wears size 6 in shoes"
    assert memory.commit_node(state, cfg, store=ltm_store.ltm)["saved"] == ["Updated: Wears size 6 in shoes"]
    assert [m["text"] for m in ltm_store.all_memories(ltm_store.ltm, user_id)] == ["Wears size 6 in shoes"]


def test_commit_saves_nothing_for_buttons_and_empty_plans(user_id):
    cfg = {"configurable": {"user_id": user_id}}
    plan = {"remember": [{"text": "Should not be saved"}]}
    assert memory.commit_node({"messages": [HumanMessage(content=SHOW_ALTERNATIVES)], "plan": plan}, cfg, store=ltm_store.ltm)["saved"] == []
    assert memory.commit_node({"messages": [HumanMessage(content="hi")], "plan": {}}, cfg, store=ltm_store.ltm)["saved"] == []
    assert ltm_store.all_memories(ltm_store.ltm, user_id) == []


def test_accepting_a_pick_is_remembered(user_id):
    cfg = {"configurable": {"user_id": user_id}}
    state = {"messages": [HumanMessage(content=ACCEPT[0])], "profile": {"product": "running_shoes", "pick": 2},
             "offers": [{"number": 2, "title": "Nike Quest 5", "price_display": "₹3,242"}]}
    out = memory.commit_node(state, cfg, store=ltm_store.ltm)
    assert out["saved"] == ["Saved: Picked Nike Quest 5 (₹3,242) as their running shoes"]


def test_recall_returns_person_facts_plus_semantic_hits_and_load_dedupes(user_id):
    cfg = {"configurable": {"user_id": user_id}}
    ltm_store.remember(ltm_store.ltm, user_id, "Name is Heeral", "person", "profile")
    ltm_store.remember(ltm_store.ltm, user_id, "Wears size 5 in shoes", "shoes", "profile")
    out = memory.recall_node({"messages": [HumanMessage(content="what shoe size")], "profile": {}}, cfg, store=ltm_store.ltm)
    assert {m["text"] for m in out["fresh"]} == {"Name is Heeral", "Wears size 5 in shoes"}
    assert set(out["fresh"][0]) == {"text", "category", "kind"}
    loaded = memory.load_node({"fresh": out["fresh"], "recalled": out["fresh"][:1]})["recalled"]
    assert len(loaded) == 2
    assert memory.route_after_recall({"fresh": []}) == "__end__" and memory.route_after_recall({"fresh": [1]}) == "load"


def test_category_pages_and_filter_prices_are_not_listings(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    rows = [{"title": "Shop adidas Women's Running Shoes under ₹3000", "url": "https://www.myntra.com/adidas-shoes", "content": "under ₹3000"},
            {"title": "Nike Revolution 8", "url": "https://www.nike.com/in/p/rev8", "content": "Buy now under ₹5000 limit. Price ₹4,295"},
            {"title": "Women's shoes", "url": "https://www.ajio.com/c/shoes", "content": "₹999"}]
    monkeypatch.setattr(tavily.httpx, "post", lambda *a, **k: httpx.Response(200, json={"results": rows}, request=httpx.Request("POST", "x")))
    out = tavily.tavily_offers("running shoes")
    assert [o["title"] for o in out] == ["Nike Revolution 8"] and out[0]["price_inr"] == 4295


def test_threads_saved_by_older_versions_still_load():
    from app.agents.common import as_memory
    old = ["Uses laptop for heavy coding (laptop)", "Name is Heeral", "Spent about ₹1 to 2 lakh on a laptop (laptop)"]
    assert as_memory(old[0]) == {"text": "Uses laptop for heavy coding", "category": "laptop"}
    assert as_memory(old[1]) == {"text": "Name is Heeral", "category": "general"}
    loaded = memory.load_node({"fresh": [{"text": "Wears size 5", "category": "shoes", "kind": "profile"}], "recalled": old})["recalled"]
    assert [m["text"] for m in loaded] == ["Wears size 5", "Uses laptop for heavy coding", "Name is Heeral",
                                           "Spent about ₹1 to 2 lakh on a laptop"]
    assert [m["text"] for m in relevant_memories(old, "laptop")] == ["Uses laptop for heavy coding", "Name is Heeral",
                                                                     "Spent about ₹1 to 2 lakh on a laptop"]


def test_preferences_from_different_questions_never_overwrite_each_other(user_id):
    cfg = {"configurable": {"user_id": user_id}}
    commit = lambda text, topic: memory.commit_node(
        {"messages": [HumanMessage(content="x")],
         "plan": {"remember": [{"text": text, "category": "jeans", "kind": "preference", "key": f"pref:jeans:{topic}"}]}},
        cfg, store=ltm_store.ltm)["saved"]
    assert commit("Fit preference for jeans: Straight", "fit") == ["Saved: Fit preference for jeans: Straight"]
    assert commit("Rise preference for jeans: High", "rise") == ["Saved: Rise preference for jeans: High"]  # not "Updated"
    assert commit("Color preference for jeans: Dark blue", "color") == ["Saved: Color preference for jeans: Dark blue"]
    assert commit("Rise preference for jeans: High", "rise") == []  # same answer again: nothing to do
    assert commit("Fit preference for jeans: Skinny", "fit") == ["Updated: Fit preference for jeans: Skinny"]  # a changed mind
    assert {m["text"] for m in ltm_store.all_memories(ltm_store.ltm, user_id)} == {
        "Fit preference for jeans: Skinny", "Rise preference for jeans: High", "Color preference for jeans: Dark blue"}


def test_only_single_product_pages_are_listings():
    ok = [("https://www.flipkart.com/lee-skinny-women-blue-jeans/p/itme46", "LEE Skinny Jeans"),
          ("https://www.amazon.in/Levis-Womens/dp/B0GS3HJ6Q7", "Buy Levi's Women's 721 Jeans at Amazon.in")]
    bad = [("https://levi.in/collections/women-jeans", "Buy Jeans for Women Online"), ("https://www.myntra.com/women-super-skinny-jeans", "x"),
           ("https://www.amazon.in/skinny-jeans/s?k=skinny+jeans", "Amazon.in : skinny jeans"),
           ("https://www.flipkart.com/jeans/p/itm1", "Jeans Price List in India on 13 Oct 2026")]
    assert all(tavily.is_product_page(u, t) for u, t in ok) and not any(tavily.is_product_page(u, t) for u, t in bad)
    assert tavily.clean_title("LEE Skinny Jeans - Buy LEE Skinny Jeans Online at Best Pri") == "LEE Skinny Jeans"
    assert tavily.clean_title("Buy Levi's Women's 721 Jeans at Amazon.in") == "Levi's Women's 721 Jeans"
