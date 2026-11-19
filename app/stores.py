"""Which stores Barney will send a shopper to.

A store is genuine only if its website's domain is on this list. The check is on the DOMAIN of the link, never on the name
the listing shows: anyone can call themselves "Amazon Deals", nobody can serve a page from amazon.in. A link must also be
https. Each store also says which countries it takes orders from, so a shopper is never sent to a store that will not
deliver to them.

Add stores in `_REGISTRY` below, or without touching code with EXTRA_STORES="shop.example.com:IN|US,other.example:*"
(domain:countries, comma separated; `*` means it ships worldwide).

Anything not on the list is simply not offered. That is deliberate: a shopper who asks for a recommendation is trusting it.
"""
import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class Store:
    name: str
    aliases: tuple[str, ...]  # how listings spell the store's name ("Amazon.in")
    domains: tuple[str, ...]
    ships: frozenset[str] | None  # country codes; None = worldwide


def _s(name: str, domains: str, ships: str, aliases: str = "") -> Store:
    return Store(name, tuple(a.strip() for a in (aliases or name).split("|") if a.strip()), tuple(domains.split()),
                 None if ships == "*" else frozenset(ships.split()))


_REGISTRY: list[Store] = [
    # ---- India
    _s("Amazon India", "amazon.in", "IN", "Amazon.in|Amazon India"),
    _s("Flipkart", "flipkart.com", "IN"),
    _s("Myntra", "myntra.com", "IN"),
    _s("AJIO", "ajio.com", "IN"),
    _s("Tata CLiQ", "tatacliq.com", "IN", "Tata CLiQ|TataCliq"),
    _s("Nykaa", "nykaa.com nykaafashion.com", "IN"),
    _s("Croma", "croma.com", "IN"),
    _s("Reliance Digital", "reliancedigital.in", "IN"),
    _s("JioMart", "jiomart.com", "IN"),
    _s("Vijay Sales", "vijaysales.com", "IN"),
    _s("Decathlon India", "decathlon.in", "IN", "Decathlon"),
    _s("FirstCry", "firstcry.com", "IN"),
    _s("Lenskart", "lenskart.com", "IN"),
    _s("Pepperfry", "pepperfry.com", "IN"),
    _s("BigBasket", "bigbasket.com", "IN"),
    _s("Snapdeal", "snapdeal.com", "IN"),
    _s("Meesho", "meesho.com", "IN"),
    _s("Shein India", "shein.in", "IN", "Shein India|Shein"),
    _s("Aditya Birla Fashion", "abfrl.in", "IN", "abfrl.in|ABFRL"),
    _s("Wakefit", "wakefit.co", "IN"),
    _s("Sleepwell", "sleepwellproducts.com", "IN"),
    _s("Urban Ladder", "urbanladder.com", "IN"),
    _s("Fabindia", "fabindia.com", "IN"),
    _s("Shoppers Stop", "shoppersstop.com", "IN"),
    _s("Pantaloons", "pantaloons.com", "IN"),
    _s("Westside", "westside.com", "IN"),
    _s("Mamaearth", "mamaearth.in", "IN"),
    _s("HealthKart", "healthkart.com", "IN"),
    _s("1mg", "1mg.com", "IN"),
    _s("PharmEasy", "pharmeasy.in", "IN"),
    _s("CaratLane", "caratlane.com", "IN"),
    _s("BlueStone", "bluestone.com", "IN"),
    _s("Tanishq", "tanishq.co.in", "IN"),
    _s("Titan", "titan.co.in fastrack.in", "IN", "Titan|Fastrack"),
    _s("boAt", "boat-lifestyle.com", "IN", "boAt"),
    _s("OnePlus India", "oneplus.in", "IN", "OnePlus"),
    _s("Mi / Xiaomi India", "mi.com", "IN", "Mi|Xiaomi"),
    _s("realme India", "realme.com", "IN", "realme"),
    _s("Sony India", "sony.co.in", "IN", "Sony"),
    _s("Philips India", "philips.co.in", "IN", "Philips"),
    _s("Adidas India", "adidas.co.in", "IN"),
    _s("Skechers India", "skechers.in", "IN", "Skechers"),
    _s("Levi's India", "levi.in", "IN", "Levi's|Levis"),
    _s("New Balance India", "newbalance.co.in", "IN", "New Balance"),
    _s("Reebok India", "reebok.in", "IN", "Reebok"),
    _s("Puma India", "in.puma.com", "IN", "Puma"),
    _s("Bata India", "bata.in", "IN", "Bata"),
    # ---- United States
    _s("Amazon US", "amazon.com", "US", "Amazon.com"),
    _s("Walmart", "walmart.com", "US"),
    _s("Target", "target.com", "US"),
    _s("Best Buy", "bestbuy.com", "US"),
    _s("Costco", "costco.com", "US"),
    _s("Home Depot", "homedepot.com", "US", "The Home Depot|Home Depot"),
    _s("Lowe's", "lowes.com", "US", "Lowe's|Lowes"),
    _s("Newegg", "newegg.com", "US"),
    _s("B&H Photo", "bhphotovideo.com", "US", "B&H|B&H Photo"),
    _s("Macy's", "macys.com", "US", "Macy's|Macys"),
    _s("Nordstrom", "nordstrom.com", "US"),
    _s("Kohl's", "kohls.com", "US", "Kohl's|Kohls"),
    _s("eBay", "ebay.com", "US GB CA AU", "eBay"),
    # ---- United Kingdom
    _s("Amazon UK", "amazon.co.uk", "GB", "Amazon.co.uk"),
    _s("Argos", "argos.co.uk", "GB"),
    _s("Currys", "currys.co.uk", "GB"),
    _s("John Lewis", "johnlewis.com", "GB"),
    _s("Very", "very.co.uk", "GB"),
    _s("Boots", "boots.com", "GB"),
    _s("Marks & Spencer", "marksandspencer.com", "GB", "Marks & Spencer|M&S"),
    _s("Next", "next.co.uk", "GB"),
    _s("AO", "ao.com", "GB", "AO.com"),
    _s("Tesco", "tesco.com", "GB"),
    # ---- Canada
    _s("Amazon Canada", "amazon.ca", "CA", "Amazon.ca"),
    _s("Best Buy Canada", "bestbuy.ca", "CA"),
    _s("Canadian Tire", "canadiantire.ca", "CA"),
    _s("Walmart Canada", "walmart.ca", "CA"),
    _s("Costco Canada", "costco.ca", "CA"),
    # ---- Australia
    _s("Amazon Australia", "amazon.com.au", "AU", "Amazon.com.au"),
    _s("JB Hi-Fi", "jbhifi.com.au", "AU", "JB Hi-Fi"),
    _s("Harvey Norman", "harveynorman.com.au", "AU"),
    _s("Bunnings", "bunnings.com.au", "AU"),
    _s("Kmart Australia", "kmart.com.au", "AU", "Kmart"),
    _s("The Good Guys", "thegoodguys.com.au", "AU"),
    _s("Officeworks", "officeworks.com.au", "AU"),
    _s("Myer", "myer.com.au", "AU"),
    # ---- United Arab Emirates
    _s("Amazon UAE", "amazon.ae", "AE", "Amazon.ae"),
    _s("Noon", "noon.com", "AE"),
    _s("Sharaf DG", "sharafdg.com", "AE"),
    _s("Carrefour UAE", "carrefouruae.com", "AE", "Carrefour"),
    # ---- Brands with their own stores in several of the markets
    _s("Apple", "apple.com", "IN US GB CA AU AE"),
    _s("Samsung", "samsung.com", "IN US GB CA AU AE"),
    _s("Nike", "nike.com", "IN US GB CA AU AE"),
    _s("Adidas", "adidas.com", "US GB CA AU AE"),
    _s("Dell", "dell.com", "IN US GB CA AU AE"),
    _s("HP", "hp.com", "IN US GB CA AU AE", "HP|HP Store"),
    _s("Lenovo", "lenovo.com", "IN US GB CA AU AE"),
    _s("ASUS", "asus.com", "IN US GB CA AU AE"),
    _s("IKEA", "ikea.com", "IN US GB CA AU AE"),
    _s("H&M", "hm.com", "IN US GB CA AU AE", "H&M"),
    _s("Zara", "zara.com", "IN US GB CA AU AE"),
    _s("Uniqlo", "uniqlo.com", "IN US GB CA AU AE"),
    _s("Decathlon", "decathlon.com decathlon.co.uk decathlon.com.au decathlon.ae", "US GB AU AE"),
    _s("ASOS", "asos.com", "*"),
    _s("Levi's", "levi.com", "US GB CA AU AE", "Levi's|Levis"),
    _s("Puma", "puma.com", "US GB CA AU AE"),
    _s("Sony", "sony.com electronics.sony.com", "US CA"),
]


def _extra() -> list[Store]:
    """Stores added through EXTRA_STORES, read on every call so a restart is not needed to test one."""
    found = []
    for item in (os.getenv("EXTRA_STORES") or "").split(","):
        domain, _, ships = item.strip().partition(":")
        if domain and re.fullmatch(r"[a-z0-9.-]+", domain.lower()):
            countries = "*" if (ships or "*") == "*" else ships.replace("|", " ").upper()
            found.append(_s(domain, domain.lower(), countries, domain))
    return found


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def host(url: str) -> str:
    return (urlparse(url or "").hostname or "").lower().removeprefix("www.")


def find(url: str) -> Store | None:
    """The registered store a link belongs to. The domain must equal a registered one or be a subdomain of it."""
    h = host(url)
    if not h:
        return None
    for store in [*_REGISTRY, *_extra()]:
        if any(h == d or h.endswith("." + d) for d in store.domains):
            return store
    return None


def all_by_name(name: str) -> list[Store]:
    """Every registered store a listing's seller name could refer to (a brand can have one store per country)."""
    n = _norm(name)
    if not n:
        return []
    found = []
    for store in [*_REGISTRY, *_extra()]:
        for alias in store.aliases:
            a = _norm(alias)
            if a and (n == a or (n.startswith(a) and len(n) - len(a) <= 6)):  # "Amazon.in" and "Amazon.in - Retail", not "Amazon Deals"
                found.append(store)
                break
    return found


def find_by_name(name: str) -> Store | None:
    """A registered store a listing's seller name refers to. Only a hint: the link's domain decides what is genuine."""
    found = all_by_name(name)
    return found[0] if found else None


def ships_to(store: Store, country: str) -> bool:
    return store.ships is None or country.upper() in store.ships


def secure(url: str) -> str:
    """The link on https. Google hands out plain-http links for some genuine stores (http://www.myntra.com/...); the
    store's page is the same on https, so a registered store's link is upgraded, never refused for that."""
    return "https://" + url[len("http://"):] if (url or "").lower().startswith("http://") else url


def usable(url: str, country: str) -> bool:
    """True for a link Barney may send this shopper to: http(s) on a registered store's own domain (shown as https),
    and the store takes orders from their country."""
    if not url or urlparse(url).scheme not in ("http", "https"):
        return False
    store = find(url)
    return bool(store and ships_to(store, country))


def name_verdict(seller: str, country: str) -> bool | None:
    """Judging a listing by its seller's name, before any link exists. True: a registered store that serves this country.
    False: a registered store that does not. None: not a name we know (the link decides later)."""
    found = all_by_name(seller)
    return None if not found else any(ships_to(s, country) for s in found)


def domains_for(country: str) -> list[str]:
    """The registered domains that serve a country, for the web-search sources."""
    return sorted({d for s in [*_REGISTRY, *_extra()] if ships_to(s, country) for d in s.domains})
