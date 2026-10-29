"use client";

import { signIn } from "next-auth/react";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useBarney } from "@/lib/barney";
import type { Memory, Suggestion } from "@/lib/types";
import { Empty, Page } from "@/components/ui/Page";

const titleOf = (category: string) => (category === "person" || category === "general" ? "About you" : category.charAt(0).toUpperCase() + category.slice(1));

export default function PreferencesPage() {
  const { account, refresh, refreshSettings, settings, profile, ready } = useBarney();
  const [memories, setMemories] = useState<Memory[] | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);

  const load = useCallback(async () => {
    const [m, s] = await Promise.all([api.memories().catch(() => []), api.suggestions().catch(() => [])]);
    setMemories(m);
    setSuggestions(s);
  }, []);

  // Reload whenever who is signed in or which profile is selected changes.
  useEffect(() => {
    if (!ready) return;
    let live = true;
    Promise.all([api.memories().catch(() => []), api.suggestions().catch(() => [])]).then(([m, s]) => {
      if (!live) return;
      setMemories(m);
      setSuggestions(s);
    });
    return () => { live = false; };
  }, [ready, account, profile]);

  const groups = (memories ?? []).reduce<Record<string, Memory[]>>((acc, m) => {
    (acc[titleOf(m.category)] ??= []).push(m);
    return acc;
  }, {});
  const order = Object.keys(groups).sort((a, b) => (a === "About you" ? -1 : b === "About you" ? 1 : a.localeCompare(b)));

  async function forget(m: Memory) {
    await api.forget(m.key);
    setMemories((all) => (all ?? []).filter((x) => x.key !== m.key));
    refresh();
  }

  async function decide(s: Suggestion, decision: "accept" | "dismiss") {
    await api.decide(s.id, decision).catch(() => {});
    await load();
    refresh();
  }

  async function setLearning(on: boolean) {
    await api.setLearning(on);
    await refreshSettings();
  }

  const who = profile === "me" ? "you" : profile;

  return (
    <Page title="What Barney knows" intro={`What I’ve learned about ${who}, and where each thing came from. Change any of it, or make me forget it. Nothing here is a guess you can’t correct.`}>
      <section className="mb-10 flex items-start justify-between gap-6 rounded-2xl border border-line bg-card p-5">
        <div>
          <h2 className="font-serif text-[20px]">Keep learning</h2>
          <p className="mt-1.5 max-w-lg text-[13.5px] leading-6 text-muted">
            When this is on, I remember lasting tastes from what you tell me and what you save. When it’s off I stop saving anything new, and I stop noting which listings you open. What’s already here stays until you remove it.
          </p>
        </div>
        <button
          role="switch"
          aria-checked={settings?.learning ?? true}
          aria-label="Keep learning"
          onClick={() => setLearning(!(settings?.learning ?? true))}
          className={`relative mt-1 h-7 w-12 shrink-0 rounded-full transition ${(settings?.learning ?? true) ? "bg-ink" : "bg-line-strong"}`}
        >
          <span className={`absolute top-1 h-5 w-5 rounded-full bg-white transition-all ${(settings?.learning ?? true) ? "left-6" : "left-1"}`} />
        </button>
      </section>

      {suggestions.length > 0 && (
        <section className="mb-10">
          <h2 className="font-serif text-[22px]">Barney noticed</h2>
          <p className="mt-1 text-[13.5px] text-muted">From the listings you opened. I only keep these if you say so.</p>
          <ul className="mt-3 divide-y divide-line rounded-2xl border border-line bg-card">
            {suggestions.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5 text-[14.5px]">
                <span>{s.text}</span>
                <span className="flex gap-2">
                  <button onClick={() => decide(s, "accept")} className="rounded-full bg-ink px-4 py-1.5 text-[13px] text-white transition hover:bg-ink/85">Yes, remember it</button>
                  <button onClick={() => decide(s, "dismiss")} className="rounded-full border border-line-strong px-4 py-1.5 text-[13px] transition hover:bg-tint/70">Not me</button>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {ready && memories && memories.length === 0 ? (
        <Empty title="I haven’t learned anything yet." text="Tell me what you like (a size, a fit, a brand you avoid) and I’ll remember it for next time." />
      ) : (
        <div className="space-y-8">
          {order.map((group) => (
            <section key={group}>
              <h2 className="font-serif text-[22px]">{group}</h2>
              <ul className="mt-3 divide-y divide-line rounded-2xl border border-line bg-card">
                {groups[group].map((m) => <MemoryRow key={m.key} m={m} onForget={() => forget(m)} onSaved={load} />)}
              </ul>
            </section>
          ))}
        </div>
      )}

      <Profiles />

      {ready && !account && (
        <section className="mt-14 rounded-2xl border border-line bg-[#faf8f5] p-6">
          <h2 className="font-serif text-[20px]">Keep this for good</h2>
          <p className="mt-2 text-[13.5px] leading-6 text-muted">
            Right now I only know you by this browser. Sign in and everything above, plus your wishlist and budget, follows you to any device.
          </p>
          <button onClick={() => signIn("google", { callbackUrl: "/preferences" })} className="mt-4 rounded-lg bg-ink px-5 py-2.5 text-[14px] text-white transition hover:bg-ink/85">
            Sign in with Google
          </button>
        </section>
      )}
    </Page>
  );
}

function MemoryRow({ m, onForget, onSaved }: { m: Memory; onForget: () => void; onSaved: () => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(m.text);
  const [error, setError] = useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.editMemory(m.key, text);
      setEditing(false);
      setError(false);
      await onSaved();
    } catch {
      setError(true);
    }
  }

  return (
    <li className="px-5 py-3.5 text-[14.5px]">
      {editing ? (
        <form onSubmit={save} className="flex flex-wrap items-center gap-2">
          <input value={text} onChange={(e) => setText(e.target.value)} maxLength={140} aria-label="Edit this preference" autoFocus className="h-10 min-w-0 flex-1 rounded-lg border border-line-strong bg-paper px-3 outline-none focus:border-ink/50" />
          <button className="rounded-full bg-ink px-4 py-1.5 text-[13px] text-white">Save</button>
          <button type="button" onClick={() => { setEditing(false); setText(m.text); setError(false); }} className="text-[13px] text-muted underline underline-offset-4">Cancel</button>
          {error && <span className="w-full text-[12.5px] text-danger">Write at least two words.</span>}
        </form>
      ) : (
        <div className="flex items-center justify-between gap-4">
          <span>
            {m.text}
            <span className={`ml-2.5 rounded-full px-2 py-0.5 text-[11px] ${m.source === "inferred" ? "bg-tint text-muted" : "bg-sage-bg text-sage-ink"}`}>
              {m.source === "inferred" ? "I picked this up" : "You told me"}
            </span>
          </span>
          <span className="flex shrink-0 gap-4 text-[13px] text-faint">
            <button onClick={() => setEditing(true)} className="underline-offset-4 transition hover:text-ink hover:underline">Edit</button>
            <button onClick={onForget} className="underline-offset-4 transition hover:text-danger hover:underline">Forget</button>
          </span>
        </div>
      )}
    </li>
  );
}

function Profiles() {
  const { settings, refreshSettings, profile, setProfile } = useBarney();
  const others = (settings?.profiles ?? []).filter((p) => p !== "me");
  if (!others.length) return null;

  async function remove(name: string) {
    await api.removeProfile(name);
    if (profile === name) setProfile("me");
    await refreshSettings();
  }

  return (
    <section className="mt-14">
      <h2 className="font-serif text-[22px]">Profiles</h2>
      <p className="mt-1 text-[13.5px] text-muted">Each one keeps its own tastes. Switch between them from the sidebar.</p>
      <ul className="mt-3 divide-y divide-line rounded-2xl border border-line bg-card">
        {others.map((p) => (
          <li key={p} className="flex items-center justify-between px-5 py-3.5 text-[14.5px]">
            <span>{p}</span>
            <button onClick={() => remove(p)} className="text-[13px] text-faint underline-offset-4 transition hover:text-danger hover:underline">Remove</button>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[12.5px] text-faint">Removing a profile hides it. Its saved tastes stay in case you add it back.</p>
    </section>
  );
}
