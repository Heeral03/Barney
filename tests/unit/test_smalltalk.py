import httpx
import pytest
from groq import BadRequestError, RateLimitError
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

import app.agents.requirements as req
import app.agents.smalltalk as st
import app.llm as llm_module


@pytest.mark.parametrize("text", ["hey", "Hey barney", "hello there!", "thanks", "thank you so much", "ok", "good morning",
                                  "who are you", "what can you do", "how are you", "bye", "hiii", "Hey Barney 👋", "thx"])
def test_pleasantries_are_small_talk(text):
    assert st.is_small_talk(text)


@pytest.mark.parametrize("text", ["hey I need a laptop", "help me find shoes", "thanks, show me cheaper ones", "nice laptop under 50k",
                                  "Foaming", "Show me more alternatives", "my name is Heeral", "compare them", "hi, running shoes for women", ""])
def test_anything_about_shopping_is_not(text):
    assert not st.is_small_talk(text)


class FakeChat:
    def __init__(self, text="Hey there! 👋 What are you shopping for?", error=None):
        self.text, self.error, self.calls = text, error, []

    def invoke(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return type("R", (), {"content": self.text})()


def run(monkeypatch, said, chat, **state):
    def forbidden(messages):
        raise AssertionError("small talk must not reach the shopping model")
    monkeypatch.setattr(req.decider, "invoke", forbidden)
    monkeypatch.setattr(st, "chat_llm", chat)
    return req.requirements_node({"messages": [HumanMessage(content=said)], **state})


def test_a_greeting_is_one_small_plain_chat_call(monkeypatch):
    chat = FakeChat()
    out = run(monkeypatch, "hey barney", chat, recalled=[{"text": "Name is Heeral", "category": "person"}],
              profile={"product": "jeans"})
    assert out["plan"] == {"decision": "chat", "message": "Hey there! 👋 What are you shopping for?"} and out["table"] is None
    assert len(chat.calls) == 1 and "Heeral" in chat.calls[0][1].content and "jeans" in chat.calls[0][1].content
    assert sum(len(str(m.content)) for m in chat.calls[0]) < 1500  # a tiny prompt, not the shopping prompt
    assert chat.calls[0][2].content == "hey barney"


def test_notes_are_never_empty_or_dangling(monkeypatch):
    chat = FakeChat()
    run(monkeypatch, "hey", chat)
    assert chat.calls[0][1].content == "Notes: none"


def test_a_failed_chat_call_gets_a_friendly_canned_reply(monkeypatch):
    for error in (RuntimeError("boom"), RateLimitError("limit", response=httpx.Response(429, request=httpx.Request("POST", "x")), body=None)):
        out = run(monkeypatch, "hello", FakeChat(error=error), recalled=[{"text": "Name is Heeral"}])
        assert out["plan"]["message"] == "Hey, Heeral! 👋 I'm Barney. What are you looking to buy?"
    assert run(monkeypatch, "hello", FakeChat(error=RuntimeError()))["plan"]["message"].startswith("Hey! 👋")
    assert run(monkeypatch, "hello", FakeChat(text="   "))["plan"]["message"].startswith("Hey! 👋")  # an empty reply is no reply


def test_an_answer_to_a_pending_question_is_not_small_talk(monkeypatch):
    chat = FakeChat()
    calls = []
    monkeypatch.setattr(req.decider, "invoke", lambda m: calls.append(m) or req.Plan(decision="ask", product="jeans"))
    monkeypatch.setattr(st, "chat_llm", chat)
    pending = {"topic": "fit", "options": ["Straight"], "durable": False}
    req.requirements_node({"messages": [HumanMessage(content="nice")], "profile": {"product": "jeans", "pending": pending}})
    assert chat.calls == [] and len(calls) == 1  # "nice" answered the question; it goes to the shopping model


# ----------------------------------------------------------------- the model answering outside JSON
def bad_request(text):
    return BadRequestError("bad", response=httpx.Response(400, request=httpx.Request("POST", "x")),
                           body={"error": {"code": "json_validate_failed", "failed_generation": text}})


def test_prose_from_a_failed_json_request_is_recovered():
    assert llm_module.prose_from_error(bad_request("Hey Heeral! 👋 Anything else?")) == "Hey Heeral! 👋 Anything else?"
    assert llm_module.prose_from_error(bad_request('{"decision": "chat"}')) == ""  # that was JSON: not prose
    assert llm_module.prose_from_error(RuntimeError("x")) == ""


def test_the_requirements_agent_uses_the_models_plain_answer_as_the_reply(monkeypatch):
    """The exact failure from the logs: Groq rejected a friendly sentence for not being JSON."""
    monkeypatch.setattr(req.decider, "invoke", lambda m: (_ for _ in ()).throw(
        bad_request("Hey Heeral! 👋 Want me to dig up a few more options in that range?")))
    out = req.requirements_node({"messages": [HumanMessage(content="which one do you like?")], "profile": {"product": "face_wash"}})
    assert out["plan"] == {"decision": "chat", "message": "Hey Heeral! 👋 Want me to dig up a few more options in that range?"}
    assert out["profile"] == {"product": "face_wash"} and out["table"] is None


def test_structured_calls_fall_back_to_a_plain_call_when_json_mode_keeps_failing(monkeypatch):
    class Out(BaseModel):
        answer: str

    class JsonMode:
        def invoke(self, messages):
            raise bad_request("Sure! Here you go.")

    s = llm_module.Structured(Out, '{"answer":""}')
    s.json_llm = JsonMode()
    plain = FakeChat(text='Here it is:\n```json\n{"answer": "42"}\n```')
    monkeypatch.setattr(llm_module, "llm", plain)
    assert s.invoke([HumanMessage(content="q")]).answer == "42"
    assert len(plain.calls) == 1


def test_a_rate_limit_is_never_retried_by_the_plain_fallback(monkeypatch):
    class Out(BaseModel):
        answer: str

    class Limited:
        def invoke(self, messages):
            raise RateLimitError("limit", response=httpx.Response(429, request=httpx.Request("POST", "x")), body=None)

    s = llm_module.Structured(Out, "{}")
    s.json_llm = Limited()
    plain = FakeChat()
    monkeypatch.setattr(llm_module, "llm", plain)
    with pytest.raises(RateLimitError):
        s.invoke([HumanMessage(content="q")])
    assert plain.calls == []
