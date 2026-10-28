from langchain_core.messages import HumanMessage

import app.agents.table as table
from app.agents.common import matched_on_text, requirement_labels
from app.agents.supervisor import route_after_supervisor, supervisor_node
from app.commands import COMPARE

OFFERS = [
    {"number": n, "title": t, "price_inr": p, "price_display": f"₹{p}", "seller": s, "rating": 4.4, "rating_count": 100 + n,
     "image_url": f"img{n}", "link": f"https://{s.lower()}.com/{n}", "token": None}
    for n, t, p, s in [(1, "Levi's 724 High Rise Straight Jeans Dark Indigo", 1999, "Myntra"), (2, "Kotty Women Straight Fit Jeans Blue", 600, "AJIO"),
                       (3, "Skinny Fit Low Rise Black Jeans", 700, "Flipkart")]]
PROFILE = {"product": "jeans", "pick": 1, "budget_max": 2500, "facts": {"fit": "Straight", "rise": "High", "colour": "open to suggestions"}}


def stub(monkeypatch, result):
    seen = []
    monkeypatch.setattr(table.extractor, "invoke", lambda m: seen.append(m) or result)
    monkeypatch.setattr(table, "prepare_all", lambda offers: [dict(o) for o in offers])
    return seen


def run(shown=(1, 2, 3), **state):
    return table.compare_node({"profile": PROFILE, "offers": OFFERS, "shown": list(shown), **state})


# ----------------------------------------------------------------- the shopper's context, made explicit
def test_requirements_are_listed_as_labels_and_memories_are_marked():
    mems = [{"text": "Likes dark indigo jeans", "category": "jeans", "kind": "preference"},
            {"text": "Wears size 5 in shoes", "category": "shoes", "kind": "profile"},
            {"text": "Fit preference for jeans: Straight", "category": "jeans", "kind": "preference"}]
    labels = requirement_labels(PROFILE, mems)
    assert labels == [("Straight fit", False), ("High rise", False), ("under ₹2,500", False), ("Likes dark indigo jeans", True)]
    # "open to suggestions" is not a requirement, shoe memories do not leak into jeans, a remembered fit already stated is not repeated
    assert matched_on_text(PROFILE, mems) == "**Matched on:** Straight fit · High rise · under ₹2,500 · 🧠 Likes dark indigo jeans"
    assert matched_on_text({"product": "jeans"}, []) == ""
    assert requirement_labels({"budget_min": 500, "budget_max": 900}) == [("₹500 to ₹900", False)]
    # readable labels: a bare value gets its topic, the product's own name and plain topics do not
    facts = {"gender": "women", "category": "jeans", "rise": "High", "color": "dark blue", "wash": "Dark indigo", "fit": "Straight fit"}
    assert [l for l, _ in requirement_labels({"product": "jeans", "facts": facts})] == ["women", "High rise", "dark blue color", "Dark indigo wash", "Straight fit"]


# ----------------------------------------------------------------- the comparison
def test_the_table_has_normalised_specs_matches_and_verified_prices(monkeypatch):
    result = table.SpecTable(specs=["Fit", "Rise", "Colour"], verdict="#1 matches your fit and rise; #2 is cheaper but its rise is unstated.", rows=[
        {"number": 1, "values": {"Fit": "Straight", "Rise": "High", "Colour": "Dark indigo"}, "matches": {"Straight fit": "yes", "High rise": "yes", "under ₹2,500": "no"}},
        {"number": 2, "values": {"Fit": "Straight", "Rise": None, "Colour": "Blue"}, "matches": {"Straight fit": "yes", "High rise": "bogus"}}])
    seen = stub(monkeypatch, result)
    out = run()
    t = out["table"]
    assert t["specs"] == ["Fit", "Rise", "Colour"] and t["requirements"] == ["Straight fit", "High rise", "under ₹2,500"]
    one, two, three = t["rows"]
    assert one["best"] and not two["best"] and one["price_display"] == "₹1999" and one["seller"] == "Myntra" and one["link"].startswith("https://myntra")
    assert one["values"] == {"Fit": "Straight", "Rise": "High", "Colour": "Dark indigo"} and two["values"]["Rise"] is None
    # the budget is computed from the real price (₹1,999 is under ₹2,500) even though the model said "no"
    assert one["matches"] == {"Straight fit": "yes", "High rise": "yes", "under ₹2,500": "yes"}
    assert two["matches"]["High rise"] == "unknown"  # an invalid answer from the model becomes "unknown", never "yes"
    assert three["values"] == {"Fit": None, "Rise": None, "Colour": None}  # the model skipped it
    assert three["matches"] == {"Straight fit": "unknown", "High rise": "unknown", "under ₹2,500": "yes"}
    assert out["messages"][-1].content.startswith("#1 matches your fit") and out["route"] == "end"
    assert "Straight fit | High rise | under ₹2,500" in seen[0][1].content and "current recommendation is #1" in seen[0][1].content


def test_it_compares_what_was_shown_and_needs_two_options(monkeypatch):
    stub(monkeypatch, table.SpecTable(specs=["Fit"], rows=[]))
    assert [r["number"] for r in run(shown=(1, 3))["table"]["rows"]] == [1, 3]
    assert [r["number"] for r in run(shown=(2,))["table"]["rows"]] == [1, 2, 3]  # only one seen: compare the shortlist
    too_few = table.compare_node({"profile": PROFILE, "offers": OFFERS[:1], "shown": [1]})
    assert too_few["table"] is None and "at least two" in too_few["messages"][-1].content


def test_the_compare_button_and_the_compare_intent_route_to_the_table():
    def route(said, plan=None, offers=OFFERS):
        return supervisor_node({"messages": [HumanMessage(content=said)], "plan": plan or {}, "profile": PROFILE, "offers": offers})
    assert route_after_supervisor(route(COMPARE)) == "compare"
    assert route_after_supervisor(route("compare them", {"decision": "compare"})) == "compare"
    assert route_after_supervisor(route(COMPARE, offers=OFFERS[:1])) == "__end__"  # nothing to compare yet
    assert route_after_supervisor({"route": "compare"}) == "compare"


def test_the_budget_is_judged_from_the_real_price():
    from app.agents.common import within_budget
    assert within_budget({"budget_max": 1500}, 1499) == "yes" and within_budget({"budget_max": 1500}, 1501) == "no"
    assert within_budget({"budget_min": 500, "budget_max": 900}, 400) == "no" and within_budget({"budget_min": 500, "budget_max": 900}, 700) == "yes"
    assert within_budget({}, 700) == "unknown" and within_budget({"budget_max": 900}, None) == "unknown"
