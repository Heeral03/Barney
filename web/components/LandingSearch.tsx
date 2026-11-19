"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowRight } from "./icons";

const IDEAS = ["Best laptops for coding", "Stylish work bags under ₹5k", "Skincare for oily skin", "Travel cameras under 1L"];

export function LandingSearch() {
  const router = useRouter();
  const [text, setText] = useState("");

  const go = (q: string) => {
    const query = q.trim();
    router.push(query ? `/app?q=${encodeURIComponent(query)}` : "/app");
  };

  return (
    <div className="elev-lg mx-auto w-full max-w-[720px] rounded-[28px] border border-line bg-card p-5 sm:p-7">
      <div className="flex items-center gap-3.5">
        <span aria-hidden className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-ink font-serif text-[20px] text-white">B</span>
        <div className="text-left">
          <p className="text-[15.5px] font-medium">Hey, I’m Barney.</p>
          <p className="text-[14px] text-muted">What are you looking to buy today?</p>
        </div>
      </div>
      <form
        onSubmit={(e) => { e.preventDefault(); go(text); }}
        className="mt-5 flex items-center gap-2 rounded-full border border-line-strong bg-paper py-1.5 pl-5 pr-1.5 transition-colors focus-within:border-ink/50"
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          name="q"
          type="text"
          autoComplete="off"
          aria-label="What are you looking to buy?"
          placeholder="e.g. laptop for college, work bag, headphones…"
          className="min-w-0 flex-1 bg-transparent py-2.5 text-[15px] outline-none placeholder:text-faint"
        />
        <button type="submit" aria-label="Start shopping" className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-ink text-white transition-colors hover:bg-ink/85">
          <ArrowRight />
        </button>
      </form>
      <div className="mt-4 flex flex-wrap justify-center gap-2 sm:justify-start">
        {IDEAS.map((i) => (
          <button key={i} type="button" onClick={() => go(i)} className="rounded-full border border-line px-3.5 py-1.5 text-[13px] text-muted transition-colors hover:border-line-strong hover:bg-tint/70 hover:text-ink">{i}</button>
        ))}
      </div>
    </div>
  );
}
