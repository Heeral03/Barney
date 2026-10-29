"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

const IDEAS = ["Best laptops for coding", "Stylish work bags under ₹5k", "Skincare for oily skin", "Travel cameras under 1L"];

export function LandingSearch() {
  const router = useRouter();
  const [text, setText] = useState("");

  const go = (q: string) => {
    const query = q.trim();
    router.push(query ? `/app?q=${encodeURIComponent(query)}` : "/app");
  };

  return (
    <div className="mx-auto w-full max-w-[760px] rounded-3xl border border-line bg-card p-6 sm:p-8">
      <div className="flex items-center gap-4">
        <span aria-hidden className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-tint font-serif text-[22px]">B</span>
        <div>
          <p className="text-[17px] font-medium">Hey, I’m Barney.</p>
          <p className="text-[14.5px] text-muted">What are you looking to buy today?</p>
        </div>
      </div>
      <form onSubmit={(e) => { e.preventDefault(); go(text); }} className="mt-6 flex items-center gap-2 rounded-full border border-line-strong bg-paper py-1.5 pl-5 pr-1.5">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          aria-label="What are you looking to buy?"
          placeholder="e.g. laptop for college, work bag, headphones…"
          className="min-w-0 flex-1 bg-transparent py-2 text-[15px] outline-none placeholder:text-faint"
        />
        <button type="submit" aria-label="Start shopping" className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-ink text-white transition hover:bg-ink/85">→</button>
      </form>
      <div className="mt-4 flex flex-wrap gap-2">
        {IDEAS.map((i) => (
          <button key={i} onClick={() => go(i)} className="rounded-full border border-line px-3.5 py-1.5 text-[13px] text-muted transition hover:bg-tint/70 hover:text-ink">{i}</button>
        ))}
      </div>
    </div>
  );
}
