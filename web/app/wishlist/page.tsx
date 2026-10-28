"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { useBarney } from "@/lib/barney";
import { inr } from "@/lib/format";
import type { WishItem } from "@/lib/types";
import { ArtFor } from "@/components/illustrations";
import { HeartIcon } from "@/components/icons";
import { Img } from "@/components/Img";
import { Empty, Page } from "@/components/ui/Page";

export default function WishlistPage() {
  const { wishlist, userId, refresh, ready } = useBarney();

  return (
    <Page title="Your wishlist" intro="Everything you’ve hearted. Set the price you’re waiting for and I’ll flag an item when it gets there. Each heart also teaches me what you like.">
      {ready && wishlist.length === 0 ? (
        <Empty title="Nothing saved yet." text="Tap the heart on any product and it will wait for you here.">
          <Link href="/" className="mt-5 inline-block rounded-full bg-ink px-5 py-2.5 text-[14px] text-white transition hover:bg-ink/85">Find something</Link>
        </Empty>
      ) : (
        <ul className="divide-y divide-line rounded-2xl border border-line bg-card">
          {wishlist.map((w) => <Row key={w.id} item={w} userId={userId} onChange={refresh} />)}
        </ul>
      )}
    </Page>
  );
}

function Row({ item: w, userId, onChange }: { item: WishItem; userId: string; onChange: () => Promise<void> }) {
  const [target, setTarget] = useState(w.target_inr ? String(Math.round(w.target_inr)) : "");
  const hit = !!(w.target_inr && w.price_inr && w.price_inr <= w.target_inr);

  async function save() {
    const value = target.trim() === "" ? null : Number(target.replace(/[^\d.]/g, ""));
    if (value === (w.target_inr ?? null) || (value !== null && Number.isNaN(value))) return;
    await api.setTarget(userId, w.id, value);
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
          onClick={async () => { await api.removeWish(userId, w.id); await onChange(); }}
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
