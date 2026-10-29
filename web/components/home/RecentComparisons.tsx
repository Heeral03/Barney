"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useBarney } from "@/lib/barney";
import { compact, priceRange } from "@/lib/format";
import type { ComparisonCard } from "@/lib/types";
import { ArrowRight, StarIcon } from "../icons";
import { ArtFor } from "../illustrations";
import { Img } from "../Img";
import { Section } from "./Section";

export function RecentComparisons() {
  const { overview, openThread } = useBarney();
  const [all, setAll] = useState<ComparisonCard[] | null>(null);
  const cards = all ?? overview?.comparisons ?? [];
  const total = overview?.stats.comparisons ?? 0;

  if (!overview) return null;

  return (
    <Section
      label="Your history"
      title="Pick up where you left off"
      action={total > 3 && !all ? (
        <button onClick={() => api.comparisons(12).then(setAll)} className="inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-ink">
          View all <ArrowRight width={15} height={15} />
        </button>
      ) : null}
    >
      {cards.length === 0 ? (
        <p className="text-[14px] leading-6 text-muted">Nothing yet. Ask Barney for something, tap “Compare these side by side”, and it lands here.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {cards.slice(0, all ? 12 : 3).map((c) => (
            <Card key={c.thread_id + c.title} c={c} onOpen={() => openThread(c.thread_id)} />
          ))}
        </div>
      )}
    </Section>
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
    </button>
  );
}
