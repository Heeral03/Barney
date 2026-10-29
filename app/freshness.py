"""How new a listing's product is, read from its title. Shoppers want the current generation, not last decade's.

A title rarely says "2023", but it often names a chip or a model number that carries the year: "i7 13th Gen", "i7-1360P",
"MacBook Air M1", "iPhone 13", "Galaxy S22". Those are mapped to a release year here. Only well-known families are covered;
anything not recognised has no year and is never treated as old.
"""
import re
from datetime import date

_YEAR = re.compile(r"(?<![\d₹.,])(20[0-3]\d)(?![\d,])")

# Intel Core generation -> year it launched (the number in "13th Gen" and the first digits of "i7-1360P" / "i7-13650HX").
_INTEL = {6: 2015, 7: 2016, 8: 2017, 9: 2018, 10: 2019, 11: 2021, 12: 2022, 13: 2023, 14: 2024}
_GEN = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)[ -]?gen(?:eration)?\b", re.I)
_INTEL_MODEL = re.compile(r"\bi[3579][ -](\d{2})\d{2,3}[a-z]{0,3}\b", re.I)
_APPLE_M = re.compile(r"\bM([1-9])(?:\s?(?:pro|max|ultra))?\b")
_APPLE_YEAR = {1: 2020, 2: 2022, 3: 2023, 4: 2024, 5: 2025}
_IPHONE = re.compile(r"\biphone\s?(\d{1,2})\b", re.I)
_IPHONE_YEAR = {11: 2019, 12: 2020, 13: 2021, 14: 2022, 15: 2023, 16: 2024, 17: 2025}
_GALAXY_S = re.compile(r"\bgalaxy\s?s(2\d)\b", re.I)
_RYZEN = re.compile(r"\bryzen\s?[3579]\s?([4-9])\d{3}[a-z]{0,3}\b", re.I)
_RYZEN_YEAR = {4: 2020, 5: 2021, 6: 2022, 7: 2023, 8: 2024, 9: 2025}


# Things that mark a product as a past generation although the title gives no year. (pattern, year, unless this also matches)
_LEGACY = [
    (re.compile(r"\blightning\b", re.I), 2022, None),  # Apple moved to USB-C with the iPhone 15 (2023)
    (re.compile(r"\bmicro[ -]?usb\b", re.I), 2018, re.compile(r"\b(usb[ -]?c|type[ -]?c)\b", re.I)),
    (re.compile(r"\bearpods\b", re.I), 2016, re.compile(r"\b(usb[ -]?c|type[ -]?c)\b", re.I)),
]


# "for iPhone 15", "compatible with Galaxy S22": the device an accessory works with says nothing about the accessory's age.
_FOR_DEVICE = re.compile(r"\b(?:for|compatible with|fits|works with|supports?)\b[^|,()]{0,40}", re.I)


def model_year(title: str) -> int | None:
    """The year a listing's product came out, or None when its title says nothing we recognise. The newest clue wins."""
    t = title or ""
    years = [int(y) for y in _YEAR.findall(t)]
    for gen in _GEN.findall(t):
        if int(gen) in _INTEL and "ryzen" not in t.lower():
            years.append(_INTEL[int(gen)])
    for gen in _INTEL_MODEL.findall(t):
        if int(gen) in _INTEL:
            years.append(_INTEL[int(gen)])
    for n in _APPLE_M.findall(t):
        if "mac" in t.lower() or "apple" in t.lower():
            years.append(_APPLE_YEAR.get(int(n), 2025))
    device_free = _FOR_DEVICE.sub(" ", t)
    for n in _IPHONE.findall(device_free):
        if int(n) in _IPHONE_YEAR:
            years.append(_IPHONE_YEAR[int(n)])
    for n in _GALAXY_S.findall(device_free):
        years.append(2000 + int(n))
    for n in _RYZEN.findall(t):
        years.append(_RYZEN_YEAR[int(n)])
    for pattern, year, unless in _LEGACY:
        if pattern.search(t) and not (unless and unless.search(t)):
            years.append(year)
    return max(years) if years else None


_YEARLY = re.compile(r"\b(laptop|notebook|macbook|phone|smartphone|iphone|tablet|ipad|tv|television|headphones?|earbuds?|earphones?|"
                     r"camera|smartwatch|watch|console|monitor|speaker)s?\b", re.I)
_WANTS_OLD = re.compile(r"\b(refurbished|renewed|used|second[- ]?hand|pre[- ]?owned|old|older|vintage|retro)\b", re.I)


def with_current_year(product: str, queries: list[str]) -> list[str]:
    """Products that come in yearly generations: the lead search carries the current year, so the shopping results lean new.
    Left alone when the query already names a year or generation, or when the shopper wants old or used models."""
    if not queries or not _YEARLY.search(f"{product} {queries[0]}") or any(_WANTS_OLD.search(q) for q in queries):
        return queries
    if model_year(queries[0]):
        return queries
    return [f"{queries[0]} {date.today().year}", *queries[1:]]
