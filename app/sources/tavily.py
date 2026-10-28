"""Tavily web search, restricted to Indian retailers: the fallback when Google Shopping finds too little.

Tavily returns product and listing pages, not structured offers, so the price is read from the page text. EMI
instalments ("₹352/month") and list prices (MRP) are ignored: they would otherwise look like the cheapest price.
"""
import logging
import os
import re
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

URL = "https://api.tavily.com/search"
RETAILERS = ["amazon.in", "flipkart.com", "myntra.com", "ajio.com", "tatacliq.com", "nykaa.com", "croma.com",
             "reliancedigital.in", "vijaysales.com", "snapdeal.com", "meesho.com", "decathlon.in", "in.puma.com",
             "nike.in", "adidas.co.in", "skechers.in", "levi.in", "croma.com", "lenskart.com", "firstcry.com"]

_MONEY = r"(?:₹|\bRs\.?|\bINR)\s?"
_EMI = re.compile(rf"{_MONEY}[\d,]+(?:\.\d+)?\s*(?:/|per|a)\s*(?:month|mo)\b|\bEMI\b[^.]*", re.I)
_MRP = re.compile(rf"\b(?:MRP|M\.R\.P|list price|was)\b[:\s]*{_MONEY}[\d,]+(?:\.\d+)?", re.I)
_FILTER = re.compile(rf"\b(?:under|below|upto|up to|over|above)\s*{_MONEY}[\d,]+(?:\.\d+)?", re.I)  # "under ₹3000" is a filter
_CATEGORY_TITLE = re.compile(r"^(shop|buy|best|top)\b|\b(online|collection|store)\b.*\b(at|in|on)\b.*\b(price|india|offer)", re.I)
_PRICE = re.compile(rf"{_MONEY}([\d,]{{2,9}}(?:\.\d+)?)", re.I)


_PRODUCT_URL = re.compile(r"/dp/|/gp/product/|/p/|/p-|/buy(?:[/?]|$)|[?&]pid=|/product|/pd/", re.I)
_NOT_A_PRODUCT = re.compile(r"price list|\bvs\b|\breviews?\b|\btop \d+|\bbest\b.*\bin india\b|how to|buying guide|^amazon\.in\s*:", re.I)


def is_product_page(url: str, title: str) -> bool:
    """A single product's page, not a category, search result, price list or article."""
    return bool(_PRODUCT_URL.search(url or "")) and not _NOT_A_PRODUCT.search(title or "")


def clean_title(title: str) -> str:
    """"LEE Skinny Jeans - Buy LEE Skinny Jeans Online at Best Pri..." -> "LEE Skinny Jeans"."""
    title = re.split(r"\s+[-|–]\s+(?:Buy|Shop)\b", title or "", maxsplit=1, flags=re.I)[0]
    title = re.sub(r"^(?:Buy|Shop)\s+", "", title, flags=re.I)
    title = re.sub(r"\s+(?:at|on|from)\s+(?:Amazon\.in|Flipkart\.com|Myntra|Ajio|Nykaa|Croma|Tata ?CLiQ)\W*$", "", title, flags=re.I)
    return title.strip(" -|–")


def read_price(text: str):
    """The selling price in rupees found in page text, or None."""
    text = _FILTER.sub(" ", _MRP.sub(" ", _EMI.sub(" ", text or "")))
    nums = [float(m.replace(",", "")) for m in _PRICE.findall(text)]
    nums = [n for n in nums if n >= 100]
    return min(nums) if nums else None


def tavily_offers(query: str, limit: int = 6) -> list[dict]:
    from app.tools.products import inr

    key = os.getenv("TAVILY_API_KEY")
    if not key:
        return []
    try:
        r = httpx.post(
            URL, headers={"Authorization": f"Bearer {key}"}, timeout=20,
            json={"query": f"{query} price", "search_depth": "basic", "max_results": 10, "include_domains": RETAILERS},
        )
        r.raise_for_status()
        rows = r.json().get("results") or []
    except Exception as e:
        log.warning("tavily search %r failed: %s", query, e)
        return []

    offers, seen = [], set()
    for rank, row in enumerate(rows):
        url, title = row.get("url") or "", (row.get("title") or "").strip()
        host = urlparse(url).netloc.lower().removeprefix("www.")
        foreign = bool(re.match(r"^[a-z]{2}\.", host)) and not host.startswith("in.")  # ph.puma.com, uk.shop...
        listing_page = foreign or not is_product_page(url, title) or "/collections/" in url or _CATEGORY_TITLE.search(title)
        if not url or not title or url in seen or listing_page:  # skip search-result, category and non-Indian pages
            continue
        seen.add(url)
        price = read_price(f"{title} {row.get('content')}")
        title = clean_title(title)
        offers.append({
            "title": title, "price_inr": price, "price_display": inr(price) if price else "See price on site",
            "seller": host, "rating": None, "rating_count": None, "link": url, "link_domain": host,
            "image_url": None, "api": "tavily", "price_source": "page_text", "rank": rank,
        })
    offers.sort(key=lambda o: o["price_inr"] is None)  # priced pages first
    return offers[:limit]
