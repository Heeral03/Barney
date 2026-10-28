import httpx
import pytest
from groq import RateLimitError
from langchain_core.runnables import RunnableLambda


def test_a_rate_limited_model_hands_over_to_the_next_one():
    limited = RateLimitError("limit", response=httpx.Response(429, request=httpx.Request("POST", "x")), body=None)

    def boom(_):
        raise limited

    chain = RunnableLambda(boom).with_fallbacks([RunnableLambda(lambda x: "from fallback")], exceptions_to_handle=(RateLimitError,))
    assert chain.invoke("hi") == "from fallback"


def test_llm_is_configured_with_fallbacks():
    import app.llm as llm_module
    assert llm_module.llm.names == [llm_module.MODEL, *llm_module.FALLBACKS]
    assert llm_module.MODEL not in llm_module.FALLBACKS
    assert llm_module.chat_llm.names[0] == llm_module.CHAT_MODEL and set(llm_module.chat_llm.names) == set(llm_module.llm.names)


def test_recovery_handles_prose_around_the_json_and_gives_up_on_garbage():
    import json

    import pytest
    from groq import BadRequestError

    from app.llm import Structured

    def err(failed):
        return BadRequestError("bad", response=httpx.Response(400, request=httpx.Request("POST", "x")),
                               body={"error": {"failed_generation": failed}})

    assert json.loads(Structured._recover(err('Sure! {"decision": "chat"} hope that helps'))) == {"decision": "chat"}
    assert json.loads(Structured._recover(err('{"name": "x", "arguments": {"decision": "ask"}}'))) == {"decision": "ask"}
    with pytest.raises(BadRequestError):
        Structured._recover(err("just some thinking, no json at all"))


def test_every_structured_call_has_a_user_message():
    """Fallback models reject a prompt made only of system messages ("No user query found in messages")."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from pydantic import BaseModel

    import app.llm as llm_module

    class Out(BaseModel):
        ok: bool = True

    sent = []

    class Fake:
        def invoke(self, messages):
            sent.append(messages)
            return type("R", (), {"content": '{"ok": true}'})()

    s = llm_module.Structured(Out, '{"ok":true}')
    s.json_llm = Fake()
    s.invoke([SystemMessage(content="prompt"), SystemMessage(content="context")])
    assert any(isinstance(m, HumanMessage) for m in sent[-1])
    s.invoke([SystemMessage(content="prompt"), HumanMessage(content="the shopper's words")])
    assert [m.content for m in sent[-1] if isinstance(m, HumanMessage)] == ["the shopper's words"]  # not added twice


# ----------------------------------------------------------------- the quota-aware chain (the cause of 30-60 second "hey"s)
def limit(message="Rate limit reached ... Please try again in 1m25.5s."):
    return RateLimitError(message, response=httpx.Response(429, request=httpx.Request("POST", "x")), body=None)


class Fake:
    def __init__(self, text="ok", error=None):
        self.text, self.error, self.calls = text, error, []

    def invoke(self, input, config=None, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.text


def chain(monkeypatch, **fakes):
    import app.llm as llm_module
    monkeypatch.setattr(llm_module, "_blocked", {})
    c = llm_module.FallbackChat(list(fakes))
    c.chats = fakes
    return c


def test_a_model_out_of_quota_is_skipped_instantly_next_time(monkeypatch):
    import app.llm as llm_module
    a, b = Fake(error=limit()), Fake("from b")
    c = chain(monkeypatch, a=a, b=b)
    assert c.invoke("hi") == "from b" and len(a.calls) == 1
    assert 80 <= llm_module._blocked["a"] - __import__("time").time() <= 90  # Groq said 1m25s
    assert c.invoke("hi again") == "from b" and len(a.calls) == 1  # "a" was not even tried again


def test_a_blocked_model_is_used_again_once_it_has_recovered(monkeypatch):
    import app.llm as llm_module
    a, b = Fake("from a"), Fake("from b")
    c = chain(monkeypatch, a=a, b=b)
    llm_module._blocked["a"] = __import__("time").time() - 1
    assert c.invoke("hi") == "from a"


def test_when_every_model_is_limited_it_fails_at_once_not_after_a_minute(monkeypatch):
    import time
    import pytest
    c = chain(monkeypatch, a=Fake(error=limit()), b=Fake(error=limit()))
    started = time.monotonic()
    with pytest.raises(RateLimitError):
        c.invoke("hi")
    assert time.monotonic() - started < 1
    with pytest.raises(RateLimitError):  # all are blocked now: they are tried anyway, in case they have recovered
        c.invoke("hi")


def test_other_errors_are_not_swallowed_and_do_not_block_a_model(monkeypatch):
    import app.llm as llm_module
    import pytest
    c = chain(monkeypatch, a=Fake(error=ValueError("bad request")), b=Fake("from b"))
    with pytest.raises(ValueError):
        c.invoke("hi")
    assert "a" not in llm_module._blocked


def test_bind_passes_json_mode_through_to_the_model(monkeypatch):
    a = Fake("json")
    c = chain(monkeypatch, a=a)
    assert c.bind(response_format={"type": "json_object"}).invoke("hi") == "json"
    assert a.calls == [{"response_format": {"type": "json_object"}}]


def test_the_clients_own_sleep_and_retry_is_off():
    import app.llm as llm_module
    assert all(chat.max_retries == 0 for chat in llm_module.llm.chats.values())


def test_wait_times_are_read_from_groqs_message():
    import app.llm as llm_module
    wait = lambda t: llm_module._wait_seconds(Exception(t))
    assert wait("Please try again in 1m25.536s.") == pytest.approx(85.5, abs=0.1)
    assert wait("try again in 16s") == 16 and wait("try again in 850ms") == 5 and wait("try again in 3h20m7s") == 3600
    assert wait("no hint") == 60
