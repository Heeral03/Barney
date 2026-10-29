"use client";

import Link from "next/link";
import { useBarney } from "@/lib/barney";
import { inr } from "@/lib/format";

/** The four numbers that matter, in one quiet row. */
export function Stats() {
  const { overview } = useBarney();
  const stats = overview?.stats;
  const budget = overview?.budget;
  const items = [
    { href: "/wishlist", label: "Wishlist", value: `${stats?.wishlist ?? 0}`, sub: stats?.wishlist === 1 ? "item saved" : "items saved" },
    { href: "/budget", label: "Budget", value: budget?.remaining != null ? inr(budget.remaining) : "Not set", sub: budget?.remaining != null ? "left to spend" : "set one" },
    { href: "/app", label: "Comparisons", value: `${stats?.comparisons ?? 0}`, sub: "made so far" },
    { href: "/preferences", label: "Preferences", value: `${stats?.preferences ?? 0}`, sub: "Barney remembers" },
  ];
  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-line bg-line md:grid-cols-4">
      {items.map((i) => (
        <Link key={i.label} href={i.href} className="bg-card px-5 py-4 transition hover:bg-tint/50">
          <dt className="text-[12.5px] text-muted">{i.label}</dt>
          <dd className="mt-1 font-serif text-[26px] leading-none">{i.value}</dd>
          <dd className="mt-1.5 text-[12px] text-faint">{i.sub}</dd>
        </Link>
      ))}
    </dl>
  );
}
