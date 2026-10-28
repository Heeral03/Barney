from langchain_core.messages import HumanMessage

from app.agents.supervisor import route_after_supervisor, supervisor_node
from app.commands import ACCEPT, BROADEN, MAX_QUESTIONS, RAISE_BUDGET, SHOW_ALTERNATIVES


def run(said, plan=None, **state):
    return supervisor_node({"messages": [HumanMessage(content=said)], "plan": plan or {}, **state})


ASK = {"decision": "ask", "question": "Who is it for?", "question_topic": "recipient", "options": ["Me", "other"]}
SHOWN = [{"number": 1, "title": "x"}]


def test_ask_records_topic_and_adds_not_sure():
    out = run("a gift", ASK, profile={"product": "gift"})
    assert out["route"] == "end" and out["profile"]["asked"] == ["recipient"]
    assert "**Who is it for?**" in out["messages"][0].content
    assert out["options"] == ["Me", "Not sure, you suggest"]  # "other" dropped


ATTRS = [
    {"topic": "fit", "question": "What fit do you like?", "options": ["Straight", "Skinny", "other"], "durable": True},
    {"topic": "colour", "question": "Which colour?", "options": ["Blue", "Black"], "durable": True},
    {"topic": "occasion", "question": "What for?", "options": ["Everyday", "Office"]},
    {"topic": "budget", "question": "What budget?", "options": ["Under ₹1,000", "₹1,000 to ₹2,000"]},
    {"topic": "material", "question": "Fabric?", "options": ["Denim"]},
]


def test_it_walks_through_the_question_plan_before_searching():
    profile = {"product": "jeans", "attrs": ATTRS}
    out = run("jeans for women", {"decision": "search", "queries": ["women jeans"], "message": "Nice, jeans!"}, profile=profile)
    assert out["route"] == "end" and "**What fit do you like?**" in out["messages"][0].content
    assert out["options"] == ["Straight", "Skinny", "Not sure, you suggest"]  # "other" dropped, no skip on the first question
    assert out["profile"]["asked"] == ["fit"]
    assert out["profile"]["pending"] == {"topic": "fit", "options": ["Straight", "Skinny"], "durable": True}
    second = run("Straight", {"decision": "ask"}, profile={**out["profile"], "facts": {"fit": "Straight"}})
    assert "**Which colour?**" in second["messages"][0].content
    assert second["options"] == ["Blue", "Black", "Not sure, you suggest", "Just show me options"]  # a way out from question 2


def test_it_stops_asking_after_the_cap_the_skip_and_when_results_exist():
    four = {"product": "jeans", "attrs": ATTRS, "asked": ["fit", "colour", "occasion", "budget"]}
    assert run("x", {"decision": "ask", "queries": ["q"]}, profile=four)["route"] == "research"  # cap reached
    skipped = {"product": "jeans", "attrs": ATTRS, "skip": True}
    assert run("just show me", {"decision": "search", "queries": ["q"]}, profile=skipped)["route"] == "research"
    assert run("x", {"decision": "search", "queries": ["q"]}, profile={"product": "jeans", "attrs": ATTRS}, offers=SHOWN)["route"] == "research"


def test_attributes_already_known_are_not_asked_again():
    profile = {"product": "jeans", "attrs": ATTRS, "facts": {"Fit": "straight", "color": "blue"}, "asked": []}
    assert "**What for?**" in run("x", {"decision": "ask"}, profile=profile)["messages"][0].content
    profile["budget_max"] = 1000
    profile["facts"]["occasion"] = "office"
    assert "**Fabric?**" in run("x", {"decision": "ask"}, profile=profile)["messages"][0].content


def test_pending_question_is_cleared_when_it_searches():
    out = run("x", {"decision": "search", "queries": ["q"]}, profile={"product": "p", "pending": {"topic": "fit"}})
    assert "pending" not in out["profile"]


def test_questions_are_allowed_again_once_there_are_results():
    out = run("hmm", ASK, profile={"product": "laptop", "asked": ["budget"]}, offers=SHOWN)
    assert out["route"] == "end" and out["profile"]["asked"] == ["budget", "recipient"]


def test_repeated_topic_and_question_budget_become_search():
    plan = {**ASK, "queries": ["q"]}
    assert run("x", plan, profile={"product": "p", "asked": ["recipient"]}, offers=SHOWN)["route"] == "research"
    asked = [f"t{i}" for i in range(MAX_QUESTIONS)]
    assert run("x", plan, profile={"product": "p", "asked": asked}, offers=SHOWN)["route"] == "research"


def test_no_product_never_searches():
    out = run("hi", {"decision": "search", "message": "Hey there!"})
    assert out["route"] == "end" and out["messages"][0].content == "Hey there!"


def test_chat_replies_keep_all_their_sentences():
    msg = "It's lighter. It also has better battery life. Want to compare?"
    assert run("which?", {"decision": "chat", "message": msg}, profile={"product": "p"})["messages"][0].content == msg


def test_alternatives_reuse_the_shortlist_unless_the_request_changes():
    assert run("others", {"decision": "alternatives"}, profile={"product": "x"}, offers=SHOWN)["route"] == "more"
    assert run("cheaper", {"decision": "alternatives"}, profile={"product": "x"})["route"] == "research"
    plan = {"decision": "alternatives", "queries": ["cheaper laptop"], "mode": "refine"}
    out = run("cheaper", plan, profile={"product": "x"}, offers=SHOWN)
    assert out["route"] == "research" and out["search"]["mode"] == "refine"


def test_more_mode_without_a_shortlist_is_a_new_search():
    out = run("more", {"decision": "search", "queries": ["q"], "mode": "more"}, profile={"product": "x"})
    assert out["search"]["mode"] == "new"


def test_buttons_need_no_plan():
    assert run(SHOW_ALTERNATIVES, offers=SHOWN)["route"] == "more"
    assert run(SHOW_ALTERNATIVES, profile={"product": "laptop"})["route"] == "research"
    out = run(SHOW_ALTERNATIVES)
    assert out["route"] == "end" and "haven't shown" in out["messages"][0].content
    assert run(BROADEN, profile={"product": "laptop"})["search"] == {"queries": ["laptop"], "mode": "more"}
    out = run(RAISE_BUDGET + "₹90,000", profile={"product": "laptop", "budget_max": 50000}, search={"queries": ["a"]})
    assert out["profile"]["budget_max"] == 90000 and out["search"]["queries"] == ["a"] and out["route"] == "research"
    assert run(ACCEPT[0])["route"] == "end"


def test_routing_table():
    assert route_after_supervisor({"route": "research"}) == "plan_research"
    assert route_after_supervisor({"route": "more"}) == "more"
    assert route_after_supervisor({"route": "end"}) == "__end__"
