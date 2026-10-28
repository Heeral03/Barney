"""DuckDuckGo fallback: used when the shopping API fails or finds nothing.

Web search has no structured prices, so a price is read from the result text when one is there
(for example "at Rs. 999"). Results without a price are kept, labelled "see price on site".
"""
import logging
import re
from urllib.parse import urlparse

from app.sources.serpkite import _tokens

log = logging.getLogger(__name__)

PRICE = re.compile(r"(?:₹|\bRs\.?|\bINR)\s?([\d,]{2,9}(?:\.\d+)?)", re.I)
SHOPS = ("amazon.in", "flipkart.com", "myntra.com", "ajio.com", "nykaa.com", "croma.com", "reliancedigital.in",
         "tatacliq.com", "meesho.com", "snapdeal.com", "vijaysales.com", "shopify", "bewakoof.com")
JUNK = ("wikipedia", "youtube", "reddit", "quora", "facebook", "instagram", "pinterest", "buyhatke", "twitter",
        "linkedin", "medium.com", "blogspot")


def _price(text: str):
    nums = [float(m.replace(",", "")) for m in PRICE.findall(text or "")]
    nums = [n for n in nums if n >= 10]
    return min(nums) if nums else None


def _images(query: str) -> list[dict]:
    try:
        from ddgs import DDGS
        return DDGS().images(query, region="in-en", max_results=12) or []
    except Exception as e:
        log.warning("ddg images failed: %s", e)
        return []


def ddg_offers(query: str, limit: int = 6) -> list[dict]:
    from app.tools.products import inr

    try:
        from ddgs import DDGS
    except Exception as e:
        log.warning("ddgs not available: %s", e)
        return []

    hits, seen = [], set()
    for q in (f"{query} price ₹", f"{query} buy online"):
        try:
            rows = DDGS().text(q, region="in-en", max_results=10) or []
        except Exception as e:
            log.warning("ddg text %r failed: %s", q, e)
            continue
        for r in rows:
            url, title = r.get("href") or "", r.get("title") or ""
            host = urlparse(url).netloc.lower().removeprefix("www.")
            if not url or not title or url in seen or any(j in host for j in JUNK):
                continue
            seen.add(url)
            hits.append({"title": title, "url": url, "host": host, "price": _price(f"{title} {r.get('body')}")})

    # Priced results first, then known Indian retailers.
    hits.sort(key=lambda h: (h["price"] is None, not any(s in h["host"] for s in SHOPS)))
    hits = hits[:limit]
    pics = _images(query)

    offers = []
    for i, h in enumerate(hits, 1):
        want = _tokens(h["title"])
        pic = max(pics, key=lambda p: len(want & _tokens(p.get("title") or "")), default=None)
        ok = pic and len(want & _tokens(pic.get("title") or "")) / max(len(want), 1) >= 0.4
        offers.append({
            "title": h["title"],
            "price_inr": h["price"],
            "price_display": inr(h["price"]) if h["price"] else "See price on site",
            "seller": h["host"],
            "rating": None,
            "rating_count": None,
            "link": h["url"],
            "link_domain": h["host"],
            "image_url": pic.get("image") if ok else None,
            "number": i,
        })
    return offers
