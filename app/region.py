"""Where the shopper is, and what that means for the search.

A market is a country Barney can search properly: it has a Google Shopping locale and a list of verified stores that sell
there (see `app/stores.py`). The shopper's country comes from, in order: what they chose in Preferences, then the country
the web app detected from their connection, then India.

Barney never shows a store that does not take orders from the shopper's country. For a country that is not a market yet,
he says so instead of showing stores that would not deliver.
"""
from dataclasses import dataclass
from typing import Optional

DEFAULT = "IN"


@dataclass(frozen=True)
class Market:
    code: str
    name: str
    gl: str  # Google country code
    hl: str  # Google language
    location: str  # SerpAPI "location" for Google Shopping
    symbol: str


MARKETS: dict[str, Market] = {m.code: m for m in (
    Market("IN", "India", "in", "en", "India", "₹"),
    Market("US", "the United States", "us", "en", "United States", "$"),
    Market("GB", "the United Kingdom", "uk", "en", "United Kingdom", "£"),
    Market("CA", "Canada", "ca", "en", "Canada", "CA$"),
    Market("AU", "Australia", "au", "en", "Australia", "A$"),
    Market("AE", "the United Arab Emirates", "ae", "en", "United Arab Emirates", "AED "),
)}

_ALIASES = {"UK": "GB", "IND": "IN", "USA": "US"}


def normalize(code: Optional[str]) -> str:
    """A two-letter upper-case country code, or "" when the input is not one."""
    code = (code or "").strip().upper()
    code = _ALIASES.get(code, code)
    return code if len(code) == 2 and code.isalpha() else ""


def from_accept_language(header: str) -> str:
    """The region in an Accept-Language header ("en-IN,en;q=0.9" -> "IN"). A weak signal, used only when nothing better is known."""
    for part in (header or "").split(","):
        tag = part.split(";")[0].strip()
        if "-" in tag and (code := normalize(tag.split("-")[-1])):
            return code
    return ""


def resolve(saved: Optional[str], detected: Optional[str]) -> str:
    """The shopper's country: their own choice, else the detected one, else the default market."""
    return normalize(saved) or normalize(detected) or DEFAULT


def supported(code: str) -> bool:
    return normalize(code) in MARKETS


def market(code: str) -> Market:
    return MARKETS.get(normalize(code)) or MARKETS[DEFAULT]


def money(amount: float, code: str = DEFAULT) -> str:
    """A price in the market's currency. India keeps its lakh grouping."""
    m = market(code)
    if m.code == "IN":
        from app.tools.products import inr
        return inr(amount)
    return f"{m.symbol}{amount:,.0f}"


def not_served_text(code: str) -> str:
    return (f"I can't find stores I trust that deliver to {normalize(code) or 'your country'} yet. "
            f"Right now I search in {', '.join(m.name for m in MARKETS.values())}. "
            "You can change your country in Preferences if you are shopping for somewhere else.")
