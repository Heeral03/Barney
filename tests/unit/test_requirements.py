from langchain_core.messages import HumanMessage

import app.agents.requirements as req
from app.commands import SHOW_ALTERNATIVES


def run(monkeypatch, said, plan, **state):
    calls = []
    monkeypatch.setattr(req.decider, "invoke", lambda m: calls.append(m) or req.Plan(**plan.pop(0)))
    return req.requirements_node({"messages": [HumanMessage(content=said)], **state}), calls


def test_budget_the_model_missed_is_parsed_from_the_message(monkeypatch):
    out, _ = run(monkeypatch, "around 1 lakh", [{"decision": "search", "product": "laptop", "queries": ["laptop"]}])
    assert out["profile"]["budget_max"] == 100_000


def test_model_budget_wins_over_parser(monkeypatch):
    out, _ = run(monkeypatch, "around 1 lakh", [{"decision": "search", "product": "laptop", "budget_max": 90_000}])
    assert out["profile"]["budget_max"] == 90_000


def test_missing_product_is_retried_once(monkeypatch):
    out, calls = run(monkeypatch, "laptop for coding", [{"decision": "ask", "question": "q"},
                                                       {"decision": "ask", "product": "laptop", "question": "q"}])
    assert len(calls) == 2 and out["profile"]["product"] == "laptop"


def test_changing_product_resets_profile_and_shortlist(monkeypatch):
    out, _ = run(monkeypatch, "now a t-shirt", [{"decision": "ask", "product": "bamboo t-shirt", "question": "size?"}],
                 profile={"product": "macbook", "budget_max": 150_000, "facts": {"ram": "16GB"}},
                 offers=[{"number": 1, "title": "MacBook", "price_display": "₹1", "rating": None}])
    assert out["profile"] == {"product": "bamboo t-shirt", "facts": {}} and out["offers"] == []


def test_buttons_skip_the_llm(monkeypatch):
    out, calls = run(monkeypatch, SHOW_ALTERNATIVES, [])
    assert out == {"plan": {}, "table": None} and calls == []


def test_mode_and_remember_are_carried_in_the_plan(monkeypatch):
    out, _ = run(monkeypatch, "my name is Heeral", [{
        "decision": "chat", "message": "Nice to meet you!", "mode": "bogus",
        "remember": [{"text": "Name is Heeral", "category": "person", "kind": "profile"}]}])
    assert out["plan"]["mode"] == "new"
    assert out["plan"]["remember"] == [{"text": "Name is Heeral", "category": "person", "kind": "profile", "key": None}]


def test_the_model_sees_the_shortlist_and_only_relevant_memories(monkeypatch):
    mems = [{"text": "Uses a laptop for heavy coding", "category": "laptop"},
            {"text": "Name is Heeral", "category": "person"},
            {"text": "Wears size 5 in shoes", "category": "shoes"}]
    offers = [{"number": 1, "title": "Nike Quest", "price_display": "₹3,000", "rating": 4.5, "rating_count": 10}]
    _, calls = run(monkeypatch, "which is cheapest?", [{"decision": "chat", "product": "running_shoes"}],
                   profile={"product": "running_shoes"}, recalled=mems, offers=offers, shown=[1])
    seen = calls[0][1].content  # the "what is known" block, not the prompt
    assert "#1 (shown): Nike Quest" in seen and "Name is Heeral" in seen and "size 5" in seen
    assert "heavy coding" not in seen  # laptop habits stay out of a shoe search


# ----------------------------------------------------------------- the question plan
from app.commands import NOT_SURE, SKIP  # noqa: E402

PENDING = {"topic": "fit", "options": ["Straight", "Skinny"], "durable": True}
ATTRS = [{"topic": "fit", "question": "Fit?", "options": ["Straight"], "durable": True},
         {"topic": "colour", "question": "Colour?", "options": ["Blue"], "durable": True},
         {"topic": "budget", "question": "Budget?", "options": ["Under ₹1,000"]}]


def test_a_tapped_answer_needs_no_model_call_and_a_durable_one_is_remembered(monkeypatch):
    profile = {"product": "jeans", "attrs": ATTRS, "asked": ["fit"], "pending": PENDING}
    out, calls = run(monkeypatch, "Straight", [], profile=profile)
    assert calls == [] and out["plan"]["decision"] == "ask"
    assert out["profile"]["facts"] == {"fit": "Straight"} and "pending" not in out["profile"]
    assert out["plan"]["remember"] == [{"text": "Fit preference for jeans: Straight", "category": "jeans", "kind": "preference", "key": "pref:jeans:fit"}]


def test_a_tapped_budget_sets_the_budget_and_is_not_remembered(monkeypatch):
    pending = {"topic": "budget", "options": ["Under ₹1,000"], "durable": False}
    profile = {"product": "jeans", "attrs": ATTRS, "asked": ["fit", "colour", "budget"], "facts": {"fit": "x", "colour": "y"}, "pending": pending}
    out, calls = run(monkeypatch, "Under ₹1,000", [{"decision": "search", "queries": ["jeans"]}], profile=profile)
    assert out["profile"]["budget_max"] == 1000 and "budget" not in out["profile"]["facts"]
    assert len(calls) == 1  # the last answer: now the model writes the search
    assert out["plan"]["remember"] == []


def test_not_sure_and_skip(monkeypatch):
    profile = {"product": "jeans", "attrs": ATTRS, "asked": ["fit"], "pending": PENDING}
    out, calls = run(monkeypatch, NOT_SURE, [], profile=profile)
    assert out["profile"]["facts"] == {"fit": "open to suggestions"} and calls == [] and out["plan"]["remember"] == []
    out, calls = run(monkeypatch, SKIP, [{"decision": "search", "queries": ["jeans"]}], profile=profile)
    assert out["profile"]["skip"] is True and len(calls) == 1  # skipping goes straight to the model for the search


def test_a_typed_answer_is_filed_under_the_question_when_the_model_does_not(monkeypatch):
    profile = {"product": "jeans", "attrs": ATTRS, "asked": ["fit"], "pending": PENDING}
    out, calls = run(monkeypatch, "I like them loose and straight", [{"decision": "ask", "product": "jeans"}], profile=profile)
    assert len(calls) == 1 and out["profile"]["facts"]["fit"] == "I like them loose and straight"
    assert out["plan"]["remember"][0]["text"].startswith("Fit preference for jeans")


def test_a_typed_answer_the_model_already_filed_is_not_duplicated(monkeypatch):
    pending = {"topic": "colour", "options": ["Blue"], "durable": True}
    profile = {"product": "jeans", "attrs": ATTRS, "asked": ["fit", "colour"], "pending": pending}
    out, _ = run(monkeypatch, "navy blue", [{"decision": "ask", "product": "jeans", "facts": [{"topic": "color", "value": "navy"}]}], profile=profile)
    assert out["profile"]["facts"] == {"color": "navy"} and out["plan"]["remember"] == []  # "color" is the same question as "colour"


def test_the_question_plan_is_written_once_per_product(monkeypatch):
    attrs = [{"topic": "fit", "question": "Fit?", "options": ["Straight", "other"], "durable": True}]
    out, _ = run(monkeypatch, "jeans for women", [{"decision": "ask", "product": "jeans", "attributes": attrs}])
    assert out["profile"]["attrs"] == [{"topic": "fit", "question": "Fit?", "options": ["Straight"], "durable": True}]
    again, _ = run(monkeypatch, "hmm", [{"decision": "ask", "product": "jeans", "attributes": [{"topic": "other", "question": "?"}]}],
                   profile=out["profile"])
    assert again["profile"]["attrs"][0]["topic"] == "fit"  # not replaced


def test_an_unusable_model_answer_becomes_a_chat_reply_not_an_error(monkeypatch):
    def broken(messages):
        raise ValueError("model answered with prose")
    monkeypatch.setattr(req.decider, "invoke", broken)
    profile = {"product": "jeans", "facts": {"fit": "straight"}}
    out = req.requirements_node({"messages": [HumanMessage(content="which colours do I like?")], "profile": profile})
    assert out["plan"]["decision"] == "chat" and "say that again" in out["plan"]["message"] and out["profile"] == profile


def test_a_rate_limit_is_not_swallowed(monkeypatch):
    import httpx
    from groq import RateLimitError
    limited = RateLimitError("limit", response=httpx.Response(429, request=httpx.Request("POST", "x")), body=None)

    def boom(messages):
        raise limited
    monkeypatch.setattr(req.decider, "invoke", boom)
    import pytest
    with pytest.raises(RateLimitError):
        req.requirements_node({"messages": [HumanMessage(content="I want a pair of jeans")]})
