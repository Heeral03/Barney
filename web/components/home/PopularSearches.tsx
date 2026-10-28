"use client";

import { useBarney } from "@/lib/barney";
import { ArrowRight } from "../icons";
import { Backpack, Headphones, Laptop, Sneaker } from "../illustrations";

const POPULAR = [
  { title: "Headphones", sub: "Under ₹5,000", ask: "Headphones under ₹5,000", Art: Headphones },
  { title: "Laptops", sub: "For students", ask: "A good laptop for a college student", Art: Laptop },
  { title: "Backpacks", sub: "For everyday use", ask: "A backpack for everyday use", Art: Backpack },
  { title: "Sneakers", sub: "Top rated", ask: "Top rated sneakers", Art: Sneaker },
];

export function PopularSearches() {
  const { send } = useBarney();
  return (
    <section className="mt-14">
      <h2 className="font-serif text-[22px]">Popular Searches</h2>
      <div className="mt-5 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {POPULAR.map(({ title, sub, ask, Art }) => (
          <button
            key={title}
            onClick={() => send(ask)}
            className="group rounded-2xl border border-line bg-[#faf8f5] p-3 text-left transition hover:-translate-y-0.5 hover:border-line-strong hover:shadow-[0_8px_24px_rgba(0,0,0,0.05)]"
          >
            <div className="grid h-[132px] place-items-center rounded-xl">
              <Art className="h-[104px] w-[140px]" />
            </div>
            <div className="mt-3 flex items-end justify-between px-1 pb-1">
              <div>
                <p className="text-[14px] font-medium">{title}</p>
                <p className="mt-0.5 text-[12px] text-faint">{sub}</p>
              </div>
              <ArrowRight width={16} height={16} className="mb-1 text-ink/70 transition group-hover:translate-x-0.5" />
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
