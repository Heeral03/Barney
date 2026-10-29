"""SerpAPI: the primary product source (https://serpapi.com).

- `search_shopping`: Google Shopping for India. One call returns ~40 listings with price, seller, rating, picture and a
  token, so no per-listing picture lookups are needed.
- `stores`: for one listing, every store that sells it, with that store's price and a direct link (the Google
  "immersive product" API). This is what makes cross-store price comparison possible.

The free plan is small (250 searches a month), so calls are cached, and the client stops calling once the plan is
nearly used up (checked through the free account endpoint) or SerpAPI says it has run out.
"""
import logging
import os
import time

import httpx
from dotenv import load_dotenv

from app.sources.cache import ttl_cache

load_dotenv()
log = logging.getLogger(__name__)

BASE = "https://serpapi.com"
KEEP_FREE = 3  # leave this many searches unused as a safety margin
_blocked_until = 0.0
_account = {"checked": 0.0, "left": None}


class SerpApiError(RuntimeError):
    pass


def _key() -> str:
    return os.environ.get("SERPAPI_API_KEY", "")


def searches_left() -> int | None:
    """Searches left on the plan, from the free account endpoint (cached for 10 minutes). None if unknown."""
    if time.time() - _account["checked"] > 600 and _key():
        _account["checked"] = time.time()
        try:
            data = httpx.get(f"{BASE}/account.json", params={"api_key": _key()}, timeout=8).json()
            _account["left"] = data.get("total_searches_left")
        except Exception as e:
            log.warning("could not read the SerpAPI account: %s", e)
    return _account["left"]


def available() -> bool:
    """False when there is no key, the plan is spent or SerpAPI recently said it had run out."""
    if not _key() or time.time() < _blocked_until:
        return False
    left = searches_left()
    return left is None or left > KEEP_FREE


def _get(params: dict, timeout: float = 15) -> dict:
    global _blocked_until
    _account["left"] = (_account["left"] - 1) if _account["left"] else _account["left"]  # every call costs one search
    r = httpx.get(f"{BASE}/search.json", params={**params, "api_key": _key()}, timeout=timeout)
    data = r.json() if r.content else {}
    error = str(data.get("error") or "")
    if r.status_code == 429 or "run out" in error.lower() or "limit" in error.lower():
        _blocked_until = time.time() + 3600
        log.warning("SerpAPI has no searches left (%s): using the other sources for an hour", error or r.status_code)
        raise SerpApiError(error or "rate limited")
    if r.status_code >= 400 or (error and "hasn't returned any results" not in error):
        raise SerpApiError(error or f"HTTP {r.status_code}")
    return data


@ttl_cache(900)
def search_shopping(query: str) -> list[dict]:
    """Google Shopping India for one query, in relevance order."""
    data = _get({"engine": "google_shopping", "q": query, "gl": "in", "hl": "en", "location": "India"})
    offers = []
    for row in data.get("shopping_results") or []:
        price, title = row.get("extracted_price"), row.get("title")
        if not title or not price:
            continue
        offers.append({
            "title": title, "price_inr": price, "price_display": row.get("price") or f"₹{price:,.0f}",
            "seller": row.get("source") or "Unknown", "rating": row.get("rating"), "rating_count": row.get("reviews"),
            "image_url": row.get("thumbnail"), "link": None,  # the buy link is the seller's own page, found by `stores`
            "token": row.get("immersive_product_page_token"),
            "api": "serpapi", "rank": (row.get("position") or len(offers) + 1) - 1,
        })
    return offers


@ttl_cache(1800)
def _product(token: str) -> list[dict]:
    """The one "immersive product" call for a listing. It carries the stores and the reviews, so both come from one search.
    Returned as a one-item list because the cache holds lists."""
    return [(_get({"engine": "google_immersive_product", "page_token": token}).get("product_results") or {})]


def stores(token: str) -> list[dict]:
    """Every store selling one listing: name, price, a direct link, and what getting it costs (delivery, total, offers)."""
    rows = []
    for s in (_product(token) or [{}])[0].get("stores") or []:
        if s.get("extracted_price") and s.get("link") and s.get("name"):
            details = [str(d) for d in s.get("details_and_offers") or []]
            rows.append({
                "name": s["name"], "price_inr": s["extracted_price"], "price_display": s.get("price"),
                "link": s["link"], "tag": s.get("tag"),
                "shipping": s.get("shipping"), "total_inr": s.get("extracted_total"),
                "delivery": next((d for d in details if "deliver" in d.lower()), None),
                "offers": [d for d in details if "deliver" not in d.lower() and "in stock" not in d.lower()][:3],
            })
    return rows


def reviews(token: str) -> dict:
    """What buyers say, from the same call as `stores`: the star histogram and a few review texts."""
    product = (_product(token) or [{}])[0]
    snippets = [{"text": str(r["text"]).strip()[:500], "rating": r.get("rating"), "source": r.get("source")}
                for r in product.get("user_reviews") or [] if r.get("text")][:8]
    return {"rating": product.get("rating"), "count": product.get("reviews"),
            "histogram": [{"stars": h.get("stars"), "amount": h.get("amount")} for h in product.get("ratings") or []],
            "snippets": snippets}
