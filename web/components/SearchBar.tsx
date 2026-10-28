"use client";

import { useRouter, usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useBarney } from "@/lib/barney";
import { inr } from "@/lib/format";
import { ArrowUp, BellIcon, SearchIcon } from "./icons";

/** The one search bar. It is also the chat box: whatever you type, Barney answers in the conversation below. */
export function SearchBar() {
  const { send, sending, ready, wishlist } = useBarney();
  const router = useRouter();
  const path = usePathname();
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const bell = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (ready) input.current?.focus();
  }, [ready]);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (bell.current && !bell.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  // Alerts are only things we know: a saved item whose price is at or under the price you are waiting for.
  const alerts = wishlist.filter((w) => w.target_inr && w.price_inr && w.price_inr <= w.target_inr);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const message = text.trim();
    if (!message || sending) return;
    setText("");
    if (path !== "/") router.push("/");
    send(message);
  }

  return (
    <div className="flex items-center gap-4">
      <form onSubmit={submit} className="group flex h-[52px] flex-1 items-center gap-3 rounded-xl border border-line-strong bg-card px-4 shadow-[0_1px_0_rgba(0,0,0,0.02)] transition focus-within:border-ink/40 focus-within:shadow-[0_0_0_4px_rgba(22,21,19,0.05)]">
        <SearchIcon className="shrink-0 text-muted" />
        <input
          ref={input}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Tell Barney what you’re looking for…"
          aria-label="Tell Barney what you’re looking for"
          className="h-full min-w-0 flex-1 bg-transparent text-[15px] text-ink outline-none placeholder:text-faint"
        />
        <button
          type="submit"
          disabled={!text.trim() || sending}
          aria-label="Send"
          className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-ink text-white transition disabled:scale-90 disabled:opacity-0"
        >
          <ArrowUp width={18} height={18} />
        </button>
      </form>

      <div ref={bell} className="relative">
        <button onClick={() => setOpen((o) => !o)} aria-label="Notifications" className="relative rounded-full p-2 text-ink/80 transition hover:bg-tint">
          <BellIcon width={22} height={22} />
          {alerts.length > 0 && <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-danger" />}
        </button>
        {open && (
          <div className="rise absolute right-0 top-12 z-30 w-80 rounded-2xl border border-line bg-card p-4 shadow-[0_12px_40px_rgba(0,0,0,0.08)]">
            <p className="font-serif text-lg">Alerts</p>
            {alerts.length === 0 ? (
              <p className="mt-2 text-[14px] text-muted">You’re all caught up. Set a target price on a wishlist item and I’ll flag it here.</p>
            ) : (
              <ul className="mt-2 divide-y divide-line">
                {alerts.map((w) => (
                  <li key={w.id} className="py-2.5 text-[14px]">
                    <span className="line-clamp-1">{w.title}</span>
                    <span className="text-sage-ink">{inr(w.price_inr)} is at or under your {inr(w.target_inr)} target</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
