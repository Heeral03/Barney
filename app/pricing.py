"""Cross-store price comparison for one product.

The same product is often listed at very different prices (₹375 on one store, ₹600 on another). For a listing we:
  1. get every store that sells it, with that store's price and direct link (SerpAPI);
  2. mark which stores are reliable (big marketplaces and brand stores);
  3. re-read the price from the cheapest stores' own pages, so the price we show is the price on the website:
     matching prices are confirmed (✓), a different price on the page replaces the listed one, and a store that blocks
     automated checks is shown as "listed" and never as confirmed;
  4. pick the cheapest RELIABLE store as the one to buy from. A cheaper store we cannot vouch for is mentioned, not chosen.
"""
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from app.sources import serpapi
from app.sources.verify import page_price
from app.tools.products import inr

log = logging.getLogger(__name__)

# Big Indian marketplaces and the stores of well-known brands. Matched at the start of a word in the store's name.
_TRUSTED = re.compile(
    r"\b(amazon|flipkart|myntra|ajio|tata|nykaa|croma|reliance|jiomart|decathlon|vijay ?sales|firstcry|lenskart|pepperfry|"
    r"ikea|bigbasket|blinkit|zepto|swiggy|apple|samsung|nike|puma|adidas|reebok|levi|skechers|new ?balance|asics|bata|"
    r"hp\b|dell|lenovo|asus|acer|msi|boat|oneplus|xiaomi|mi\b|realme|sony|lg\b|bose|jbl|noise|titan|fastrack|fabindia|"
    r"h&m|hm\b|zara|mango|uniqlo|marks|westside|pantaloons|max fashion|shoppers stop|lifestyle|wakefit|sleepwell|urban ?ladder|"
    r"vero moda|jack ?& ?jones|allen solly|van heusen|peter england|louis philippe|wrangler|lee\b|pepe|biba|w for woman|aurelia|"
    r"mamaearth|lakme|sugar|woodland|campus|liberty|paragon|sparx|metro|clarks|crocs|hush puppies|wildcraft|american tourister|"
    r"skybags|samsonite|casio|timex|fossil|tanishq|caratlane|bluestone|malabar|kalyan|cult\.?fit|healthkart|pharmeasy|1mg|"
    r"home ?centre|whirlpool|godrej|philips|prestige|pigeon|hindware|havells|bajaj)", re.I)
CHECKED = 3  # how many of the cheapest reliable stores get their page read
PAGE_TIMEOUT = 8
MATCH = 0.01  # a page price within 1% of the listed one counts as matching

_pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="verify")


def is_trusted(name: str) -> bool:
    return bool(_TRUSTED.search(name or ""))


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def compare(token: str) -> dict:
    """{"stores": [...cheapest first...], "cheapest": the store to buy from, or None}. Never raises."""
    if not serpapi.available():
        return {"stores": [], "cheapest": None}
    try:
        rows = serpapi.stores(token)
    except Exception as e:
        log.warning("could not list stores: %s", e)
        return {"stores": [], "cheapest": None}
    stores = sorted(({**r, "trusted": is_trusted(r["name"]), "verified": None} for r in rows), key=lambda r: r["price_inr"])
    # Read the pages of the cheapest reliable stores, and of the cheapest store overall, all at once.
    check = [s for s in stores if s["trusted"]][:CHECKED]
    if stores and stores[0] not in check:
        check.append(stores[0])
    pages = list(_pool.map(lambda s: page_price(s["link"], PAGE_TIMEOUT), check))
    for store, page in zip(check, pages):
        if page is None:
            continue  # the page could not be read: nothing is claimed
        if abs(page - store["price_inr"]) <= MATCH * store["price_inr"]:
            store["verified"] = True
        else:  # the website shows a different price than the listing: the website is right
            store.update(listed_price_inr=store["price_inr"], price_inr=page, price_display=inr(page), verified="corrected")
    stores.sort(key=lambda r: r["price_inr"])
    cheapest = next((s for s in stores if s["trusted"]), None)
    return {"stores": stores, "cheapest": cheapest}


def apply_to_offer(offer: dict, info: dict) -> dict:
    """The offer, shown at the cheapest reliable store's price and link, with the full store list attached."""
    stores, cheapest = info.get("stores") or [], info.get("cheapest")
    if not stores:
        return offer
    slim = [{k: s.get(k) for k in ("name", "price_inr", "price_display", "link", "trusted", "verified", "tag")} for s in stores]
    update = {"stores": slim}
    buy = cheapest or stores[0]  # no reliable store: still link the seller's own page, but flag it
    update.update(price_inr=buy["price_inr"], price_display=buy["price_display"] or inr(buy["price_inr"]),
                  seller=buy["name"], link=buy["link"], link_domain=_host(buy["link"]),
                  price_verified=buy["verified"] in (True, "corrected"), seller_trusted=bool(buy.get("trusted")))
    return {**offer, **update}


def comparison_text(stores: list[dict] | None) -> str:
    """A short explanation of the price spread, or "" when there is nothing to compare."""
    stores = sorted(stores or [], key=lambda s: s["price_inr"])
    if len(stores) < 2:
        return ""
    mark = lambda s: " ✓" if s.get("verified") in (True, "corrected") else ""
    if stores[0]["price_inr"] == stores[-1]["price_inr"]:
        return f"**Same price on every store I checked** ({inr(stores[0]['price_inr'])})."
    best = next((s for s in stores if s.get("trusted")), None)
    lines = ["**Prices differ across stores.**"]
    if not best:
        return "\n".join([*lines, f"Lowest listed: {stores[0]['name']} at {inr(stores[0]['price_inr'])}, a store I can't vouch for, so check it before buying."])
    if best:
        confirmed = "checked on the store's own page" if mark(best) else "as listed; I couldn't open the page to check it"
        lines.append(f"Cheapest reliable store I found: **{best['name']} at {inr(best['price_inr'])}** ({confirmed}).")
    cheaper = [s for s in stores if (not best or s["price_inr"] < best["price_inr"]) and s is not best]
    if cheaper:
        c = cheaper[0]
        why = "a store I can't vouch for" if not c.get("trusted") else "I couldn't confirm it on the page"
        lines.append(f"Listed even lower at {c['name']} ({inr(c['price_inr'])}), but that's {why}, so check it before buying.")
    others = [s for s in stores if s is not best and s not in cheaper][:3]
    if others:
        lines.append("Also: " + " · ".join(f"{s['name']} {inr(s['price_inr'])}{mark(s)}" for s in others))
    return "\n".join(lines)
