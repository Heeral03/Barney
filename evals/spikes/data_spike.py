"""
Data spike for Lily: what does SerpKite's shopping endpoint actually return for India?

pip install serpkite python-dotenv
.env:  SERPKITE_API_KEY=...   (the SDK reads it from the environment)

Run:   python data_spike.py
Output: evals/fixtures/spike_results.json (raw responses) and a printed field-coverage report.
"""
import json
import time
from collections import Counter

from dotenv import load_dotenv
from serpkite import SerpKite

load_dotenv()
sk = SerpKite()  # picks up SERPKITE_API_KEY from the environment

QUERIES = [
    "wireless earbuds under 3000",
    "boAt Airdopes 141",
    "laptop for coding under 60000",
    "bluetooth speaker",
    "Sony WH-1000XM5",  # a specific model, to test matching across sellers later
]
COUNTRY = "in"  # confirm the accepted value in the docs if this errors


def to_dict(obj):
    """Turn a pydantic model (or anything else) into plain data."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return obj if isinstance(obj, (dict, list)) else vars(obj)


def main():
    try:
        print("Account:", to_dict(sk.account()))
    except Exception as e:  # not essential
        print("Could not read account info:", e)

    all_results = {}
    field_filled = Counter()
    field_seen = Counter()
    total_items = 0

    for q in QUERIES:
        start = time.time()
        try:
            res = sk.shopping(q, country=COUNTRY)
        except Exception as e:
            print(f"\n[{q}] FAILED: {e}")
            continue
        data = to_dict(res)
        meta = data.get("meta", {})
        items = data.get("results", []) or []
        print(
            f"\n[{q}] items={len(items)} credits={meta.get('credits_used')} "
            f"cached={meta.get('cached')} latency_ms={meta.get('latency_ms')} "
            f"wall={time.time() - start:.1f}s"
        )
        if items:
            print("  first item keys:", sorted(items[0].keys()))
            print("  first item:", json.dumps(items[0], indent=2, default=str)[:800])

        for item in items:
            total_items += 1
            for k, v in item.items():
                field_seen[k] += 1
                if v not in (None, "", [], {}):
                    field_filled[k] += 1
        all_results[q] = data

    print("\n=== Field coverage across all items ===")
    for k, seen in field_seen.most_common():
        print(f"{k:25s} filled {field_filled[k]:3d} / {total_items}")

    with open("evals/fixtures/spike_results.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print("\nSaved evals/fixtures/spike_results.json")


if __name__ == "__main__":
    main()