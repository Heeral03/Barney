"""Words and limits shared by the agents. The buttons the app shows are commands, so no LLM is needed to read them."""
import re

MAX_QUESTIONS = 6
MAX_QUESTIONS_BEFORE_RESULTS = 4  # understand the shopper first, but never interrogate: 4 at most, and skippable
NOT_SURE = "Not sure, you suggest"
SKIP = "Just show me options"  # answers nothing: stop asking and search with what is known

SHOW_ALTERNATIVES = "Show me other options"
COMPARE = "Compare these side by side"
ACCEPT = ("No, this works for me", "I'll go with my first pick")
RESTART = ("Start over", "Find something else")
CHANGE = "Change my requirements"
BROADEN = "Search more broadly"
RAISE_BUDGET = "Raise budget to "

COMMANDS = {SHOW_ALTERNATIVES, COMPARE, CHANGE, BROADEN, *ACCEPT, *RESTART}


def is_command(text: str) -> bool:
    return text in COMMANDS or text.startswith(RAISE_BUDGET)


_WANTS_RESULTS = re.compile(
    r"\b(just show( me)?|show me (what you have|options|something)|you (decide|choose|pick)|(pick|choose|decide) (for|it for) me|"
    r"surprise me|up to you|your call|skip (the )?(questions|this)|no more questions|stop asking)\b", re.I)


def wants_results_now(text: str) -> bool:
    """The shopper asks to stop being questioned ("just show me", "you decide", "surprise me"). A safety net for when the model forgets `skip`."""
    return bool(_WANTS_RESULTS.search(text or ""))
