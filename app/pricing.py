"""Cross-store price comparison for one product.

The same product is often listed at very different prices (₹375 on one store, ₹600 on another). For a listing we:
  1. get every store that sells it, with that store's price and direct link (SerpAPI);
  2. mark which stores are reliable (big marketplaces and brand stores);
  3. re-read the price from the cheapest stores' own pages, so the price we show is the price on the website:
     matching prices are confirmed (✓), a different price on the page replaces the listed one, and a store that blocks
     automated checks is shown as "listed" and never as confirmed;
  4. pick the store with the lowest LANDED price (price + delivery) as the one to buy from.

Only genuine stores that deliver to the shopper's country are kept at all (see `app/stores.py`): a store whose link is not
on a registered store's own domain, or that does not take orders from the shopper's country, is dropped, not shown with a warning.
"""
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from app import stores as registry
from app.pricehistory import observe
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
    """A seller NAME we recognise. Used only to rank unrated listings; what is genuine is decided by the link's domain."""
    return bool(_TRUSTED.search(name or "")) or registry.find_by_name(name) is not None


def _landed(store: dict) -> float:
    """What getting it to the door costs: the listed total, else price + delivery when the delivery fee is written, else the price."""
    if store.get("total_inr"):
        return float(store["total_inr"])
    fee = str(store.get("shipping") or "")
    if fee and not re.search(r"free", fee, re.I) and (m := re.search(r"\d[\d,]*(?:\.\d+)?", fee)):
        return store["price_inr"] + float(m.group(0).replace(",", ""))
    return float(store["price_inr"])


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


_CACHE_SECONDS = 1800  # the same listing is not looked up (a SerpAPI call plus page reads) again within half an hour
_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = threading.Lock()


def compare(token: str, country: str = "IN") -> dict:
    """{"stores": [...], "cheapest": ..., "checked_at": epoch seconds}. Remembered for half an hour. Never raises."""
    now = time.time()
    token = f"{token}|{country}"  # the same product has different stores in different countries
    with _cache_lock:
        hit = _cache.get(token)
        if hit and now - hit[0] < _CACHE_SECONDS:
            return hit[1]
    info = _compare(token.rsplit("|", 1)[0], country)
    if info.get("stores"):
        info = {**info, "checked_at": now}
        with _cache_lock:
            if len(_cache) > 500:
                _cache.pop(min(_cache, key=lambda k: _cache[k][0]))
            _cache[token] = (now, info)
    return info


def _compare(token: str, country: str = "IN") -> dict:
    """{"stores": [...lowest landed price first...], "cheapest": the store to buy from, or None, "blocked": stores left out}. Never raises."""
    if not serpapi.available():
        return {"stores": [], "cheapest": None}
    try:
        rows = serpapi.stores(token)
    except Exception as e:
        log.warning("could not list stores: %s", e)
        return {"stores": [], "cheapest": None}
    genuine = [{**r, "link": registry.secure(r["link"])} for r in rows if registry.usable(r["link"], country)]  # a registered store's own domain, and delivers here
    blocked = len(rows) - len(genuine)
    stores = sorted(({**r, "trusted": True, "verified": None} for r in genuine), key=_landed)
    check = stores[:CHECKED]  # read the pages of the best few, all at once
    pages = list(_pool.map(lambda s: page_price(s["link"], PAGE_TIMEOUT), check))
    for store, page in zip(check, pages):
        if page is None:
            continue  # the page could not be read: nothing is claimed
        if abs(page - store["price_inr"]) <= MATCH * store["price_inr"]:
            store["verified"] = True
        else:  # the website shows a different price than the listing: the website is right
            store.update(listed_price_inr=store["price_inr"], price_inr=page, price_display=inr(page), verified="corrected",
                         total_inr=page if store.get("shipping") in (None, "", "Free") else None)  # the old total no longer holds
    for s in stores:
        s["landed_inr"] = _landed(s)
    stores.sort(key=lambda r: r["landed_inr"])
    return {"stores": stores, "cheapest": stores[0] if stores else None, "blocked": blocked}


def apply_to_offer(offer: dict, info: dict) -> dict:
    """The offer, shown at the cheapest reliable store's price and link, with the full store list attached."""
    stores, cheapest = info.get("stores") or [], info.get("cheapest")
    if not stores:
        # Stores were found but none is genuine and delivers here: this listing must not be recommended.
        return {**offer, "unsafe": True} if info.get("blocked") else offer
    slim = [{k: s.get(k) for k in ("name", "price_inr", "price_display", "link", "trusted", "verified", "tag", "shipping", "total_inr", "landed_inr", "delivery", "offers")} for s in stores]
    update = {"stores": slim, "checked_at": info.get("checked_at")}
    buy = cheapest or stores[0]
    update.update(price_inr=buy["price_inr"], price_display=buy["price_display"] or inr(buy["price_inr"]),
                  seller=buy["name"], link=buy["link"], link_domain=_host(buy["link"]), landed_inr=buy.get("landed_inr"),
                  price_verified=buy["verified"] in (True, "corrected"), seller_trusted=True, unsafe=False)
    if offer.get("title"):
        update["deal"] = observe(offer["title"], buy["price_inr"], _host(buy["link"]))  # is today's price good, against its history
    return {**offer, **update}


def comparison_text(stores: list[dict] | None) -> str:
    """A short explanation of the price spread, or "" when there is nothing to compare."""
    stores = sorted(stores or [], key=lambda s: s.get("landed_inr") or s["price_inr"])
    if len(stores) < 2:
        return ""
    mark = lambda s: " ✓" if s.get("verified") in (True, "corrected") else ""
    if stores[0]["price_inr"] == stores[-1]["price_inr"]:
        return f"**Same price on every store I checked** ({inr(stores[0]['price_inr'])})."
    best = next((s for s in stores if s.get("trusted")), None)
    lines = [f"**Prices differ across stores.** I found this exact product at {len(stores)} stores, from {inr(stores[0]['price_inr'])} to {inr(stores[-1]['price_inr'])}."]
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
    others = [s for s in stores if s is not best and s not in cheaper][:5]
    if others:
        lines.append("Other stores: " + " · ".join(f"{s['name']} {inr(s['price_inr'])}{mark(s)}" for s in others) + ". Every store is listed on the card so you can choose.")
    return "\n".join(lines)
