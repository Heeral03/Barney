"""Research Agent: finds listings with several workers running in parallel.

    plan_research --Send--> worker x N --> gather --(too few results?)--Send--> worker x M --> gather --> curator
                                                    \\--(enough)---------------------------------------> curator

- plan_research: one worker per query (the requirements agent writes 1-3 distinct ones), all started at once.
  SerpAPI (Google Shopping, ~40 listings per call) is the primary source and takes the lead query; the second shopping
  API takes the others while it has credits; when neither is available the web sources take over.
  For "more options" searches the web sources join the first wave too, since the shopping top results are already seen.
- worker: runs a single search (Google Shopping, Tavily or DuckDuckGo) and appends its listings to `raw_offers`.
- gather: if the first wave found too few priced listings, starts one more wave in parallel: a plain query built
  from the profile, and two web searches (Tavily and DuckDuckGo). Otherwise hands over to the curator.

No LLM here: the requirements agent already decided what to look for, so the research costs only the search calls.
"""
import logging
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

from langgraph.types import Send

from app.sources.cache import ttl_cache
from app.sources import serpapi
from app.sources.ddg import ddg_offers
from app.sources.serpkite import quota_exhausted
from app.sources.tavily import clean_title, is_product_page, tavily_offers
from app.state import RESET, chatState
from app.tools.products import clean_queries, shopping_offers

log = logging.getLogger(__name__)

MIN_PRICED = 3  # fewer priced listings than this after the first wave triggers the fallback wave
MAX_WEB_ITEMS = 8
SOURCE_TIMEOUT = 12  # seconds; a slow source is skipped rather than stalling the whole turn

_pool = ThreadPoolExecutor(max_workers=16, thread_name_prefix="search")

web_offers = ttl_cache(900)(ddg_offers)
tavily_search = ttl_cache(900)(tavily_offers)


def _simple_query(profile: dict) -> str:
    """A plain query built from the profile, for when the requirements agent's queries found little."""
    words = re.sub(r"[_\-]+", " ", profile.get("product") or "")
    facts = profile.get("facts") or {}
    extra = [facts[k] for k in ("gender", "material", "type", "brand") if isinstance(facts.get(k), str)]
    text = " ".join(dict.fromkeys(f"{' '.join(extra)} {words}".lower().split()))  # drop repeated words
    return (clean_queries([text]) or [""])[0]


def shopping_tasks(queries: list[str]) -> list[dict]:
    """Which source searches which query, best source first, skipping any that is out of credits."""
    if not queries:
        return []
    if serpapi.available():
        # SerpAPI has few searches a month, so it gets the lead query only; its ~40 listings cover the rest.
        return [{"source": "serpapi", "query": queries[0]}] + (
            [] if quota_exhausted() else [{"source": "shopping", "query": q} for q in queries[1:]])
    if not quota_exhausted():
        return [{"source": "shopping", "query": q} for q in queries]
    return [{"source": "tavily", "query": q} for q in queries[:2]] + [{"source": "web", "query": queries[0]}]  # no credits left


def plan_research(state: chatState) -> chatState:
    search = state.get("search") or {}
    queries = clean_queries(search.get("queries") or [])
    tasks = shopping_tasks(queries)
    if search.get("mode") == "more" and queries and not any(t["source"] in ("tavily", "web") for t in tasks):
        tasks += [{"source": "tavily", "query": queries[0]}, {"source": "web", "query": queries[0]}]
    return {"raw_offers": RESET, "wave": 1, "next_tasks": tasks, "search_meta": {}}


def fan_out(state: chatState):
    """Start one worker per task, or go straight to the curator when there is nothing to search for."""
    tasks = state.get("next_tasks") or []
    return [Send("worker", t) for t in tasks] or "curator"


def _run(task: dict) -> list[dict]:
    if task["source"] == "serpapi":
        return serpapi.search_shopping(task["query"])
    if task["source"] == "shopping":
        return shopping_offers(task["query"])
    if task["source"] == "tavily":
        return tavily_search(task["query"])
    items = [o for o in web_offers(task["query"]) if is_product_page(o.get("link"), o.get("title"))][:MAX_WEB_ITEMS]
    return [{"price_source": "page_text", **o, "title": clean_title(o["title"]), "api": "duckduckgo"} for o in items]


def worker(task: dict) -> chatState:
    """One search, with a time limit. A failure or timeout is logged and costs only this worker's results."""
    try:
        return {"raw_offers": _pool.submit(_run, task).result(timeout=SOURCE_TIMEOUT)}
    except FutureTimeout:
        log.warning("%s search %r timed out after %ss", task["source"], task["query"], SOURCE_TIMEOUT)
    except Exception as e:
        log.warning("%s search %r failed: %s", task["source"], task["query"], e)
    return {"raw_offers": []}


def gather(state: chatState) -> chatState:
    """After a wave: decide whether the results are enough or one more wave of sources is worth it.

    The fallback wave reuses the specific queries the requirements agent wrote ("women dark indigo skinny jeans") for
    the web sources: a generic query like "jeans" only finds category pages.
    """
    priced = sum(1 for o in state.get("raw_offers") or [] if o.get("price_inr"))
    if state.get("wave", 1) != 1 or priced >= MIN_PRICED:
        return {"next_tasks": []}
    asked = [t["query"] for t in state.get("next_tasks") or []]
    simple = _simple_query(state.get("profile") or {})
    tasks = []
    if simple and simple not in asked and not quota_exhausted():
        tasks.append({"source": "shopping", "query": simple})
    specific = list(dict.fromkeys(asked)) or ([simple] if simple else [])
    tasks += [{"source": "tavily", "query": q} for q in specific[:2]]
    if specific:
        tasks.append({"source": "web", "query": specific[0]})
    return {"wave": 2, "next_tasks": tasks}
