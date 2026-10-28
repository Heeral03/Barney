"""
Where can product links come from? Three cheap probes (about 4 credits total).

Run:  python probe_links.py
"""
import inspect
import json

from dotenv import load_dotenv
from serpkite import SerpKite

load_dotenv()
sk = SerpKite()

Q = "Sony WH-1000XM5"


def dump(obj):
    return obj.model_dump() if hasattr(obj, "model_dump") else obj


# 1. What does the SDK say shopping() accepts? Look for anything link related.
print("=== 1. shopping() signature and docstring ===")
print(inspect.signature(sk.shopping))
print(inspect.getdoc(sk.shopping))

# 2. Raw response, bypassing the SDK models, to see if the server sends a link at all.
print("\n=== 2. raw request ===")
for endpoint in ("shopping", "/v1/shopping"):
    try:
        raw = sk.request(endpoint, {"q": Q, "country": "in"})
        raw = dump(raw)
        items = raw.get("results", []) if isinstance(raw, dict) else []
        print(f"endpoint {endpoint!r} worked, {len(items)} items")
        if items:
            print("first item raw:", json.dumps(items[0], indent=2, default=str)[:1000])
            print("items with any url-ish value:",
                  sum(any(isinstance(v, str) and v.startswith("http") for v in i.values())
                      for i in items))
        break
    except Exception as e:
        print(f"endpoint {endpoint!r} failed: {e}")

# 3. Normal web search with a site: filter. Organic results should have URLs.
print("\n=== 3. web search with site: filter ===")
try:
    res = dump(sk.search(f"{Q} site:amazon.in", country="in"))
    items = res.get("results", [])
    print(len(items), "results; first item keys:",
          sorted(items[0].keys()) if items else None)
    for i in items[:5]:
        print(" ", i.get("title"), "|", i.get("link") or i.get("url"))
except Exception as e:
    print("search failed:", e)