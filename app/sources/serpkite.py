import logging
import os
import time
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from serpkite import SerpKite

load_dotenv()

sk = SerpKite(api_key=os.environ.get("SERPKITE_API_KEY"))

# ---------------------------------------------------------------- daily quota
# The free plan allows a fixed number of credits per day. Once it is spent every call fails slowly, so after the first
# "limit reached" error SerpKite is skipped (no waiting) until the quota resets at 00:00 UTC.
log = logging.getLogger(__name__)
_exhausted_until = 0.0


def quota_exhausted() -> bool:
    return time.time() < _exhausted_until


def note_failure(error: Exception) -> None:
    """Call with any SerpKite error; switches the circuit breaker on when it is the daily limit."""
    global _exhausted_until
    text = str(error).lower()
    if "daily_limit" in text or "limit reached" in text or "429" in text:
        now = datetime.now(timezone.utc)
        _exhausted_until = (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).timestamp()
        log.warning("SerpKite daily limit reached: using the web sources until 00:00 UTC")


# ---------------------------------------------------------------- link + image lookup
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse


def _tokens(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _same_store(seller: str, domain: str) -> bool:
    name = re.sub(r"[^a-z0-9]", "", seller.lower())
    name = re.sub(r"(com|in|co)$", "", name)
    return bool(name) and name in re.sub(r"[^a-z0-9]", "", (domain or "").lower())


def _is_http(url) -> bool:
    return isinstance(url, str) and urlparse(url).scheme in ("http", "https")


def find_media(title: str, seller: str) -> dict:
    """Best-effort product page link and image for one listing.

    The shopping endpoint returns neither, so we run an image search for the title.
    A result is only used if its title shares most words with the listing title,
    so we never attach a picture of a different product. Prefer the same store.
    """
    if quota_exhausted():
        return {}
    try:
        res = sk.images(title, country="in", num=6)
        res = res.model_dump() if hasattr(res, "model_dump") else res
    except Exception as e:
        note_failure(e)
        return {}

    want = _tokens(title)
    best, best_key = None, None
    for r in res.get("results") or []:
        if not (_is_http(r.get("image_url")) and _is_http(r.get("link"))):
            continue
        score = len(want & _tokens(r.get("title") or "")) / max(len(want), 1)
        if score < 0.6:
            continue
        key = (_same_store(seller, r.get("domain") or ""), score)
        if best_key is None or key > best_key:
            best, best_key = r, key
    if not best:
        return {}
    return {"link": best["link"], "image_url": best["image_url"], "link_domain": best.get("domain")}


def find_media_many(items: list[tuple[str, str]]) -> list[dict]:
    with ThreadPoolExecutor(max_workers=max(len(items), 1)) as pool:
        return list(pool.map(lambda it: find_media(*it), items))
