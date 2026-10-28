"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useBarney } from "@/lib/barney";
import { inr } from "@/lib/format";
import { Page } from "@/components/ui/Page";

export default function BudgetPage() {
  const { overview } = useBarney();
  // Keyed so the field restarts from the saved amount once it loads or changes.
  return <BudgetView key={overview?.budget?.amount ?? "none"} />;
}

function BudgetView() {
  const { overview, wishlist, userId, refresh } = useBarney();
  const budget = overview?.budget;
  const [value, setValue] = useState(budget?.amount ? String(Math.round(budget.amount)) : "");
  const [saved, setSaved] = useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const n = value.trim() === "" ? null : Number(value.replace(/[^\d.]/g, ""));
    if (n !== null && (Number.isNaN(n) || n < 0)) return;
    await api.setBudget(userId, n);
    await refresh();
    setSaved(true);
    setTimeout(() => setSaved(false), 1800);
  }

  const priced = wishlist.filter((w) => w.price_inr).sort((a, b) => (b.price_inr ?? 0) - (a.price_inr ?? 0));
  const total = budget?.wishlist_total ?? 0;
  const over = budget?.remaining != null && budget.remaining < 0;

  return (
    <Page title="Your budget" intro="Set what you’re comfortable spending. I’ll show how much is left once everything on your wishlist is counted.">
      <form onSubmit={save} className="flex flex-wrap items-end gap-3 rounded-2xl border border-line bg-card p-6">
        <label className="block text-[13px] text-muted">
          Budget
          <span className="mt-2 flex items-center rounded-xl border border-line-strong bg-paper px-4 focus-within:border-ink/50">
            <span className="text-[18px] text-muted">₹</span>
            <input value={value} onChange={(e) => setValue(e.target.value)} inputMode="numeric" placeholder="e.g. 25000" className="h-12 w-48 bg-transparent px-3 text-[18px] text-ink outline-none placeholder:text-faint" />
          </span>
        </label>
        <button className="h-12 rounded-xl bg-ink px-6 text-[14px] text-white transition hover:bg-ink/85">{saved ? "Saved" : "Save budget"}</button>
      </form>

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <Stat label="Budget" value={budget?.amount != null ? inr(budget.amount) : "Not set"} />
        <Stat label="Wishlist total" value={inr(total) || "₹0"} />
        <Stat label={over ? "Over budget by" : "Remaining"} value={budget?.remaining != null ? inr(Math.abs(budget.remaining)) : "—"} tone={over ? "bad" : budget?.remaining != null ? "good" : undefined} />
      </div>

      <h2 className="mt-12 font-serif text-[24px]">Where it would go</h2>
      {priced.length === 0 ? (
        <p className="mt-3 text-[14.5px] text-muted">Save products to your wishlist and they’ll show up here, largest first.</p>
      ) : (
        <ul className="mt-4 space-y-3">
          {priced.map((w) => (
            <li key={w.id}>
              <div className="flex justify-between gap-4 text-[14px]"><span className="line-clamp-1">{w.title}</span><span className="shrink-0 text-muted">{inr(w.price_inr)}</span></div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-tint"><div className="h-full rounded-full bg-ink/70" style={{ width: `${Math.max(3, ((w.price_inr ?? 0) / total) * 100)}%` }} /></div>
            </li>
          ))}
        </ul>
      )}
    </Page>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "good" | "bad" }) {
  return (
    <div className="rounded-2xl border border-line bg-card p-5">
      <p className="text-[13px] text-muted">{label}</p>
      <p className={`mt-1.5 font-serif text-[30px] leading-none ${tone === "bad" ? "text-danger" : tone === "good" ? "text-sage-ink" : ""}`}>{value}</p>
    </div>
  );
}
