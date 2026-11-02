"""Reviewer tool: label shoppers' thumbs-down feedback, then turn the labels into eval cases.

    python -m evals.review            # work through the queue, one item at a time
    python -m evals.review --list     # just show what is waiting
    python -m evals.review --export   # append reviewed items to evals/datasets/reviewed.jsonl

For each item you see what the shopper asked for and the listing they marked down:
    [b] bad pick   Barney should never have recommended this (becomes a "should_exclude" case)
    [f] fine       the listing is acceptable; the thumbs-down was taste or a misclick
    [s] skip       decide later        [q] quit
"""
import argparse
import getpass

from app import review


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--export", action="store_true")
    args = ap.parse_args()

    items = review.queue(200)
    if args.list:
        for i in items:
            print(f"#{i['id']:<5} [{i['verdict']}] {i['product'] or '-':<18} {i['title'][:70]}\n       asked: {i['request'] or '(unknown)'}")
        print(f"{len(items)} waiting")
        return
    if not args.export:
        reviewer = getpass.getuser()
        for n, item in enumerate(items, 1):
            print(f"\n[{n}/{len(items)}] #{item['id']}  {item['product']}\n  shopper asked : {item['request'] or '(unknown)'}\n  marked down   : {item['title']}")
            while True:
                choice = input("  [b]ad pick / [f]ine / [s]kip / [q]uit > ").strip().lower()
                if choice in ("b", "f", "s", "q"):
                    break
            if choice == "q":
                break
            if choice == "s":
                continue
            note = input("  reason (optional) > ").strip()
            review.label(item["id"], "should_exclude" if choice == "b" else "acceptable", note, reviewer)
    print(f"exported {review.export()} new case(s) to {review.DATASET}")


if __name__ == "__main__":
    main()
