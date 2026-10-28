import threading
import time

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import app.agents.memory as memory
import app.agents.presenter as presenter
import app.agents.requirements as requirements
import app.agents.researcher as researcher
from app.commands import ACCEPT, COMPARE, SHOW_ALTERNATIVES
from app.graph import chatbot, checkpointer
from app.memory import store as ltm_store


def shoe(name, price, rating=4.4, count=200):
    return (name, price, rating, count)


CATALOG = {
    "women running shoes": [shoe("Nike Quest 5 Women's", 3242, 4.6, 611), shoe("Skechers Women Go Run", 3374, 4.6, 517),
                            shoe("Puma Men's Softride", 3149, 4.0, 90), shoe("Asics Women Gel", 4100, 4.5, 300),
                            shoe("Brooks Women Ghost", 4900, 4.7, 150)],
    "stability running shoes": [shoe("Saucony Women's Guide", 4500, 4.5, 80), shoe("Nike Quest 5 Women's", 3242, 4.6, 611),
                                shoe("Adidas Women Duramo", 3000, 4.2, 400), shoe("Reebok Women Energy", 2900, 4.1, 250),
                                shoe("Mizuno Women Wave", 4700, 4.4, 60)],
    "running shoes": [shoe("Hoka Women Clifton", 4950, 4.8, 40), shoe("New Balance Women 880", 4800, 4.5, 70),
                      shoe("Under Armour Women Charged", 3900, 4.3, 120), shoe("Fila Women Zeal", 2500, 4.0, 55),
                      shoe("Decathlon Kalenji Women", 1999, 4.1, 900)],
    "laptop": [shoe("Alpha Dev 16GB", 70000, 4.6, 900)],
}


@pytest.fixture
def stubs(monkeypatch):
    calls = {"shopping": [], "threads": set(), "decider_saw": [], "compare": 0, "media": []}
    plans = []

    def decider(messages):
        calls["decider_saw"].append(messages[1].content)  # the "what is known" block
        return requirements.Plan(**plans.pop(0))

    def shopping(query):
        calls["shopping"].append(query)
        calls["threads"].add(threading.get_ident())
        time.sleep(0.3)  # a real search takes a while; parallel workers overlap this
        return [{"title": t, "price_inr": p, "price_display": f"₹{p}", "seller": "Shop", "rating": r,
                 "rating_count": c, "api": "google_shopping", "rank": i} for i, (t, p, r, c) in enumerate(CATALOG.get(query, []))]

    def media(items):
        calls["media"].append([title for title, _ in items])
        return [{"link": f"https://shop/{i}", "image_url": "img"} for i, _ in enumerate(items)]

    def compare(messages):
        calls["compare"] += 1
        return presenter.Comparison(tradeoffs=[presenter.Tradeoff(number=n, line=f"line {n}") for n in range(1, 30)], verdict="ok")

    monkeypatch.setattr(requirements.decider, "invoke", decider)
    monkeypatch.setattr(researcher, "shopping_offers", shopping)
    monkeypatch.setattr(researcher, "web_offers", lambda q: [])
    monkeypatch.setattr(researcher, "tavily_search", lambda q: [])
    monkeypatch.setattr(presenter, "find_media_many", media)
    monkeypatch.setattr(presenter.recommender, "invoke", lambda m: presenter.Recommendation(
        best_number=1, intro="Found a solid women's stability runner 👟", reasons=["fits your budget", "well reviewed"],
        follow_up="Want something lighter or more cushioned?", follow_up_topic="cushioning",
        follow_up_options=["Lighter", "More cushioned"]))
    monkeypatch.setattr(presenter.comparer, "invoke", compare)
    return calls, plans


def chat(thread_id, user_id, text):
    cfg = {"configurable": {"thread_id": thread_id, "user_id": user_id}, "recursion_limit": 25}
    return chatbot.invoke({"messages": [HumanMessage(content=text)]}, config=cfg), cfg


def test_search_first_then_more_options_then_accept(stubs, thread_id, user_id):
    calls, plans = stubs

    # 1. one message is enough to get results: no questionnaire. Two queries search in parallel.
    plans.append({"decision": "search", "product": "running_shoes", "facts": [{"topic": "gender", "value": "women"}],
                  "queries": ["women running shoes", "stability running shoes"],
                  "remember": [{"text": "Name is Heeral", "category": "person", "kind": "profile"}]})
    started = time.monotonic()
    out, cfg = chat(thread_id, user_id, "Help me buy cool running shoes, I'm Heeral")
    assert time.monotonic() - started < 0.55, "two 0.3s searches should overlap"
    assert len(calls["threads"]) == 2
    reply = out["messages"][-1].content
    assert reply.startswith("Found a solid women's stability runner") and "Want something lighter" in reply
    assert len(out["cards"]) == 1 and out["cards"][0]["best"] and out["cards"][0]["title"].startswith("Nike Quest 5")
    assert out["options"] == ["Lighter", "More cushioned", SHOW_ALTERNATIVES, COMPARE, ACCEPT[0]]
    assert out["profile"]["asked"] == ["cushioning"]
    assert sorted(t for call in calls["media"] for t in call) == sorted(t["title"] for t in out["offers"][:1]), \
        "images are fetched for the top candidate only, not the whole shortlist"
    assert out["saved"] == ["Saved: Name is Heeral"]
    # Men's shoes never reach the shortlist, duplicates are merged, scratch results are cleared
    titles = [o["title"] for o in out["offers"]]
    assert not any("Men's" in t for t in titles) and len(titles) == len(set(titles)) == 6
    assert len(out["reserve"]) == 2 and out["shown"] == [1]
    assert chatbot.get_state(cfg).values.get("raw_offers") == []

    # 2. "other options": the next unseen four, straight from what was found: no search, no requirements call
    searches, plans_left, media_calls = len(calls["shopping"]), len(plans), len(calls["media"])
    out, _ = chat(thread_id, user_id, SHOW_ALTERNATIVES)
    assert len(calls["shopping"]) == searches and len(plans) == plans_left and calls["compare"] == 1
    assert [c["number"] for c in out["cards"]] == [2, 3, 4, 5] and not any(c.get("best") for c in out["cards"])
    looked_up = [t for call in calls["media"][media_calls:] for t in call]
    assert sorted(looked_up) == sorted(c["title"] for c in out["cards"])  # exactly the four shown, nothing else
    assert out["shown"] == [1, 2, 3, 4, 5]

    # 3. again: the last listing plus the reserve are promoted and numbered, still no search
    out, _ = chat(thread_id, user_id, SHOW_ALTERNATIVES)
    assert len(calls["shopping"]) == searches
    assert [c["number"] for c in out["cards"]] == [6, 7, 8] and out["reserve"] == []

    # 4. everything seen: it searches again (appending) and shows what is new
    out, _ = chat(thread_id, user_id, SHOW_ALTERNATIVES)
    assert calls["shopping"][searches:] == ["running shoes"]
    assert [c["number"] for c in out["cards"]] == [9, 10, 11, 12]
    assert all(c["title"] not in titles for c in out["cards"])
    assert out["messages"][-1].content.startswith("Here are 4 more")

    # 5. accepting the pick is remembered
    out, _ = chat(thread_id, user_id, ACCEPT[0])
    assert out["saved"] and out["saved"][0].startswith("Saved: Picked Nike Quest 5")

    # 6. a new conversation: the name is recalled, and shoe memories are not shown for a laptop search
    plans.append({"decision": "search", "product": "laptop", "queries": ["laptop"]})
    out, _ = chat(thread_id + "-b", user_id, "now I need a laptop")
    known = calls["decider_saw"][-1]
    assert "Name is Heeral" in known and "Picked Nike Quest" not in known
    checkpointer.delete_thread(thread_id + "-b")


def test_conversation_chat_question_about_the_shortlist_does_not_search(stubs, thread_id, user_id):
    calls, plans = stubs
    plans.append({"decision": "search", "product": "running_shoes", "queries": ["women running shoes"]})
    chat(thread_id, user_id, "women running shoes")
    searches = len(calls["shopping"])
    plans.append({"decision": "chat", "message": "#1 has the most reviews. It's a safe pick. Want to compare?"})
    out, _ = chat(thread_id, user_id, "is the first one popular?")
    assert out["messages"][-1].content == "#1 has the most reviews. It's a safe pick. Want to compare?"
    assert len(calls["shopping"]) == searches and "#1 (recommended)" in calls["decider_saw"][-1]


def test_a_refinement_searches_again_with_the_change(stubs, thread_id, user_id):
    calls, plans = stubs
    plans.append({"decision": "search", "product": "running_shoes", "queries": ["women running shoes"]})
    chat(thread_id, user_id, "women running shoes")
    plans.append({"decision": "search", "mode": "refine", "queries": ["stability running shoes"], "budget_max": 3100})
    out, _ = chat(thread_id, user_id, "cheaper, under 3100")
    assert calls["shopping"][-1] == "stability running shoes"
    assert all(o["price_inr"] <= 3100 for o in out["offers"]) and out["profile"]["budget_max"] == 3100
    assert out["shown"] == [1]  # a refinement starts a fresh shortlist


def test_fallback_wave_runs_when_first_wave_is_thin(stubs, thread_id, user_id, monkeypatch):
    calls, plans = stubs
    web_calls, tavily_calls = [], []
    monkeypatch.setattr(researcher, "web_offers", lambda q: web_calls.append(q) or [])
    monkeypatch.setattr(researcher, "tavily_search", lambda q: tavily_calls.append(q) or [{
        "title": "Tavily Find", "price_inr": 1000, "price_display": "₹1,000", "seller": "amazon.in", "rating": None,
        "rating_count": None, "api": "tavily", "link": "https://amazon.in/x", "rank": 0}])
    monkeypatch.setitem(CATALOG, "obscure", [shoe("Only One", 1000, 4.0, 10)])
    plans.append({"decision": "search", "product": "laptop", "queries": ["obscure"]})
    out, _ = chat(thread_id, user_id, "find me an obscure thing")
    assert web_calls == ["obscure"] and tavily_calls == ["obscure"] and "laptop" in calls["shopping"]  # web: the specific query
    assert {o["title"] for o in out["offers"]} == {"Only One", "Tavily Find", "Alpha Dev 16GB"}


def test_shrink_trims_and_summarises(monkeypatch):
    msgs = []
    for i in range(10):
        msgs += [HumanMessage(content=f"q{i}", id=f"h{i}"), AIMessage(content=f"a{i}", id=f"a{i}")]
    monkeypatch.setattr(memory, "llm", type("L", (), {"invoke": lambda self, m: AIMessage(content="SUMMARY")})())
    out = memory.shrink_node({"messages": msgs, "summary": ""})
    kept = len(msgs) - len(out["messages"])
    assert out["summary"] == "SUMMARY" and kept <= memory.KEEP and out["messages"][0].id == "h0"
    assert memory.shrink_node({"messages": msgs[:6]}) == {}


def test_presenter_is_told_the_price_spread_when_no_budget_is_set(stubs, thread_id, user_id, monkeypatch):
    calls, plans = stubs
    seen = []
    base = presenter.recommender.invoke
    monkeypatch.setattr(presenter.recommender, "invoke", lambda m: seen.append(m[1].content) or base(m))
    plans.append({"decision": "search", "product": "running_shoes", "queries": ["women running shoes", "stability running shoes"]})
    chat(thread_id, user_id, "women running shoes")
    assert "No budget is set. These listings range from ₹2,900 to ₹" in seen[0]


# ----------------------------------------------------------------- understand first
JEANS = [shoe("Levi's Women's 724 High Rise Straight", 999, 4.5, 400), shoe("Kotty Women Straight Fit Jeans", 600, 4.2, 618),
         shoe("Tokyo Talkies Women Straight Fit", 531, 4.4, 34), shoe("Nifty Women Baggy Jeans", 629, 4.5, 99)]
FIT = {"topic": "fit", "question": "What kind of fit do you like?", "options": ["Straight", "Skinny", "Wide-leg"], "durable": True}
COLOUR = {"topic": "colour", "question": "Which colour or wash?", "options": ["Light blue", "Dark blue", "Black"], "durable": True}
OCCASION = {"topic": "occasion", "question": "What are they for?", "options": ["Everyday", "Office", "Party"]}
BUDGET = {"topic": "budget", "question": "What's your budget?", "options": ["Under ₹1,000", "₹1,000 to ₹2,000"]}


def test_it_understands_the_shopper_before_showing_anything(stubs, thread_id, user_id, monkeypatch):
    calls, plans = stubs
    monkeypatch.setitem(CATALOG, "women straight jeans", JEANS)

    # 1. "jeans": one model call writes the question plan, then the app asks the first question
    plans.append({"decision": "ask", "product": "jeans", "message": "Jeans, great!", "facts": [{"topic": "gender", "value": "women"}],
                  "attributes": [FIT, COLOUR, OCCASION, BUDGET]})
    out, _ = chat(thread_id, user_id, "I want some jeans for women")
    assert "**What kind of fit do you like?**" in out["messages"][-1].content and calls["shopping"] == []
    assert out["options"] == ["Straight", "Skinny", "Wide-leg", "Not sure, you suggest"]

    # 2-3. tapped answers: no model call at all, the next question comes straight back
    decider_calls = len(calls["decider_saw"])
    out, _ = chat(thread_id, user_id, "Straight")
    assert "**Which colour or wash?**" in out["messages"][-1].content and out["options"][-1] == "Just show me options"
    assert out["saved"] == ["Saved: Fit preference for jeans: Straight"]  # a lasting taste is remembered
    out, _ = chat(thread_id, user_id, "Dark blue")
    assert "**What are they for?**" in out["messages"][-1].content
    assert len(calls["decider_saw"]) == decider_calls, "tapped answers must not call the model"
    out, _ = chat(thread_id, user_id, "Office")
    assert "**What's your budget?**" in out["messages"][-1].content and out["saved"] == []  # an occasion is not a lasting taste

    # 4. the last answer: the model now writes the search, with everything learned in its context
    plans.append({"decision": "search", "queries": ["women straight jeans"]})
    out, _ = chat(thread_id, user_id, "Under ₹1,000")
    assert len(calls["decider_saw"]) == decider_calls + 1
    seen = calls["decider_saw"][-1]
    assert "fit: answered (Straight)" in seen and "occasion: answered (Office)" in seen and "Budget: 0 to 1000" in seen
    assert out["profile"]["budget_max"] == 1000 and out["cards"][0]["best"] and all(o["price_inr"] <= 1000 for o in out["offers"])
    texts = {m["text"] for m in ltm_store.all_memories(ltm_store.ltm, user_id)}
    assert {"Fit preference for jeans: Straight", "Colour preference for jeans: Dark blue"} <= texts
    assert not any("Office" in t or "1,000" in t for t in texts)


def test_just_show_me_skips_the_remaining_questions(stubs, thread_id, user_id, monkeypatch):
    calls, plans = stubs
    monkeypatch.setitem(CATALOG, "women straight jeans", JEANS)
    plans.append({"decision": "ask", "product": "jeans", "attributes": [FIT, COLOUR, OCCASION, BUDGET]})
    chat(thread_id, user_id, "jeans")
    chat(thread_id, user_id, "Straight")
    plans.append({"decision": "ask", "queries": ["women straight jeans"]})  # even if the model keeps asking
    out, _ = chat(thread_id, user_id, "Just show me options")
    assert out["cards"] and out["cards"][0]["best"] and calls["shopping"]


# ----------------------------------------------------------------- price comparison across stores
def test_the_pick_is_shown_at_the_cheapest_reliable_store_with_that_stores_link(stubs, thread_id, user_id, monkeypatch):
    import app.pricing as pricing
    import app.sources.serpapi as serpapi
    calls, plans = stubs
    searched = []
    rows = [{"title": "Kotty Women Straight Fit High-Rise Jeans", "price_inr": 600, "price_display": "₹600", "seller": "Myntra",
             "rating": 4.2, "rating_count": 618, "image_url": "https://img/kotty", "link": None,
             "token": "tok-kotty", "api": "serpapi", "rank": 0},
            {"title": "Levi's Women High Rise Jeans", "price_inr": 1040, "price_display": "₹1,040", "seller": "Amazon.in",
             "rating": 4.4, "rating_count": 90, "image_url": "https://img/levis", "link": None,
             "token": "tok-levis", "api": "serpapi", "rank": 1},
            {"title": "Nifty Women Baggy Jeans", "price_inr": 629, "price_display": "₹629", "seller": "Amazon.in", "rating": 4.5,
             "rating_count": 99, "image_url": "https://img/nifty", "link": None,
             "token": "tok-nifty", "api": "serpapi", "rank": 2}]
    monkeypatch.setattr(serpapi, "available", lambda: True)
    monkeypatch.setattr(serpapi, "search_shopping", lambda q: searched.append(q) or [dict(r) for r in rows])
    stores = [{"name": "Myntra", "price_inr": 600, "price_display": "₹600", "link": "https://myntra.com/kotty"},
              {"name": "AJIO.com", "price_inr": 375, "price_display": "₹375", "link": "https://ajio.com/kotty"},
              {"name": "Flipkart", "price_inr": 558, "price_display": "₹558", "link": "https://flipkart.com/kotty"},
              {"name": "Bestdeals4u", "price_inr": 300, "price_display": "₹300", "link": "https://bestdeals4u.in/kotty"}]
    monkeypatch.setattr(serpapi, "stores", lambda token: [dict(s) for s in stores])
    pages = {"myntra.com": 600.0, "flipkart.com": 558.0}  # AJIO refuses automated checks
    monkeypatch.setattr(pricing, "page_price", lambda url, timeout=0: pages.get(url.split("/")[2]))
    monkeypatch.setattr(presenter.recommender, "invoke", lambda m: presenter.Recommendation(
        best_number=1, intro="Found a good pair 👖", reasons=["straight fit as you wanted", "well reviewed"]))

    plans.append({"decision": "search", "product": "jeans", "queries": ["women straight jeans", "straight high rise jeans"]})
    out, _ = chat(thread_id, user_id, "women straight jeans")

    # SerpAPI is the primary source: it gets the lead query, the second shopping API gets the other one
    assert searched == ["women straight jeans"] and calls["shopping"] == ["straight high rise jeans"]
    reply = out["messages"][-1].content
    card = out["cards"][0]
    assert "Kotty Women Straight Fit High-Rise Jeans** at **₹375**" in reply and "from AJIO.com" in reply  # not Myntra's ₹600
    assert "Prices differ across stores" in reply
    assert "Cheapest reliable store I found: **AJIO.com at ₹375** (as listed; I couldn't open the page to check it)" in reply
    assert "Listed even lower at Bestdeals4u (₹300)" in reply and "a store I can't vouch for" in reply
    assert "Flipkart ₹558 ✓" in reply and "Myntra ₹600 ✓" in reply
    assert (card["price_display"], card["seller"], card["link"]) == ("₹375", "AJIO.com", "https://ajio.com/kotty")
    assert [s["name"] for s in card["stores"]] == ["Bestdeals4u", "AJIO.com", "Flipkart", "Myntra"] and card["token"] == "tok-kotty"
    assert calls["media"] == [], "SerpAPI listings come with pictures: no image lookups"
    # listings not shown yet keep their listed price and have no link at all (certainly not a Google one)
    other = next(o for o in out["offers"] if o["title"].startswith("Levi's"))
    assert other["price_display"] == "₹1,040" and other["link"] is None and "stores" not in other
    assert "google" not in str(out["offers"]).lower() and "google" not in reply.lower()


def test_everything_stays_inside_barney_pick_other_options_and_side_by_side(stubs, thread_id, user_id, monkeypatch):
    import app.agents.table as table
    import app.pricing as pricing
    import app.sources.serpapi as serpapi
    calls, plans = stubs
    names = ["Kotty Women Straight Jeans", "Levi's Women High Rise Jeans", "Nifty Women Baggy Jeans"]
    rows = [{"title": t, "price_inr": 600 + 100 * i, "price_display": f"₹{600 + 100 * i}", "seller": "Myntra", "rating": 4.5 - i / 10,
             "rating_count": 500 - 100 * i, "image_url": f"https://img/{i}", "link": None, "token": f"tok{i}", "api": "serpapi", "rank": i}
            for i, t in enumerate(names)]
    monkeypatch.setattr(serpapi, "available", lambda: True)
    monkeypatch.setattr(serpapi, "search_shopping", lambda q: [dict(r) for r in rows])
    lookups = []

    def stores(token):
        lookups.append(token)
        i = int(token[3:])
        return [{"name": "Myntra", "price_inr": 700 + 100 * i, "price_display": f"₹{700 + 100 * i}", "link": f"https://myntra.com/{i}"},
                {"name": "Flipkart", "price_inr": 650 + 100 * i, "price_display": f"₹{650 + 100 * i}", "link": f"https://flipkart.com/{i}"}]

    monkeypatch.setattr(serpapi, "stores", stores)
    monkeypatch.setattr(pricing, "page_price", lambda url, timeout=0: None)
    monkeypatch.setattr(presenter.recommender, "invoke", lambda m: presenter.Recommendation(best_number=1, reasons=["fits"]))
    monkeypatch.setattr(table.extractor, "invoke", lambda m: table.SpecTable(
        specs=["Fit", "Rise"], verdict="#1 fits best.", rows=[
            {"number": n, "values": {"Fit": "Straight", "Rise": "High" if n == 1 else None}, "matches": {"Straight fit": "yes"}} for n in (1, 2, 3)]))

    plans.append({"decision": "search", "product": "jeans", "facts": [{"topic": "fit", "value": "Straight"}], "queries": ["women jeans"]})
    out, _ = chat(thread_id, user_id, "women straight jeans")
    assert "**Matched on:** Straight fit" in out["messages"][-1].content  # the shopper's context, stated
    assert COMPARE in out["options"] and lookups == ["tok0"]  # only the pick's stores were looked up so far

    # other options: every card is resolved inside Barney, with the seller's own link
    out, _ = chat(thread_id, user_id, SHOW_ALTERNATIVES)
    assert sorted(lookups) == ["tok0", "tok1", "tok2"]
    assert all(c["link"].startswith(("https://flipkart.com", "https://myntra.com")) and len(c["stores"]) == 2 for c in out["cards"])
    assert all(c["seller"] == "Flipkart" for c in out["cards"])  # the cheaper store of the two
    assert COMPARE in out["options"]

    # side by side: normalised specs, the shopper's needs, verified-or-listed prices, links to the original sellers
    searches = len(calls["decider_saw"])
    out, _ = chat(thread_id, user_id, COMPARE)
    t = out["table"]
    assert len(calls["decider_saw"]) == searches, "a button press needs no requirements call"
    assert [r["number"] for r in t["rows"]] == [1, 2, 3] and t["specs"] == ["Fit", "Rise"]
    assert t["requirements"] == ["Straight fit"] and t["rows"][0]["matches"] == {"Straight fit": "yes"} and t["rows"][0]["best"]
    assert [r["price_display"] for r in t["rows"]] == ["₹650", "₹750", "₹850"] and all(r["link"].startswith("https://flipkart.com") for r in t["rows"])
    assert out["messages"][-1].content == "#1 fits best."
    assert lookups.count("tok0") == 1, "stores already looked up are not fetched (or paid for) again"
    assert "google" not in str((out, t)).lower()
    # the table belongs to that turn only
    plans.append({"decision": "chat", "message": "Sure!"})
    assert chat(thread_id, user_id, "thanks")[0]["table"] is None


def test_a_greeting_never_touches_the_shopping_model_or_the_search(stubs, thread_id, user_id, monkeypatch):
    import app.agents.smalltalk as smalltalk
    calls, plans = stubs
    asked = []
    monkeypatch.setattr(smalltalk, "chat_llm", type("C", (), {"invoke": lambda self, m: asked.append(m) or type("R", (), {"content": "Hey! 👋 What are you after?"})()})())
    out, _ = chat(thread_id, user_id, "hey barney")
    assert out["messages"][-1].content == "Hey! 👋 What are you after?" and len(asked) == 1
    assert calls["decider_saw"] == [] and calls["shopping"] == [] and out["cards"] == [] and out["table"] is None
