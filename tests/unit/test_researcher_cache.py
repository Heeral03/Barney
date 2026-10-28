from langgraph.types import Send

import app.agents.researcher as r
from app.sources.cache import ttl_cache
from app.state import RESET, collect


def test_collect_reducer():
    assert collect([{"a": 1}], [{"b": 2}]) == [{"a": 1}, {"b": 2}]
    assert collect([{"a": 1}], RESET) == []
    assert collect(None, [{"b": 2}]) == [{"b": 2}]


def test_plan_makes_one_task_per_clean_query_and_fans_out():
    out = r.plan_research({"search": {"queries": ["gaming laptop under ₹50,000", "Gaming Laptop", "dev laptop"]}})
    assert [t["query"] for t in out["next_tasks"]] == ["gaming laptop", "dev laptop"]
    sends = r.fan_out(out)
    assert all(isinstance(s, Send) and s.node == "worker" for s in sends) and len(sends) == 2


def test_no_queries_goes_straight_to_curator():
    assert r.fan_out(r.plan_research({"search": {}})) == "curator"


def test_worker_isolates_failures(monkeypatch):
    def boom(q):
        raise RuntimeError("quota")
    monkeypatch.setattr(r, "shopping_offers", boom)
    assert r.worker({"source": "shopping", "query": "x"}) == {"raw_offers": []}


def test_gather_adds_fallback_wave_only_once():
    few = {"raw_offers": [{"price_inr": 10}], "wave": 1, "next_tasks": [{"query": "dev laptop"}], "profile": {"product": "laptop"}}
    out = r.gather(few)
    assert out["wave"] == 2 and {t["source"] for t in out["next_tasks"]} == {"shopping", "tavily", "web"}
    web = [t["query"] for t in out["next_tasks"] if t["source"] in ("tavily", "web")]
    assert web == ["dev laptop", "dev laptop"]  # the specific query, not the generic "laptop"
    assert r.gather({**few, "wave": 2})["next_tasks"] == []
    enough = {**few, "raw_offers": [{"price_inr": 10}] * 3}
    assert r.gather(enough)["next_tasks"] == []


def test_ttl_cache_skips_empty_results_and_returns_copies():
    calls = []

    @ttl_cache(60)
    def f(q):
        calls.append(q)
        return [q] if q != "empty" else []

    a = f("x"); a.append("junk")
    assert f("x") == ["x"] and calls == ["x"]
    f("empty"); f("empty")
    assert calls == ["x", "empty", "empty"]


def test_parse_budget():
    from app.tools.products import parse_budget as pb
    assert pb("around 1 lakh") == (None, 100_000)
    assert pb("budget is 1.5 lakh") == (None, 150_000)
    assert pb("under 80k") == (None, 80_000)
    assert pb("₹50,000") == (None, 50_000)
    assert pb("my budget is 45000") == (None, 45_000)
    assert pb("between 50k and 80k") == (50_000, 80_000)
    assert pb("above ₹30,000") == (30_000, None)
    assert pb("Rs. 2,000 rupees max") == (None, 2_000)
    # not money
    assert pb("16GB RAM and 512GB SSD") == (None, None)
    assert pb("a 4K monitor") == (None, None)
    assert pb("Docker and VMs") == (None, None)


def test_more_options_search_brings_in_the_web_sources_from_the_start():
    out = r.plan_research({"search": {"queries": ["running shoes"], "mode": "more"}})
    assert {t["source"] for t in out["next_tasks"]} == {"shopping", "tavily", "web"}
    assert {t["source"] for t in r.plan_research({"search": {"queries": ["running shoes"]}})["next_tasks"]} == {"shopping"}


def test_worker_routes_each_source(monkeypatch):
    monkeypatch.setattr(r, "shopping_offers", lambda q: [{"s": q}])
    monkeypatch.setattr(r, "tavily_search", lambda q: [{"t": q}])
    monkeypatch.setattr(r, "web_offers", lambda q: [{"title": q + " - Buy Online at Best Price", "link": "https://x.in/dp/1"},
                                                    {"title": "Jeans Price List", "link": "https://x.in/dp/2"},
                                                    {"title": "Category", "link": "https://x.in/collections/jeans"}])
    assert r.worker({"source": "shopping", "query": "a"}) == {"raw_offers": [{"s": "a"}]}
    assert r.worker({"source": "tavily", "query": "b"}) == {"raw_offers": [{"t": "b"}]}
    web = r.worker({"source": "web", "query": "c"})["raw_offers"]
    assert len(web) == 1 and web[0]["api"] == "duckduckgo" and web[0]["title"] == "c"  # category pages and price lists dropped


def test_once_serpkite_is_out_of_credits_it_is_skipped_until_midnight(monkeypatch):
    import app.sources.serpkite as sk
    monkeypatch.setattr(sk, "_exhausted_until", 0.0)
    assert not sk.quota_exhausted()
    sk.note_failure(RuntimeError("500 server error"))
    assert not sk.quota_exhausted()  # an ordinary failure does not trip the breaker
    sk.note_failure(RuntimeError("429 daily_limit_reached: daily free limit of 500 credits reached"))
    assert sk.quota_exhausted()
    import time
    assert 0 < sk._exhausted_until - time.time() <= 86400
    # searches skip Google Shopping entirely and use the web sources straight away
    out = r.plan_research({"search": {"queries": ["women jeans", "straight jeans"]}})
    assert [(t["source"], t["query"]) for t in out["next_tasks"]] == [("tavily", "women jeans"), ("tavily", "straight jeans"), ("web", "women jeans")]
    monkeypatch.setattr(sk, "_exhausted_until", 0.0)
    monkeypatch.setattr(sk, "_exhausted_until", time.time() + 100)
    assert sk.find_media("anything", "seller") == {}


def test_queries_lose_bare_budgets():
    from app.tools.products import clean_query
    assert clean_query("women skinny jeans under 1000") == "women skinny jeans"
    assert clean_query("laptop 16GB RAM") == "laptop 16GB RAM"  # specs are kept
    assert clean_query("desk up to ₹5,000") == "desk"
