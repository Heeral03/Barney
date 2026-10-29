"use client";

import { useSyncExternalStore } from "react";
import { useBarney } from "@/lib/barney";
import { greeting } from "@/lib/format";
import { ArrowRight } from "../icons";

const SUGGESTIONS = ["Headphones under ₹5,000", "A work bag for everyday use", "Best laptop for programming"];

const noSubscribe = () => () => {};
/** The time of day is only known in the browser, so the server render says a plain "Hello". */
function useGreeting(): string {
  return useSyncExternalStore(noSubscribe, () => greeting(), () => "Hello");
}

export function Hero() {
  const { send, hasHistory, resume, account, overview } = useBarney();
  const hello = useGreeting();
  const name = (account?.name ?? overview?.name)?.split(" ")[0];
  return (
    <section className="pb-12 pt-8 md:pt-14">
      <div>
        <p className="text-[12px] font-medium uppercase tracking-[0.16em] text-muted">Suit up</p>
        <h1 className="mt-4 font-serif text-[40px] font-normal leading-[1.06] tracking-[-0.02em] sm:text-[56px]">
          {hello}{name ? `, ${name}` : ""}.
          <span className="block text-faint">What’s the next legendary buy?</span>
        </h1>
        <div className="mt-8 flex flex-wrap gap-3">
          {SUGGESTIONS.map((s) => (
            <button key={s} onClick={() => send(s)} className="rounded-full border border-line-strong bg-card px-5 py-2.5 text-[14px] text-ink/85 transition hover:border-ink/40 hover:bg-tint/60">
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
      </div>
    </section>
  );
}
