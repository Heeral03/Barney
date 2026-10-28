"""Words and limits shared by the agents. The buttons the app shows are commands, so no LLM is needed to read them."""

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
