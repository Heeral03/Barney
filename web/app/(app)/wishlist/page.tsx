"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useBarney } from "@/lib/barney";
import { ago, inr } from "@/lib/format";
import type { PriceAlert, WishItem } from "@/lib/types";
import { ArtFor } from "@/components/illustrations";
import { HeartIcon } from "@/components/icons";
import { Img } from "@/components/Img";
import { Empty, Page } from "@/components/ui/Page";

export default function WishlistPage() {
  const { wishlist, refresh, ready } = useBarney();
  const [alerts, setAlerts] = useState<PriceAlert[]>([]);

  // Price drops that reached a target since the last visit; seeing them here counts as reading them.
  useEffect(() => {
    if (!ready) return;
    api.alerts().then((a) => {
      setAlerts(a);
      if (a.length) api.alertsSeen().then(() => refresh()).catch(() => {});
    }).catch(() => {});
  }, [ready, refresh]);

  return (
    <Page title="Your wishlist" intro="Everything you’ve hearted. Set the price you’re waiting for and I’ll flag an item when it gets there. Each heart also teaches me what you like.">
      {alerts.length > 0 && (
        <div className="mb-6 rounded-2xl border border-sage-ink/30 bg-sage-bg p-5" role="status">
          <p className="font-serif text-[20px] text-sage-ink">Good news: {alerts.length === 1 ? "a price" : `${alerts.length} prices`} dropped to your target</p>
          <ul className="mt-2 space-y-1 text-[14px]">
            {alerts.map((a) => (
              <li key={a.id}>
                {a.link ? <a href={a.link} target="_blank" rel="noopener noreferrer" className="underline underline-offset-4">{a.title}</a> : a.title}
                {" "}is now <strong>{inr(a.price_inr)}</strong> (your target was {inr(a.target_inr)}).
              </li>
            ))}
          </ul>
        </div>
      )}

      {ready && wishlist.length === 0 ? (
        <Empty title="Nothing saved yet." text="Tap the heart on any product and it will wait for you here.">
          <Link href="/app" className="mt-5 inline-block rounded-full bg-ink px-5 py-2.5 text-[14px] text-white transition hover:bg-ink/85">Find something</Link>
        </Empty>
      ) : (
        <ul className="divide-y divide-line rounded-2xl border border-line bg-card">
          {wishlist.map((w) => <Row key={w.id} item={w} onChange={refresh} />)}
        </ul>
      )}
    </Page>
  );
}

function Row({ item: w, onChange }: { item: WishItem; onChange: () => Promise<void> }) {
  const [target, setTarget] = useState(w.target_inr ? String(Math.round(w.target_inr)) : "");
  const hit = !!(w.target_inr && w.price_inr && w.price_inr <= w.target_inr);
  const [checking, setChecking] = useState<"idle" | "busy" | "unreadable">("idle");

  async function checkNow() {
    setChecking("busy");
    try {
      const r = await api.checkPrice(w.id);
      setChecking(r.price === null ? "unreadable" : "idle");
      await onChange();
    } catch {
      setChecking("unreadable");
    }
  }

  async function save() {
    const value = target.trim() === "" ? null : Number(target.replace(/[^\d.]/g, ""));
    if (value === (w.target_inr ?? null) || (value !== null && Number.isNaN(value))) return;
    await api.setTarget(w.id, value);
    await onChange();
  }

  return (
    <li className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
      <div className="grid h-[84px] w-[104px] shrink-0 place-items-center rounded-xl bg-[#f7f5f1]">
        {w.image_url ? <Img src={w.image_url} className="h-full w-full object-contain p-2 mix-blend-multiply" /> : <ArtFor text={w.title} className="h-14 w-16" />}
      </div>
      <div className="min-w-0 flex-1">
        <p className="line-clamp-2 text-[15px] font-medium leading-snug">{w.title}</p>
        <p className="mt-1 text-[13.5px] text-muted">{w.price_display}{w.seller ? ` · ${w.seller}` : ""}</p>
        <p className="mt-1 text-[12.5px] text-faint">
          {w.checks && w.price_low !== undefined && w.price_high !== undefined
            ? `Seen between ${inr(w.price_low)} and ${inr(w.price_high)} · checked ${ago(w.checked_at)}`
            : "I check the store’s page for price changes every few hours"}
          {" · "}
          <button onClick={checkNow} disabled={checking === "busy"} className="underline underline-offset-4 hover:text-ink disabled:opacity-60">
            {checking === "busy" ? "Checking…" : "Check now"}
          </button>
          {checking === "unreadable" && <span className="text-[#8a5a1c]"> · this store won’t let me read its page</span>}
        </p>
        {w.link && <a href={w.link} target="_blank" rel="noopener noreferrer" className="mt-1 inline-block text-[13px] underline underline-offset-4 hover:text-muted">View at {w.seller ?? "the seller"}</a>}
      </div>
      <div className="flex items-center gap-4">
        <label className="block text-[12px] text-faint">
          Target price
          <span className="mt-1 flex items-center rounded-lg border border-line-strong bg-paper px-3 focus-within:border-ink/50">
            <span className="text-muted">₹</span>
            <input
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              onBlur={save}
              onKeyDown={(e) => e.key === "Enter" && (e.currentTarget.blur())}
              inputMode="numeric"
              placeholder="e.g. 6500"
              className="h-10 w-28 bg-transparent px-2 text-[14px] text-ink outline-none placeholder:text-faint"
            />
          </span>
        </label>
        {hit && <span className="whitespace-nowrap rounded-full bg-sage-bg px-3 py-1 text-[12px] text-sage-ink">At your target</span>}
        <button
          onClick={async () => { await api.removeWish(w.id); await onChange(); }}
          aria-label="Remove from wishlist"
          className="rounded-full p-2 text-danger transition hover:bg-tint"
        >
          <HeartIcon filled width={20} height={20} />
        </button>
      </div>
      {w.target_inr && !hit && w.price_inr ? <p className="text-[12px] text-faint sm:hidden">{inr(w.price_inr - w.target_inr)} above your target</p> : null}
    </li>
  );
}
