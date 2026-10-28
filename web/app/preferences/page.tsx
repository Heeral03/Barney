"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useBarney } from "@/lib/barney";
import type { Memory } from "@/lib/types";
import { Empty, Page } from "@/components/ui/Page";

const titleOf = (category: string) => (category === "person" || category === "general" ? "About you" : category.charAt(0).toUpperCase() + category.slice(1));

export default function PreferencesPage() {
  const { userId, setUserId, refresh, ready } = useBarney();
  const [memories, setMemories] = useState<Memory[] | null>(null);
  const [copied, setCopied] = useState(false);
  const [other, setOther] = useState("");

  useEffect(() => {
    if (userId) api.memories(userId).then(setMemories).catch(() => setMemories([]));
  }, [userId]);

  const groups = (memories ?? []).reduce<Record<string, Memory[]>>((acc, m) => {
    (acc[titleOf(m.category)] ??= []).push(m);
    return acc;
  }, {});
  const order = Object.keys(groups).sort((a, b) => (a === "About you" ? -1 : b === "About you" ? 1 : a.localeCompare(b)));

  async function forget(m: Memory) {
    await api.forget(userId, m.key);
    setMemories((all) => (all ?? []).filter((x) => x.key !== m.key));
    refresh();
  }

  return (
    <Page title="My preferences" intro="What I’ve learned from what you’ve told me and what you’ve saved. Nothing here is a guess, and you can make me forget any of it.">
      {ready && memories && memories.length === 0 ? (
        <Empty title="I haven’t learned anything yet." text="Tell me what you like (a size, a fit, a brand you avoid) and I’ll remember it for next time." />
      ) : (
        <div className="space-y-8">
          {order.map((group) => (
            <section key={group}>
              <h2 className="font-serif text-[22px]">{group}</h2>
              <ul className="mt-3 divide-y divide-line rounded-2xl border border-line bg-card">
                {groups[group].map((m) => (
                  <li key={m.key} className="flex items-center justify-between gap-4 px-5 py-3.5 text-[14.5px]">
                    <span>{m.text}</span>
                    <button onClick={() => forget(m)} className="shrink-0 text-[13px] text-faint underline-offset-4 transition hover:text-danger hover:underline">Forget</button>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}

      <section className="mt-14 rounded-2xl border border-line bg-[#faf8f5] p-6">
        <h2 className="font-serif text-[20px]">Your Barney ID</h2>
        <p className="mt-2 text-[13.5px] leading-6 text-muted">This is how I recognise you on this device. Use the same ID on another browser to bring your preferences and wishlist with you.</p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <code className="rounded-lg border border-line bg-card px-3 py-2 text-[13px]">{userId || "…"}</code>
          <button onClick={() => { navigator.clipboard?.writeText(userId); setCopied(true); setTimeout(() => setCopied(false), 1500); }} className="text-[13px] underline underline-offset-4 hover:text-muted">{copied ? "Copied" : "Copy"}</button>
        </div>
        <form onSubmit={(e) => { e.preventDefault(); setUserId(other); setOther(""); }} className="mt-5 flex flex-wrap gap-3">
          <input value={other} onChange={(e) => setOther(e.target.value)} placeholder="Paste an existing Barney ID" className="h-11 w-72 rounded-lg border border-line-strong bg-card px-3 text-[14px] outline-none placeholder:text-faint focus:border-ink/50" />
          <button disabled={!other.trim()} className="h-11 rounded-lg border border-line-strong px-5 text-[14px] transition hover:bg-tint/70 disabled:opacity-50">Use this ID</button>
        </form>
      </section>
    </Page>
  );
}
