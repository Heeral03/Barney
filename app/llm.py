"""Shared LLM client and helpers used by the supervisor and the memory agent."""
import json
import logging
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from groq import BadRequestError, RateLimitError
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langchain_groq import ChatGroq
from pydantic import BaseModel

load_dotenv()
log = logging.getLogger(__name__)

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# Groq counts tokens per model per day, so when one model is out of quota the next one takes over.
FALLBACKS = [m.strip() for m in os.getenv("GROQ_FALLBACK_MODELS", "openai/gpt-oss-20b,qwen/qwen3.8-27b").split(",")
             if m.strip() and m.strip() != MODEL]


def _chat(model: str) -> ChatGroq:
    return ChatGroq(
        model=model,
        api_key=os.environ.get("GROQ_API_KEY"),
        timeout=float(os.getenv("GROQ_TIMEOUT", "30")),  # seconds; fail fast instead of hanging a turn
        # No retries inside the client: it sleeps for the whole retry-after (up to a minute) on a 429, which made a
        # simple "hey" hang. A rate-limited model must fail at once so the next one can answer.
        max_retries=0,
        # Low effort keeps gpt-oss from leaking its reasoning into the JSON, which Groq rejects with a 400.
        **({"reasoning_effort": os.getenv("GROQ_REASONING_EFFORT", "low")} if "gpt-oss" in model else {}),
    )


_blocked: dict[str, float] = {}  # model -> time before which it is known to be out of quota


def _wait_seconds(err: Exception) -> float:
    """How long Groq says to wait ("Please try again in 1h5m3.2s"), within sensible bounds."""
    if re.search(r"try again in [\d.]+ms", str(err)):
        return 5.0
    found = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m(?!s))?(?:([\d.]+)s)?", str(err))
    if found and any(found.groups()):
        h, m, sec = (float(g) if g else 0.0 for g in found.groups())
        return min(max(h * 3600 + m * 60 + sec, 5.0), 3600.0)
    return 60.0


class FallbackChat(Runnable):
    """Tries the models in order. A model that is out of quota is skipped, instantly, until Groq says it has recovered.

    Behaves like a chat model: `.invoke(...)` and `.bind(...)` (used for JSON mode) both work.
    """

    def __init__(self, models: list[str]):
        self.names, self.chats = models, {m: _chat(m) for m in models}

    def available(self) -> list[str]:
        now = time.time()
        return [m for m in self.names if _blocked.get(m, 0) <= now]

    def invoke(self, input, config=None, **kwargs):
        last = None
        for name in self.available() or self.names:  # all blocked: try them anyway, they may have recovered
            try:
                return self.chats[name].invoke(input, config, **kwargs)
            except RateLimitError as e:
                _blocked[name] = time.time() + _wait_seconds(e)
                log.warning("%s is out of quota (skipping it for %.0fs)", name, _blocked[name] - time.time())
                last = e
        raise last


llm = FallbackChat([MODEL, *FALLBACKS])

# General conversation ("hey", "thanks") is a plain, fast chat call: no JSON mode, no long prompt. Any model will do, so
# the small one goes first; if its quota is gone the others answer.
CHAT_MODEL = os.getenv("GROQ_CHAT_MODEL", "openai/gpt-oss-20b")
chat_llm = FallbackChat([CHAT_MODEL, *[m for m in [MODEL, *FALLBACKS] if m != CHAT_MODEL]])


def load_prompt(name: str) -> SystemMessage:
    return SystemMessage(content=(PROMPTS / name).read_text().strip())


class Structured:
    """Asks the model for a JSON object and validates it against a pydantic schema.

    Plain JSON mode is more reliable here than schema-constrained decoding: gpt-oss
    sometimes answers with a fake tool call there, which Groq rejects with a 400.
    """

    def __init__(self, schema: type[BaseModel], shape: str, attempts: int = 3):
        self.schema, self.attempts = schema, attempts
        self.json_llm = llm.bind(response_format={"type": "json_object"})
        self.format = SystemMessage(
            content="Reply with ONE JSON object only, shaped like: " + shape
        )

    def invoke(self, messages: list):
        if not any(isinstance(m, HumanMessage) for m in messages):
            # Some models (the fallbacks) reject a request that has no user message at all.
            messages = [*messages, HumanMessage(content="Answer now.")]
        last = None
        for _ in range(self.attempts):
            try:
                try:
                    raw = self.json_llm.invoke([*messages, self.format]).content
                except BadRequestError as e:
                    raw = self._recover(e)
                return self.schema.model_validate_json(raw)
            except RateLimitError:
                raise  # retrying only burns more of the quota
            except Exception as e:  # bad JSON, schema mismatch or a Groq 400: just ask again
                last = e
        # JSON mode keeps failing (the model wants to answer in prose): one plain call, taking the JSON out of its text.
        try:
            text = str(llm.invoke([*messages, self.format]).content)
            return self.schema.model_validate_json(_json_in(text))
        except RateLimitError:
            raise
        except Exception:
            raise last

    @staticmethod
    def _recover(err: BadRequestError) -> str:
        """gpt-oss sometimes wraps its JSON as a fake tool call; Groq rejects it but returns the text."""
        body = err.body if isinstance(err.body, dict) else {}
        failed = (body.get("error") or body).get("failed_generation")
        if not failed:
            raise err
        try:
            data = json.loads(failed)
        except ValueError:  # prose around the JSON, or a truncated reply: take the outermost {...} if there is one
            start, end = failed.find("{"), failed.rfind("}")
            if start < 0 or end <= start:
                raise err
            data = json.loads(failed[start:end + 1])
        return json.dumps(data.get("arguments", data) if isinstance(data, dict) else data)


def _json_in(text: str) -> str:
    """The outermost {...} in a model's reply (it may wrap the JSON in prose or code fences)."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the reply")
    return text[start:end + 1]


def prose_from_error(err: Exception) -> str:
    """What the model actually said when Groq rejected it for not being JSON ("failed_generation"), or "" if that was JSON."""
    body = getattr(err, "body", None)
    body = body if isinstance(body, dict) else {}
    text = str((body.get("error") or body).get("failed_generation") or "").strip()
    return "" if "{" in text else text
