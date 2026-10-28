"use client";

import { useBarney } from "@/lib/barney";
import { ArrowRight } from "../icons";

const SUGGESTIONS = ["Headphones under ₹5,000", "A work bag for everyday use", "Best laptop for programming", "Find a better price"];

export function Hero() {
  const { send, hasHistory, resume } = useBarney();
  return (
    <section className="pt-8 md:pt-12">
      <p className="text-[12px] font-medium uppercase tracking-[0.16em] text-muted">Suit up. Your wingman for buying things</p>
      <h1 className="mt-5 font-serif text-[48px] font-normal leading-[1.02] tracking-[-0.02em] sm:text-[64px] lg:text-[76px]">
        It’s gonna be legen<span className="text-faint">… wait for it …</span>dary.
      </h1>
      <p className="mt-6 max-w-2xl text-[16px] leading-7 text-muted">
        Tell Barney what you’re after. He’ll hunt down the options, compare every store’s price, and pick the one that’s actually awesome. Please, have a seat.
      </p>

      <div className="mt-8 flex flex-wrap gap-3">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => send(s)}
            className="rounded-full border border-line-strong bg-card px-5 py-2.5 text-[14px] text-ink/85 transition hover:border-ink/40 hover:bg-tint/60"
          >
            {s}
          </button>
        ))}
      </div>

      {hasHistory && (
        <button onClick={resume} className="group mt-6 inline-flex items-center gap-2 text-[14px] text-muted transition hover:text-ink">
          Continue where you left off
          <ArrowRight width={16} height={16} className="transition group-hover:translate-x-0.5" />
        </button>
      )}
    </section>
  );
}
