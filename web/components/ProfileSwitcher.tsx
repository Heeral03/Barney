"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useBarney } from "@/lib/barney";

/** Who Barney is shopping for. Each profile keeps its own tastes, so a gift for Mom doesn't change what he knows about you. */
export function ProfileSwitcher({ compact = false }: { compact?: boolean }) {
  const { settings, profile, setProfile, newChat, refresh, refreshSettings } = useBarney();
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const profiles = settings?.profiles ?? ["me"];
  const label = (p: string) => (p === "me" ? "Me" : p);

  function choose(p: string) {
    if (p === profile) return;
    setProfile(p);
    newChat(); // a new conversation, so one person's answers don't carry into another's
    refresh();
  }

  async function add(e: React.FormEvent) {
    e.preventDefault();
    const clean = name.trim();
    if (!clean) return;
    const next = await api.addProfile(clean).catch(() => null);
    setName("");
    setAdding(false);
    if (next) {
      await refreshSettings();
      const made = next.profiles.find((p) => p.toLowerCase() === clean.toLowerCase().slice(0, 30)) ?? clean;
      choose(made);
    }
  }

  return (
    <div className={compact ? "" : "mb-4"}>
      <label className="block text-[11.5px] uppercase tracking-[0.12em] text-faint" htmlFor={compact ? "profile-mobile" : "profile"}>Shopping for</label>
      <div className="mt-1.5 flex items-center gap-2">
        <select
          id={compact ? "profile-mobile" : "profile"}
          value={profile}
          onChange={(e) => choose(e.target.value)}
          className="h-9 min-w-0 flex-1 rounded-lg border border-line-strong bg-card px-2.5 text-[13.5px] text-ink"
        >
          {profiles.map((p) => <option key={p} value={p}>{label(p)}</option>)}
        </select>
        <button onClick={() => setAdding((a) => !a)} aria-label="Add a profile" aria-expanded={adding} className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-line-strong text-[18px] leading-none text-ink/80 transition hover:bg-tint/70">+</button>
      </div>
      {adding && (
        <form onSubmit={add} className="mt-2 flex gap-2">
          <input autoFocus value={name} onChange={(e) => setName(e.target.value)} maxLength={30} placeholder="Mom, Gift for Riya…" aria-label="Name of the new profile" className="h-9 min-w-0 flex-1 rounded-lg border border-line-strong bg-card px-2.5 text-[13.5px] outline-none placeholder:text-faint" />
          <button className="h-9 rounded-lg bg-ink px-3 text-[13px] text-white">Add</button>
        </form>
      )}
    </div>
  );
}
