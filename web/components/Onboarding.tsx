"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useBarney } from "@/lib/barney";

const CATEGORIES = ["Laptops and phones", "Headphones and audio", "Clothing", "Shoes", "Home and kitchen", "Beauty", "Gifts"];
const PRIORITIES = ["Best quality", "Best value", "Lowest price", "Latest models"];
const SPEND = ["under ₹2,000", "₹2,000 to ₹10,000", "₹10,000 to ₹50,000", "over ₹50,000"];

/** Three taps on first sign-in, so the very first search already knows a little. Everything can be skipped. */
export function Onboarding() {
  const { account, settings, ready, refreshSettings, refresh } = useBarney();
  const [step, setStep] = useState(0);
  const [cats, setCats] = useState<string[]>([]);
  const [priority, setPriority] = useState("");
  const [spend, setSpend] = useState("");
  const [busy, setBusy] = useState(false);

  if (!ready || !account || !settings || settings.onboarded) return null;

  async function finish(skip = false) {
    setBusy(true);
    await api.onboarding(skip ? [] : cats, skip ? "" : priority, skip ? "" : spend).catch(() => {});
    api.track("onboarding_done");
    await refreshSettings();
    refresh();
  }

  const steps = [
    { title: "What do you usually shop for?", hint: "Pick any.", options: CATEGORIES, multi: true },
    { title: "What matters most to you?", hint: "Pick one.", options: PRIORITIES, multi: false },
    { title: "What do you usually spend on one purchase?", hint: "Pick one.", options: SPEND, multi: false },
  ] as const;
  const s = steps[step];
  const chosen = step === 0 ? cats : [step === 1 ? priority : spend];
  const pick = (o: string) => {
    if (step === 0) setCats((c) => (c.includes(o) ? c.filter((x) => x !== o) : [...c, o]));
    else if (step === 1) setPriority(o);
    else setSpend(o);
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink/30 px-5 backdrop-blur-[2px]" role="dialog" aria-modal="true" aria-labelledby="onboarding-title">
      <div className="w-full max-w-lg rounded-3xl border border-line bg-paper p-8 shadow-[0_24px_64px_rgba(0,0,0,0.18)]">
        <p className="text-[12px] font-medium uppercase tracking-[0.16em] text-muted">Step {step + 1} of 3</p>
        <h2 id="onboarding-title" className="mt-3 font-serif text-[30px] leading-tight tracking-[-0.01em]">{s.title}</h2>
        <p className="mt-1 text-[14px] text-muted">{s.hint}</p>
        <div className="mt-6 flex flex-wrap gap-2.5">
          {s.options.map((o) => (
            <button key={o} onClick={() => pick(o)} aria-pressed={chosen.includes(o)}
              className={`rounded-full border px-4 py-2 text-[14px] transition ${chosen.includes(o) ? "border-ink bg-ink text-white" : "border-line-strong bg-card text-ink/85 hover:border-ink/40 hover:bg-tint/60"}`}>
              {o}
            </button>
          ))}
        </div>
        <div className="mt-8 flex items-center justify-between">
          <button onClick={() => finish(true)} disabled={busy} className="text-[14px] text-muted underline-offset-4 hover:text-ink hover:underline">Skip for now</button>
          <button
            onClick={() => (step < 2 ? setStep(step + 1) : finish())}
            disabled={busy}
            className="rounded-full bg-ink px-7 py-2.5 text-[14.5px] text-white transition hover:bg-ink/85 disabled:opacity-60"
          >
            {step < 2 ? "Next" : "Done"}
          </button>
        </div>
      </div>
    </div>
  );
}
