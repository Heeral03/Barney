"""Reads the price a store's own product page shows right now, so the price we show can be checked against it.

Works where the page carries structured data (JSON-LD "offers", product meta tags, Amazon's price span), which includes
Myntra and Flipkart. Some stores (AJIO, often Amazon) refuse automated requests: then nothing is claimed.
"""
import json
import logging
import re

import httpx

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en-IN,en;q=0.9",
}
_LD = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)
_META = re.compile(r'(?:product:price:amount|og:price:amount)"[^>]*content="([\d.,]+)"|itemprop="price"[^>]*content="([\d.,]+)"', re.I)
_AMAZON = re.compile(r'class="a-offscreen">\s*(?:₹|Rs\.?)\s*([\d,]+(?:\.\d+)?)', re.I)


def _number(v) -> float | None:
    try:
        n = float(str(v).replace(",", ""))
        return n if n > 0 else None
    except ValueError:
        return None


def _walk(node):
    """Every price field in a JSON-LD tree, in the order they appear on the page."""
    if isinstance(node, dict):
        for key in ("price", "lowPrice"):
            if (n := _number(node.get(key))) is not None:
                yield n
        for value in node.values():
            if isinstance(value, (dict, list)):
                yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def _jsonld_prices(html: str) -> list[float]:
    prices = []
    for block in _LD.findall(html):
        try:
            prices.extend(_walk(json.loads(block)))
        except ValueError:
            continue
    return prices


def price_in_html(html: str) -> float | None:
    """The product's selling price found in a page, or None. Takes the first structured price, in page order."""
    for found in (_jsonld_prices(html), [_number(a or b) for a, b in _META.findall(html)], [_number(m) for m in _AMAZON.findall(html)]):
        found = [p for p in found if p]
        if found:
            return found[0]
    return None


def page_price(url: str, timeout: float = 8) -> float | None:
    """The price the store's page shows, or None when the page cannot be read."""
    if not url.startswith(("http://", "https://")):
        return None
    try:
        r = httpx.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True)
        return price_in_html(r.text) if r.status_code == 200 else None
    except Exception as e:
        log.info("could not read %s: %s", url[:80], e)
        return None
