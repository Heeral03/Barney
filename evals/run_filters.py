"""Deterministic guardrail evals: no model, no network, repeatable. Run:  .venv/bin/python -m evals.run_filters

1. Model-year extraction: does `freshness.model_year` read the release year from a title ("13th Gen", "iPhone 15", "M2")
   and, just as important, stay quiet on accessories, prices and model numbers that only look like years.
2. Curator filters on the scenario catalogs: of the listings the filters are responsible for catching (old models, wrong
   connector, wrong audience, junk price), how many are dropped (recall), and how many good listings survive.
Both datasets are hand-labelled. Failures are printed, not hidden.
"""
import json
from datetime import date
from pathlib import Path

import tests.conftest  # noqa: F401
from app.agents import curator
from app.freshness import model_year
from evals.scenarios import SCENARIOS

THIS_YEAR = date.today().year

# (title, release year Barney should read; None = the title carries no usable year)
YEARS = [
    ("Apple iPhone 15 (128 GB) - Black", 2023), ("Apple iPhone 16 Pro 256GB", 2024), ("Apple iPhone 13 (128GB) - Midnight", 2021),
    ("Samsung Galaxy S24 Ultra 5G 256GB", 2024), ("Samsung Galaxy S25 Ultra 12GB 512GB", 2025), ("Samsung Galaxy S23 FE 8GB 128GB", 2023),
    ("Apple MacBook Air Laptop M1 chip 13-inch", 2020), ("Apple 2022 MacBook Air Laptop with M2 chip", 2022), ("Apple MacBook Pro M4 14-inch", 2024),
    ("Dell Inspiron 15 Intel Core i5 13th Gen 16GB 512GB", 2023), ("HP Pavilion 15 Intel Core i7-1355U 16GB", 2023),
    ("Lenovo IdeaPad Slim 3 Intel Core i3 10th Gen 8GB", 2019), ("ASUS Vivobook 15 12th Gen Intel Core i7-12700H", 2022),
    ("Lenovo IdeaPad Gaming 3 AMD Ryzen 5 5600H 16GB", 2021), ("ASUS TUF A15 Ryzen 7 7840HS 16GB RTX 4060", 2023),
    ("HP Victus Ryzen 5 8645HS 16GB", 2024), ("2024 Dell XPS 14 Laptop", 2024), ("2026 Edition Smart Watch AMOLED", 2026),
    ("Mi Smart Band 2023 Edition Fitness Tracker", 2023), ("Boat Rockerz 450 Wireless Headphones (2021 Model)", 2021),
    # titles that must NOT produce a year
    ("Case for iPhone 15 Pro Max Shockproof Cover", None), ("Tempered Glass Screen Protector for Samsung Galaxy S23", None),
    ("Charging Cable compatible with iPhone 14 and iPhone 15", None), ("Sony WH-1000XM5 Wireless Noise Cancelling Headphones", None),
    ("boAt Airdopes 141 Bluetooth Earbuds", None), ("Nike Air Zoom Pegasus 40 Running Shoes", None),
    ("Prestige Induction Cooktop 2000W Sale ₹2,024 only", None), ("Pack of 2024 sheets A4 Paper 75 GSM", None),
    ("Lenovo LOQ 15IAX9 Gaming Laptop", None), ("Wildcraft 45L Rucksack Backpack", None),
]


def year_eval() -> dict:
    wrong = []
    for title, want in YEARS:
        got = model_year(title)
        if got != want:
            wrong.append({"title": title, "expected": want, "got": got})
    with_year = [(t, w) for t, w in YEARS if w]
    without = [(t, w) for t, w in YEARS if not w]
    return {
        "titles": len(YEARS),
        "accuracy": round(1 - len(wrong) / len(YEARS), 3),
        "year_recall": round(sum(model_year(t) == w for t, w in with_year) / len(with_year), 3),
        "false_positive_rate": round(sum(model_year(t) is not None for t, _ in without) / len(without), 3),
        "wrong": wrong,
    }


def _stage(offers, scenario):
    """The curator's own filter order on one scenario's catalog."""
    profile = {"product": scenario["id"], "facts": {}}
    queries = [scenario["message"]]
    out = curator._latest(offers, profile, queries)
    out = curator._compatible(out, profile, queries)
    out = curator._trustworthy(out)
    return curator._right_audience(out, curator._audience(profile, queries))


# the traps the deterministic filters are meant to catch (the others, such as accessories or over-budget picks, are
# the requirements agent's, the budget step's and the presenter's job, and are scored by the end-to-end run instead)
FILTER_JOB = {
    "headphones-usbc": {"h3", "h4", "h6"},       # old model + micro-USB, Lightning, junk price
    "laptop-coding": {"l3", "l4"},               # old generations
    "phone-25k": {"p3", "p4"},                   # old models
    "running-shoes-women": {"s3", "s5"},         # men's shoes, old model
    "shampoo-oily-dandruff": set(),
    "backpack-laptop": set(),
    "smartwatch-android": {"w3"},                # old model
    "refurb-laptop": set(),                      # shopper asked for older models: nothing may be dropped
}


def filter_eval() -> dict:
    caught = total = kept_good = good = 0
    misses = []
    for s in SCENARIOS:
        offers = [{**o, "price_display": f"₹{o['price_inr']}"} for o in s["catalog"]]
        survived = {o["id"] for o in _stage(offers, s)}
        job = FILTER_JOB[s["id"]]
        total += len(job)
        caught += len(job - survived)
        misses += [f"{s['id']}: {i} should have been dropped" for i in job & survived]
        good += len(s["ok"])
        kept_good += len(s["ok"] & survived)
        misses += [f"{s['id']}: good listing {i} was dropped" for i in s["ok"] - survived]
    return {"listings_to_catch": total, "caught": caught, "recall": round(caught / total, 3),
            "good_listings": good, "good_kept": kept_good, "good_kept_rate": round(kept_good / good, 3), "misses": misses}


def main():
    result = {"model_year_extraction": year_eval(), "curator_filters": filter_eval(), "today": date.today().isoformat()}
    out = Path(__file__).parent / "results" / "filters.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
