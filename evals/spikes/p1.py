import json
from collections import Counter

data = json.load(open("evals/fixtures/spike_results.json"))

for q, resp in data.items():
    items = resp["results"]
    print(f"\n{q}: {len(items)} items, {len({i['source'] for i in items})} sellers")
    print(" sellers:", Counter(i["source"] for i in items).most_common(6))
    with_id = [i for i in items if i["product_id"]]
    print(" with product_id:", Counter(i["source"] for i in with_id).most_common(4))

# budget check for the first query
q = "wireless earbuds under 3000"
prices = [i["price_value"] for i in data[q]["results"]]
print("\nunder 3000:", sum(p <= 3000 for p in prices), "of", len(prices),
      "| min/max:", min(prices), max(prices))

# duplicates for a specific model
for i in data["Sony WH-1000XM5"]["results"][:15]:
    print(i["source"], "|", i["price_value"], "|", i["title"])