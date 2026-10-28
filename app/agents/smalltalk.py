"""Small talk ("hey", "thanks", "who are you"): answered by one plain, fast chat call, never by the shopping pipeline.

The requirements agent sends a long JSON-formatted prompt to a large model, which is slow for a greeting and sometimes
fails when the model just wants to say hello. Pure pleasantries are recognised deterministically (a message made only of
greeting-like words), so the common case costs one small call, and a canned reply covers a failed one.
"""
import logging
import re

from groq import RateLimitError
from langchain_core.messages import HumanMessage, SystemMessage

from app.llm import chat_llm, load_prompt

log = logging.getLogger(__name__)

PROMPT = load_prompt("barney_chat.txt")
MAX_WORDS = 6
_WORDS = set("""hi hii hiii hey heyy heyyy hello hola yo sup namaste howdy good morning afternoon evening night thanks thank you u
thx ty ok okay cool great nice awesome perfect cheers bye goodbye see later how are is it going whats what up who can do help
there barney buddy friend bro man guys again a lot so much really""".split())


def is_small_talk(text: str) -> bool:
    """True for a message that is only a greeting, thanks or similar ("Hey barney", "thanks a lot", "who are you")."""
    words = re.findall(r"[a-z']+", (text or "").lower().replace("'", ""))
    return 0 < len(words) <= MAX_WORDS and all(w in _WORDS for w in words)


def _name(recalled: list[dict] | None) -> str | None:
    for m in recalled or []:
        found = re.match(r"(?i)^(?:their |the shopper's )?name is (.+)$", str(m.get("text", "")).strip()) if isinstance(m, dict) else None
        if found:
            return found.group(1).strip(" .")
    return None


def small_talk_reply(said: str, profile: dict, recalled: list[dict] | None = None) -> str:
    name = _name(recalled)
    notes = [f"The shopper's name is {name}." if name else "", f"They are currently looking for: {profile['product'].replace('_', ' ')}."
             if profile.get("product") else ""]
    try:
        text = str(chat_llm.invoke([PROMPT, SystemMessage(content="Notes: " + (" ".join(n for n in notes if n) or "none")),
                                    HumanMessage(content=said)]).content).strip()
        if text:
            return text[:400]
    except RateLimitError:
        log.warning("small talk: every chat model is rate limited")
    except Exception as e:
        log.warning("small talk failed: %s: %s", type(e).__name__, str(e)[:150])
    return f"Hey{', ' + name if name else ''}! 👋 I'm Barney. What are you looking to buy?"
