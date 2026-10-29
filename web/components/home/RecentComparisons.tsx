"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useBarney } from "@/lib/barney";
import { compact, priceRange } from "@/lib/format";
import type { ComparisonCard } from "@/lib/types";
import { ArrowRight, StarIcon } from "../icons";
import { ArtFor } from "../illustrations";
import { Img } from "../Img";

export function RecentComparisons() {
  const { overview, openThread, send } = useBarney();
  const [all, setAll] = useState<ComparisonCard[] | null>(null);
  const cards = all ?? overview?.comparisons ?? [];
  const total = overview?.stats.comparisons ?? 0;

  if (!overview) return <section className="mt-14 h-72" aria-hidden />;

  return (
    <section className="mt-14 pb-14">
      <div className="flex items-baseline justify-between">
        <h2 className="font-serif text-[22px]">Recent Comparisons</h2>
        {total > 3 && !all && (
          <button onClick={() => api.comparisons(12).then(setAll)} className="inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-ink">
            View all <ArrowRight width={15} height={15} />
          </button>
        )}
      </div>

      {cards.length === 0 ? (
        <div className="mt-5 rounded-2xl border border-dashed border-line-strong bg-card/60 p-8 text-center">
          <p className="font-serif text-[20px]">Your comparisons will live here.</p>
          <p className="mx-auto mt-2 max-w-md text-[14px] leading-6 text-muted">
            Ask Barney for something, then tap “Compare these side by side”. You can come back to it any time.
          </p>
          <button onClick={() => send("Best laptop for programming")} className="mt-5 rounded-full bg-ink px-5 py-2.5 text-[14px] text-white transition hover:bg-ink/85">
            Try “Best laptop for programming”
          </button>
        </div>
      ) : (
        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {cards.map((c) => (
            <Card key={c.thread_id + c.title} c={c} onOpen={() => openThread(c.thread_id)} />
          ))}
        </div>
      )}
    </section>
  );
}

function Card({ c, onOpen }: { c: ComparisonCard; onOpen: () => void }) {
  return (
    <button onClick={onOpen} className="group flex flex-col rounded-2xl border border-line bg-card p-4 text-left transition hover:-translate-y-0.5 hover:border-line-strong hover:shadow-[0_8px_24px_rgba(0,0,0,0.05)]">
      <div className="grid h-[150px] place-items-center rounded-xl bg-[#f7f5f1]">
        {c.image_url ? <Img src={c.image_url} className="h-full w-full object-contain p-3 mix-blend-multiply" /> : <ArtFor text={c.title} className="h-24 w-32" />}
      </div>
      <p className="mt-4 line-clamp-1 text-[15px] font-medium">{c.title}</p>
      <p className="mt-0.5 text-[13px] text-muted">{c.options} options compared</p>
      <p className="mt-3 text-[17px] font-medium">{priceRange(c.price_low, c.price_high)}</p>
      {c.rating ? (
        <p className="mt-1 flex items-center gap-1.5 text-[13px] text-muted">
          <StarIcon className="text-amber" /> {c.rating}
          {c.rating_count ? <span className="text-faint">({compact(c.rating_count)} reviews)</span> : null}
        </p>
      ) : null}
      <span className="mt-3 w-fit rounded-full bg-sage-bg px-3 py-1 text-[12px] text-sage-ink">{c.tag}</span>
      <p className="mt-4 border-t border-line pt-3 text-[12px] text-faint">
        {c.stores} {c.stores === 1 ? "store" : "stores"} <span className="mx-1">·</span> Price comparison available
      </p>
    </button>
  );
}
